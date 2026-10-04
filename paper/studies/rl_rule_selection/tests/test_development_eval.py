"""Pruebas de la evaluación de desarrollo. No usan los 40 pedidos reales."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import torch

STUDY = Path(__file__).resolve().parents[1]
TOOLS = STUDY / "tools"
PAPER_TOOLS = STUDY.parents[1] / "tools"
for entry in (str(PAPER_TOOLS), str(TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from compact_study import build_compact_problem, run_compact_greedy  # noqa: E402
from development_eval import (  # noqa: E402
    apply_gate,
    choose_reference,
    classify_case,
    deterministic_action,
    paired_summary,
    planned_cases,
    protocol_timeout_conflict,
    uniform_actions,
)
from environment import RuleSelectionEnv  # noqa: E402
from model import build_actor  # noqa: E402
from train_loop import load_actor, logits_of, save_checkpoint  # noqa: E402


def _orders() -> list[dict]:
    rows = []
    for index in range(40):
        target = "euro-pallet" if index < 20 else "rollcontainer"
        rows.append({"order_id": f"{index:08d}", "target": target, "n_items": 10 + index})
    return rows


def _scored(arm: str, label: str, order_id: str, target: str, value: float) -> dict:
    return {
        "key": f"{arm}|{label}|{order_id}",
        "arm": arm,
        "label": label,
        "order_id": order_id,
        "target": target,
        "effective_u_geom": value,
        "scored": True,
    }


class DevelopmentPlanTests(unittest.TestCase):
    def test_exactly_360_unique_keys(self) -> None:
        manifest = json.loads((STUDY / "development_manifest.json").read_text(encoding="utf-8"))
        orders = [row for rows in manifest["selected"].values() for row in rows]
        cases = planned_cases(orders)
        self.assertEqual(len(cases), 360)
        self.assertEqual(len({row["key"] for row in cases}), 360)
        self.assertEqual(sum(1 for row in cases if row["arm"] == "fixed"), 120)
        self.assertEqual(sum(1 for row in cases if row["arm"] == "uniform"), 120)
        self.assertEqual(sum(1 for row in cases if row["arm"] == "ppo"), 120)
        train = json.loads((STUDY / "train_manifest.json").read_text(encoding="utf-8"))
        train_ids = {row["order_id"] for rows in train["selected"].values() for row in rows}
        self.assertFalse({row["order_id"] for row in cases} & train_ids)

    def test_uniform_draws_cover_three_actions_and_repeat(self) -> None:
        first = uniform_actions(101, "00000001", 3000)
        second = uniform_actions(101, "00000001", 3000)
        self.assertEqual(first, second)
        self.assertEqual(set(first), {0, 1, 2})
        for action in (0, 1, 2):
            self.assertGreater(first.count(action), 800)

    def test_deterministic_tie_keeps_the_smaller_index(self) -> None:
        self.assertEqual(deterministic_action(torch.tensor([0.2, 0.2, 0.1])), 0)
        self.assertEqual(deterministic_action(torch.tensor([0.1, 0.5, 0.5])), 1)
        self.assertEqual(deterministic_action(torch.tensor([0.0, 0.0, 0.4])), 2)

    def test_checkpoint_load_reproduces_one_transform(self) -> None:
        actor = build_actor()
        critic = build_actor()
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "actor.pt"
            save_checkpoint(path, actor, critic, torch.optim.Adam(actor.parameters(), lr=1e-4), {"updates": 0})
            loaded = load_actor(path)
            observation = [0.1] * 36
            self.assertEqual(logits_of(loaded, observation), logits_of(actor, observation))
            first = deterministic_action(torch.tensor(logits_of(loaded, observation)))
            second = deterministic_action(torch.tensor(logits_of(loaded, observation)))
            self.assertEqual(first, second)
            self.assertEqual(first, 0)

    def test_fixed_rule_matches_compact_greedy_and_capture_stops(self) -> None:
        order_id = "00000001"
        orders = {
            order_id: {
                "properties": {"target": "euro-pallet"},
                "item_sequence": {
                    "1": {"sequence": 1, "id": "box", "length/mm": 100, "width/mm": 100, "height/mm": 100, "weight/kg": 1}
                },
            }
        }
        problem = build_compact_problem(orders, order_id)
        env = RuleSelectionEnv()
        observation, info = env.reset(problem)
        while not info["terminated"]:
            observation, _reward, _terminated, info = env.step(0)
        capture = env.capture(
            order_id=order_id,
            orders_path=Path("orders.json"),
            orders_sha256="0" * 64,
        )
        greedy, _info = run_compact_greedy(problem)
        self.assertEqual(len(capture["placements"]), len(greedy.packed_items))
        self.assertEqual(len(capture["placements"][0]["oriented_lwh_mm"]), 3)
        self.assertIsNone(capture["physical_stability_verified"])

    def test_failures_and_pending_stay_distinct(self) -> None:
        pending = classify_case(status="timeout", raw_u_geom=0.4, geometry_valid=True, contrast_matches=True)
        method = classify_case(status="method_failure", raw_u_geom=None, geometry_valid=False, contrast_matches=False)
        evaluator = classify_case(status="evaluator_error", raw_u_geom=0.2, geometry_valid=True, contrast_matches=True)
        self.assertTrue(pending["pending"])
        self.assertIsNone(pending["effective_u_geom"])
        self.assertFalse(pending["scored"])
        self.assertTrue(pending["in_denominator"])
        self.assertEqual(method["effective_u_geom"], 0.0)
        self.assertTrue(method["method_failure"])
        self.assertTrue(evaluator["evaluator_error"])
        self.assertIsNone(evaluator["effective_u_geom"])
        self.assertFalse(evaluator["method_failure"])

    def test_reference_and_paired_means(self) -> None:
        orders = _orders()
        rows = []
        values = {"greedy_best_fit": 0.20, "lowest_top": 0.30, "least_height_increase": 0.30}
        for order in orders:
            for rule, value in values.items():
                rows.append(_scored("fixed", rule, order["order_id"], order["target"], value))
            for seed, bonus in ((101, 0.01), (102, -0.02), (103, 0.02)):
                rows.append(_scored("uniform", str(seed), order["order_id"], order["target"], 0.10))
                rows.append(_scored("ppo", str(seed), order["order_id"], order["target"], 0.30 + bonus))
        self.assertEqual(choose_reference({"greedy_best_fit": 0.3, "lowest_top": 0.3, "least_height_increase": 0.2}), "greedy_best_fit")
        # El empate 0.30 entre lowest y height no está en esta tabla: lowest gana por índice.
        self.assertEqual(choose_reference(values), "lowest_top")
        summary = paired_summary(rows)
        self.assertEqual(summary["reference_rule"], "lowest_top")
        self.assertAlmostEqual(summary["per_seed"][0]["mean_rl_minus_reference"], 0.01)
        self.assertEqual(summary["per_seed"][0]["outcomes_versus_reference"]["victoria"], 40)
        gate = apply_gate(summary, integrity_passed=True, evaluation_complete=True)
        self.assertIn("media_rl_menos_mejor_fija", gate["conditions"])
        self.assertIsNone(protocol_timeout_conflict({"budget": {"global_wall_seconds": 14400}}))
        self.assertIsNotNone(protocol_timeout_conflict({"development_global_timeout_seconds": 10}))


if __name__ == "__main__":
    unittest.main()
