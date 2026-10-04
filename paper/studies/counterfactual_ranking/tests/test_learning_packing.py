"""Pruebas sintéticas de los episodios. No usan los doce pedidos reales."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import torch
from torch import nn

STUDY = Path(__file__).resolve().parents[1]
TOOLS = STUDY / "tools"
PAPER_TOOLS = STUDY.parents[1] / "tools"
for entry in (str(PAPER_TOOLS), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from actor_features import FEATURE_NAMES, encode_candidate  # noqa: E402
from actor_policy import ActorPolicy  # noqa: E402
from campaign import directory_must_be_new, recompute_u  # noqa: E402
from compact_study import TERMINAL_REASON, SUFFIX_REASON, build_compact_problem  # noqa: E402
from diagnostic import _legal_options, _setup  # noqa: E402
from learning_worker import run_problem  # noqa: E402
from model_spec import build_actor  # noqa: E402
from objectives import apply_normalization  # noqa: E402
from packing_analysis import (  # noqa: E402
    CLASS_AHEAD,
    CLASS_INCONCLUSIVE,
    CLASS_STOP,
    apply_gate,
    classify_episode,
    planned_cases,
    seed_report,
)
from pilot_metrics import contrast_capture  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from run_learning_packing import _audit  # noqa: E402


def _order(order_id: str, items: list[tuple[str, int, int, int]]) -> dict:
    sequence = {}
    for index, (name, length, width, height) in enumerate(items, start=1):
        sequence[str(index)] = {
            "sequence": index,
            "id": name,
            "length/mm": length,
            "width/mm": width,
            "height/mm": height,
            "weight/kg": 1,
        }
    return {order_id: {"properties": {"target": "euro-pallet"}, "item_sequence": sequence}}


def _identity_stats() -> dict[str, list[float]]:
    return {"mean": [0.0] * 17, "scale": [1.0] * 17}


class _Store(nn.Module):
    def __init__(self, column: int) -> None:
        super().__init__()
        self.column = column
        self.seen: torch.Tensor | None = None

    def forward(self, rows: torch.Tensor) -> torch.Tensor:
        self.seen = rows.detach().clone()
        return rows[:, self.column : self.column + 1]


class LearningPackingTests(unittest.TestCase):
    def test_actor_scores_more_than_four_candidates(self) -> None:
        problem = build_compact_problem(_order("A", [("box", 30, 40, 50), ("next", 20, 20, 20)]), "A")
        session, mask, _policy, _budget, remaining = _setup(problem)
        options = _legal_options(session, remaining[0], problem.constraints, mask)
        self.assertGreater(len(options), 4)
        model = _Store(FEATURE_NAMES.index("pos_x_n"))
        policy = ActorPolicy(model, _identity_stats())
        chosen = policy.decide(
            options,
            preview=remaining,
            remaining_count=99,
            session=session,
            constraints=problem.constraints,
            mask=mask,
        )
        raw = [encode_candidate(session, remaining[0], option.candidate) for option in options]
        expected = max(range(len(raw)), key=lambda index: (raw[index][FEATURE_NAMES.index("pos_x_n")], -index))
        self.assertIs(chosen, options[expected])
        self.assertGreater(policy.max_candidates, 4)
        self.assertEqual(policy.normalization_calls, len(options))

    def test_normalization_is_applied_once(self) -> None:
        problem = build_compact_problem(_order("N", [("box", 30, 40, 50)]), "N")
        session, mask, _policy, _budget, remaining = _setup(problem)
        options = _legal_options(session, remaining[0], problem.constraints, mask)
        stats = {"mean": [1.0] * 17, "scale": [2.0] * 17}
        model = _Store(0)
        policy = ActorPolicy(model, stats)
        policy.decide(options, preview=(), remaining_count=0, session=session, constraints=None, mask=None)
        raw = encode_candidate(session, remaining[0], options[0].candidate)
        once = apply_normalization(raw, stats)
        twice = apply_normalization(once, stats)
        seen = model.seen[0].tolist()
        self.assertTrue(all(abs(left - right) < 1e-5 for left, right in zip(seen, once)))
        self.assertFalse(all(abs(left - right) < 1e-5 for left, right in zip(seen, twice)))

    def test_input_ignores_the_hidden_future(self) -> None:
        early = _order("A", [("box", 30, 40, 50), ("next", 20, 20, 20)])
        late = _order("B", [("box", 30, 40, 50), ("next", 90, 80, 70)])
        left = build_compact_problem(early, "A")
        right = build_compact_problem(late, "B")
        session_a, mask_a, _a, _b, remaining_a = _setup(left)
        session_b, mask_b, _c, _d, remaining_b = _setup(right)
        options_a = _legal_options(session_a, remaining_a[0], left.constraints, mask_a)
        options_b = _legal_options(session_b, remaining_b[0], right.constraints, mask_b)
        model_a = _Store(0)
        model_b = _Store(0)
        ActorPolicy(model_a, _identity_stats()).decide(
            options_a, preview=remaining_a, remaining_count=4, session=session_a, constraints=None, mask=None
        )
        ActorPolicy(model_b, _identity_stats()).decide(
            options_b, preview=remaining_b, remaining_count=4, session=session_b, constraints=None, mask=None
        )
        self.assertEqual(model_a.seen.tolist(), model_b.seen.tolist())
        banned = {"q_hat", "order_id", "suffix", "greedy"}
        self.assertTrue(banned.isdisjoint(ActorPolicy.decide.__code__.co_names))

    def test_exact_logit_tie_uses_the_smallest_index(self) -> None:
        problem = build_compact_problem(_order("T", [("box", 30, 40, 50)]), "T")
        session, mask, _policy, _budget, remaining = _setup(problem)
        options = _legal_options(session, remaining[0], problem.constraints, mask)
        self.assertGreater(len(options), 1)
        policy = ActorPolicy(build_actor(11), _identity_stats())
        chosen = policy.decide(options, preview=(), remaining_count=0, session=session, constraints=None, mask=None)
        self.assertIs(chosen, options[0])

    def test_stop_keeps_the_suffix_unplaced(self) -> None:
        orders = _order("S", [("fit", 100, 100, 100), ("blocked", 2100, 2100, 2100), ("tail", 50, 50, 50)])
        problem = build_compact_problem(orders, "S")
        outcome = run_problem(
            problem,
            arm="greedy",
            order_id="S",
            dataset="synthetic",
            dataset_sha256="0" * 64,
            checkpoint_path=None,
            stats=None,
        )
        capture = outcome["capture"]
        placed = {row["item_id"] for row in capture["placements"]}
        self.assertEqual(placed, {"fit#1"})
        reasons = {row["item_id"]: row["reason"] for row in capture["unpacked"]}
        self.assertEqual(reasons["blocked#2"], TERMINAL_REASON)
        self.assertEqual(reasons["tail#3"], SUFFIX_REASON)
        self.assertIsNone(capture["physical_stability_verified"])

    def test_capture_oriented_dimensions_and_audit(self) -> None:
        problem = build_compact_problem(_order("R", [("box", 30, 40, 50), ("next", 30, 40, 50)]), "R")
        snapshot = problem_snapshot(problem)
        column = FEATURE_NAMES.index("ori_l_n")
        session, mask, _policy, _budget, remaining = _setup(problem)
        options = _legal_options(session, remaining[0], problem.constraints, mask)
        chosen = ActorPolicy(_Store(column), _identity_stats()).decide(
            options, preview=(), remaining_count=0, session=session, constraints=None, mask=None
        )
        self.assertNotAlmostEqual(chosen.candidate.dimensions.length, remaining[0].length)

        from compact_study import ALGORITHM_NAME, run_compact_episode
        from pilot_problems import capture_document

        solution, _diagnostics = run_compact_episode(
            problem,
            ActorPolicy(_Store(column), _identity_stats()),
            algorithm_name=ALGORITHM_NAME,
            display_name="sintetico",
            description="sintetico",
            selector="ActorPolicy",
        )
        capture = capture_document(
            problem,
            solution,
            method="classification",
            order_id="R",
            orders_path=Path("synthetic"),
            orders_sha256="0" * 64,
            checkpoint_path=Path("."),
        )
        capture["physical_stability_verified"] = None
        first = capture["placements"][0]
        self.assertEqual(first["oriented_lwh_mm"][0], chosen.candidate.dimensions.length)
        self.assertNotEqual(first["oriented_lwh_mm"], first["original_lwh_mm"])
        audit = _audit(capture)
        contrast = contrast_capture(capture, snapshot, order_id="R", method="classification")
        self.assertTrue(audit["internal_geometry_valid"])
        self.assertTrue(contrast["matches"], contrast["errors"])
        self.assertAlmostEqual(recompute_u(capture), audit["per_container"][0]["packed_volume_mm3"] / audit["per_container"][0]["bin_volume_mm3"])

    def test_method_failure_stays_in_the_denominator_and_geometry_does_not(self) -> None:
        failed = classify_episode(status="timeout", raw_u_geom=None, geometry_valid=False, contrast_matches=False)
        self.assertEqual(failed["effective_u_geom"], 0.0)
        self.assertTrue(failed["in_denominator"])
        self.assertFalse(failed["evaluator_error"])
        geometric = classify_episode(status="ok", raw_u_geom=0.2, geometry_valid=False, contrast_matches=True)
        self.assertIsNone(geometric["effective_u_geom"])
        self.assertTrue(geometric["evaluator_error"])
        self.assertFalse(geometric["in_denominator"])

    def test_planned_keys_are_eighty_four(self) -> None:
        protocol = json.loads((STUDY / "learning_protocol_frozen.json").read_text(encoding="utf-8"))
        orders = []
        for target in ("euro-pallet", "rollcontainer"):
            orders.extend(protocol["splits"][target]["development"])
        cases = planned_cases(orders)
        self.assertEqual(len(cases), 84)
        self.assertEqual(sum(1 for case in cases if case["arm"] == "greedy"), 12)
        self.assertEqual(sum(1 for case in cases if case["arm"] == "classification"), 36)
        self.assertEqual(sum(1 for case in cases if case["arm"] == "preferences"), 36)

    def test_paired_means_and_gate(self) -> None:
        orders = [{"order_id": f"{index:02d}", "target": "euro-pallet" if index < 6 else "rollcontainer"} for index in range(12)]

        def row(order: dict, arm: str, seed: int | None, value: float) -> dict:
            return {
                "order_id": order["order_id"],
                "target": order["target"],
                "arm": arm,
                "seed": seed,
                "effective_u_geom": value,
                "method_failure": False,
                "in_denominator": True,
            }

        rows = []
        for order in orders:
            base = 0.20 if order["target"] == "euro-pallet" else 0.10
            rows.append(row(order, "greedy", None, base))
            for seed in (11, 23, 37):
                rows.append(row(order, "classification", seed, base + 0.01))
                rows.append(row(order, "preferences", seed, base + 0.03))
        reports = [seed_report(rows, orders, seed) for seed in (11, 23, 37)]
        self.assertAlmostEqual(reports[0]["preferences_minus_classification"]["mean"], 0.02)
        self.assertAlmostEqual(reports[0]["preferences_minus_greedy"]["mean"], 0.03)
        self.assertEqual(reports[0]["preferences_minus_classification"]["n_orders"], 12)
        gate = apply_gate(reports, evaluator_errors=0, missing_keys=0)
        self.assertEqual(gate["classification"], CLASS_AHEAD)
        short = []
        for order in orders:
            base = 0.20
            short.append(row(order, "greedy", None, base))
            for seed in (11, 23, 37):
                short.append(row(order, "classification", seed, base))
                short.append(row(order, "preferences", seed, base))
        stopped = apply_gate([seed_report(short, orders, seed) for seed in (11, 23, 37)], evaluator_errors=0, missing_keys=0)
        self.assertEqual(stopped["classification"], CLASS_STOP)
        blocked = apply_gate([], evaluator_errors=1, missing_keys=0)
        self.assertEqual(blocked["classification"], CLASS_INCONCLUSIVE)
        self.assertFalse(blocked["authorizes_arm_substitution"])

    def test_existing_output_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "learning_packing"
            path.mkdir()
            with self.assertRaises(FileExistsError):
                directory_must_be_new(path)


if __name__ == "__main__":
    unittest.main()
