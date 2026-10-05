"""Pruebas del evaluador de development (sin episodios reales ni test)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1] / "tools"
for entry in list(sys.path):
    if "counterfactual_ranking/tools" in entry:
        sys.path.remove(entry)
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from episode_analysis import (  # noqa: E402
    apply_development_gate,
    case_key,
    classify_episode,
    order_then_seed_aggregate,
    planned_cases,
    seed_report,
)
from model_spec import ARMS, TRAINING_CONFIG, build_actor  # noqa: E402
from training_loop import configure_training_runtime, save_checkpoint  # noqa: E402


class TestEpisodeAnalysis(unittest.TestCase):
    def test_planned_240_unique_no_test(self) -> None:
        orders = [
            {"order_id": f"{i:08d}", "split": "development", "target": "euro-pallet" if i < 12 else "rollcontainer"}
            for i in range(24)
        ]
        cases = planned_cases(orders)
        self.assertEqual(len(cases), 240)
        self.assertEqual(len({c["key"] for c in cases}), 240)
        self.assertEqual(sum(1 for c in cases if c["arm"] == "greedy"), 24)
        self.assertEqual(sum(1 for c in cases if c["arm"] != "greedy"), 216)
        self.assertFalse(any(c.get("split") == "test" for c in cases))

    def test_method_failure_keeps_denominator_zero(self) -> None:
        row = classify_episode(status="timeout", raw_u_geom=None, geometry_valid=False, contrast_matches=False)
        self.assertTrue(row["method_failure"])
        self.assertEqual(row["effective_u_geom"], 0.0)
        self.assertTrue(row["in_denominator"])

    def test_evaluator_error_incomplete(self) -> None:
        row = classify_episode(status="ok", raw_u_geom=0.5, geometry_valid=False, contrast_matches=True)
        self.assertTrue(row["evaluator_error"])
        self.assertFalse(row["in_denominator"])

    def test_gate_frozen_conditions(self) -> None:
        orders = [
            {"order_id": f"o{i}", "target": "euro-pallet" if i < 12 else "rollcontainer"} for i in range(24)
        ]
        # construct synthetic rows: preferences slightly above classification
        rows = []
        for order in orders:
            rows.append(
                {
                    "order_id": order["order_id"],
                    "target": order["target"],
                    "arm": "greedy",
                    "seed": None,
                    "effective_u_geom": 0.5,
                    "method_failure": False,
                    "in_denominator": True,
                }
            )
            for arm in ARMS:
                for seed in TRAINING_CONFIG["seeds"]:
                    base = 0.50 if arm == "classification" else 0.52 if arm == "preferences" else 0.51
                    rows.append(
                        {
                            "order_id": order["order_id"],
                            "target": order["target"],
                            "arm": arm,
                            "seed": seed,
                            "effective_u_geom": base,
                            "method_failure": False,
                            "in_denominator": True,
                        }
                    )
        reports = [seed_report(rows, orders, seed) for seed in (11, 23, 37)]
        agg = order_then_seed_aggregate(reports, orders)
        gate = apply_development_gate(
            reports,
            agg,
            evaluator_errors=0,
            missing_keys=0,
            remaining_seconds_for_test=10000,
        )
        self.assertTrue(gate["conditions"]["mean_pref_minus_class_ge_0_005"])
        self.assertTrue(gate["conditions"]["positive_mean_in_at_least_two_seeds"])
        self.assertTrue(gate["conditions"]["aggregate_nonnegative_per_target"])
        self.assertTrue(gate["conditions"]["complete_audited_evaluation"])
        self.assertTrue(gate["conditions"]["remaining_budget_for_test"])
        self.assertTrue(gate["passed"])
        # secondary arm cannot change: return_difference better doesn't appear in gate conditions
        self.assertTrue(gate["secondary_arm_does_not_rescue_gate"])

    def test_gate_fails_incomplete(self) -> None:
        gate = apply_development_gate(
            [],
            {
                "preferences_minus_classification": {
                    "mean": 0.01,
                    "by_target": {"euro-pallet": {"mean": 0.01}, "rollcontainer": {"mean": 0.01}},
                }
            },
            evaluator_errors=1,
            missing_keys=0,
            remaining_seconds_for_test=10000,
        )
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["decision"], "no_avanzar_con_esta_configuracion")


class TestCheckpointIdentity(unittest.TestCase):
    def test_save_and_reload_logits(self) -> None:
        configure_training_runtime()
        import torch
        from training_loop import load_checkpoint_logits

        model = build_actor(11)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ckpt.pt"
            save_checkpoint(path, model, meta={"seed": 11, "arm": "classification", "epoch": 40, "n_optimizer_steps": 40})
            feats = torch.randn(3, 17)
            a = load_checkpoint_logits(path, feats)
            b = load_checkpoint_logits(path, feats)
            self.assertEqual(a, b)


class TestSupportPolicyUsesS(unittest.TestCase):
    def test_selects_within_support_not_full_list(self) -> None:
        # Unit-level: labeling_select_support + select_logit_index path
        from candidate_support import select_logit_index
        from pipeline import labeling_select_support

        class Opt:
            def __init__(self, i: int) -> None:
                self.i = i

        options = [Opt(i) for i in range(6)]
        greedy = options[0]

        with mock.patch("pipeline.SUPPORT_BUILDER_FROM_OPTIONS", side_effect=lambda opts, g, limit=4: list(opts)[:limit]):
            support = labeling_select_support(options, greedy, limit=4)
        self.assertEqual(len(support), 4)
        logits = [0.1, 0.9, 0.2, 0.3]
        self.assertEqual(select_logit_index(logits), 1)
        # chosen must be support[1], not options[1] necessarily same object here
        self.assertIs(support[select_logit_index(logits)], support[1])


if __name__ == "__main__":
    unittest.main()
