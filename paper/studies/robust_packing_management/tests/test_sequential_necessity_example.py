"""Test: ejemplo enumerable de insuficiencia de una regla local de protección."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from sequential_necessity_example import (  # noqa: E402
    MG,
    M0,
    arrival_model_best,
    choose_flb,
    expected_JB,
    immediate_failure_prob,
    local_rule,
    run_check,
)


class TestSequentialNecessityExample(unittest.TestCase):
    def test_enumeration_under_60s_and_nontrivial_vs_local_rule(self):
        report = run_check(time_limit_s=60.0)
        self.assertTrue(report["within_60s"])
        self.assertLess(report["elapsed_s"], 60.0)
        self.assertTrue(report["checks"]["two_admissible_actions_different_layout"])
        self.assertTrue(report["checks"]["immediate_risk_known"])
        self.assertTrue(report["checks"]["future_consequences_differ"])
        self.assertTrue(report["checks"]["local_rule_insufficient_vs_arrival_oracle"])
        self.assertTrue(report["nontrivial_example_found"])
        # Óptimo del menú bajo supuesto de llegada = MG; regla local = M0
        self.assertEqual(local_rule(0.5), M0)
        self.assertEqual(arrival_model_best()[0], MG)
        self.assertGreater(expected_JB(MG), expected_JB(M0))
        # Riesgos inmediatos conocidos y distintos del “hay candidatas”
        self.assertEqual(immediate_failure_prob(M0, choose_flb(M0)), 0.5)
        self.assertEqual(immediate_failure_prob(MG, choose_flb(MG)), 0.0)
        # Política óptima del menú es determinista (no requiere RL)
        self.assertEqual(choose_flb(MG), (0.0, 0.0, 0.0))
        self.assertEqual(choose_flb(M0), (4.0, 0.0, 0.0))
        # Baselines analíticas fuertes empatan el óptimo; L solo falla por rho_star=0.5
        from sequential_necessity_example import compare_analytical_baselines

        cmp_ = compare_analytical_baselines()
        self.assertTrue(cmp_["meta"]["strong_baselines_agree_on_MG"])
        self.assertEqual(cmp_["prefer_guarantee_if_admissible"]["margin"], MG)
        self.assertEqual(cmp_["max_immediate_expected_utility"]["margin"], MG)
        self.assertTrue(cmp_["meta"]["chooser_is_synthetic_not_EP_engine"])
        self.assertEqual(report["baseline_comparison"]["meta"]["residual_of_strong_baselines_vs_menu_opt"], 0.0)


if __name__ == "__main__":
    unittest.main()
