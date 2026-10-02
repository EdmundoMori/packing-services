"""Clasificación sintética de candidatos por target."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import torch


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


exposure = _load("audit_candidate_exposure")


class ExposureTests(unittest.TestCase):
    def _classify(self):
        return exposure.classify_by_target(
            ["00100", "00012", "00007", "00008", "00009"],
            {
                "00100": "euro-pallet",
                "00012": "euro-pallet",
                "00007": "rollcontainer",
                "00008": "rollcontainer",
                "00009": "euro-pallet",
            },
            {"bc_working_train_manifest": ["00100"], "ppo_scale_train_manifest": ["00003"]},
            {"bc_working_val_manifest": ["00012"], "ppo_scale_val_manifest": ["00004"]},
            {"report_eval": ["00007"], "pilot_manifest": ["00012"]},
            {"v1_scale_train_manifest": ["00008", "00100"], "v1_missing": None},
        )

    def test_overlapping_categories_stay_separate_for_both_targets(self):
        result = self._classify()
        euro = result["by_target"]["euro-pallet"]
        roll = result["by_target"]["rollcontainer"]
        self.assertEqual(euro["registered_training"]["ids"], ["00100"])
        self.assertEqual(euro["registered_selection"]["ids"], ["00012"])
        self.assertEqual(euro["historical_evaluation"]["ids"], ["00012"])
        self.assertEqual(euro["archived_uncertain_cross"]["ids"], ["00100"])
        self.assertIn("00100", euro["registered_training"]["ids"])
        self.assertIn("00100", euro["archived_uncertain_cross"]["ids"])
        self.assertEqual(roll["historical_evaluation"]["ids"], ["00007"])
        self.assertEqual(roll["archived_uncertain_cross"]["ids"], ["00008"])
        self.assertEqual(roll["registered_training"]["ids"], [])
        self.assertEqual(result["counts"]["rollcontainer"]["n"], 2)
        self.assertFalse(result["future_evaluation_limited_to_euro_pallet"])
        self.assertFalse(result["called_clean"])
        self.assertFalse(result["called_contaminated"])
        self.assertIsNone(result["n_not_selected"])

    def test_absence_of_a_cross_stays_missing_evidence(self):
        result = self._classify()
        euro = result["by_target"]["euro-pallet"]
        self.assertEqual(euro["missing_evidence"]["without_registered_cross_ids"], ["00009"])
        self.assertEqual(euro["missing_evidence"]["n"], 3)
        self.assertTrue(euro["missing_evidence"]["applies_to_all_candidates"])
        self.assertIn("00009", euro["missing_evidence"]["ids"])
        self.assertNotIn("limpio", json.dumps(result["note"]))
        self.assertNotIn("contaminado", json.dumps(result["note"]))

    def test_selection_is_not_relabelled_as_training(self):
        result = self._classify()
        euro = result["by_target"]["euro-pallet"]
        self.assertIn("00012", euro["registered_selection"]["ids"])
        self.assertNotIn("00012", euro["registered_training"]["ids"])
        self.assertIn("v1_missing", euro["archived_uncertain_cross"]["sources_missing"])

    def test_missing_full_test_is_not_an_empty_reserve(self):
        result = exposure.classify_by_target(None, {}, {}, {}, {}, {})
        self.assertEqual(result["evidence"], "faltante")
        self.assertIsNone(result["full_test_n"])
        self.assertFalse(result["called_clean"])
        self.assertFalse(result["future_evaluation_limited_to_euro_pallet"])

    def test_exact_weight_comparison_distinguishes_equal_and_distinct(self):
        left = {
            "0.weight": torch.tensor([[1.0, 2.0]]),
            "0.bias": torch.tensor([0.5]),
        }
        same = {key: value.clone() for key, value in left.items()}
        other = {
            "0.weight": torch.tensor([[1.0, 9.0]]),
            "0.bias": torch.tensor([0.5]),
        }
        equal = exposure.compare_state_dicts(left, same)
        distinct = exposure.compare_state_dicts(left, other)
        missing = exposure.compare_state_dicts(left, None)
        self.assertEqual(equal["weights"], "equal")
        self.assertTrue(all(row["values_equal"] for row in equal["tensors"]))
        self.assertEqual(distinct["weights"], "distinct")
        self.assertEqual(missing["weights"], "not_checkable")
        blob = json.dumps(equal)
        self.assertNotIn("1.0", blob)
        self.assertNotIn("2.0", blob)


if __name__ == "__main__":
    unittest.main()
