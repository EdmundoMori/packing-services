"""Lectura sintética del esquema de transiciones BC y de sus cruces."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load("audit_bc_transition_ids")


def _payload():
    return {
        "feature_version": 1,
        "feature_dim": 35,
        "teacher": "receding_horizon_ep",
        "seed": 42,
        "order_ids": ["00100", "00012"],
        "n_transitions": 3,
        "label_rate": 1.0,
        "regime": {"lookahead_p": 1, "select_s": 1},
        "transitions": [
            {"order_id": "00100", "step": 0, "features": [[1.25, 9.5], [0.0, 4.0]], "label": 0, "n_options": 2},
            {"order_id": "00100", "step": 1, "features": [[3.5, 8.0]], "label": 0, "n_options": 1},
            {"order_id": "00012", "step": 0, "features": [[7.75, 6.0]], "label": 0, "n_options": 1},
        ],
        "per_order": [
            {"order_id": "00100", "n_transitions": 2},
            {"order_id": "00012", "n_transitions": 1},
        ],
    }


class SchemaTests(unittest.TestCase):
    def test_summary_keeps_ids_and_drops_feature_values(self):
        summary = audit.summarize_payload(_payload())
        self.assertEqual(summary["order_ids"], ["00100", "00012"])
        self.assertEqual(summary["n_transition_rows"], 3)
        self.assertEqual(summary["transition_order_ids"], ["00100", "00100", "00012"])
        self.assertEqual(summary["duplicate_order_ids"], [])
        self.assertTrue(summary["coherence"]["declared_set_equals_transition_set"])
        self.assertTrue(summary["schema_usable"])
        self.assertEqual(summary["first_transition_feature_shape"], {"n_rows": 2, "width": 2})
        blob = json.dumps(summary)
        self.assertNotIn("1.25", blob)
        self.assertNotIn("9.5", blob)
        self.assertNotIn("7.75", blob)

    def test_declared_list_does_not_cover_a_missing_row_id(self):
        payload = _payload()
        payload["transitions"][2]["order_id"] = "00099"
        payload["order_ids"] = ["00100"]
        summary = audit.summarize_payload(payload)
        self.assertFalse(summary["coherence"]["declared_set_equals_transition_set"])
        self.assertIn("00099", summary["coherence"]["transition_not_declared"])
        self.assertFalse(audit.absence_is_established({"read_ok": True, **summary}))
        self.assertIn("00099", audit.positive_ids({"read_ok": True, **summary}))

    def test_duplicates_are_listed(self):
        payload = _payload()
        payload["order_ids"] = ["00100", "00100", "00012"]
        summary = audit.summarize_payload(payload)
        self.assertEqual(summary["duplicate_order_ids"], ["00100"])

    def test_failed_read_is_not_absence(self):
        self.assertIsNone(audit.positive_ids({"read_ok": False, "error": "timeout"}))
        cross = audit.cross_with_full_test(None, {"euro-pallet": ["00100"]}, absence_established=False)
        self.assertFalse(cross["absence_established"])
        self.assertIsNone(cross["by_target"]["euro-pallet"]["ids"])

    def test_full_test_hit_is_excluded_and_archived_cross_remains(self):
        classified = {
            "euro-pallet": {
                "n": 3,
                "registered_training": {"ids": []},
                "registered_selection": {"ids": []},
                "historical_evaluation": {"ids": []},
                "archived_uncertain_cross": {"ids": ["00012"]},
                "missing_evidence": {"ids": ["00100", "00012", "00008"]},
            },
            "rollcontainer": {
                "n": 1,
                "registered_training": {"ids": []},
                "registered_selection": {"ids": []},
                "historical_evaluation": {"ids": ["00007"]},
                "archived_uncertain_cross": {"ids": []},
                "missing_evidence": {"ids": ["00007"]},
            },
        }
        result = audit.overlay_exposure(
            classified,
            {"00100"},
            absence_established=True,
            historical_identity="no_comprobada",
        )
        euro = result["by_target"]["euro-pallet"]
        self.assertEqual(euro["current_bc_transition_cross"]["ids"], ["00100"])
        self.assertEqual(euro["absent_from_inspected_sources"]["ids"], ["00008"])
        self.assertIn("00012", euro["positive_exclusion"]["ids"])
        self.assertNotIn("00012", euro["absent_from_inspected_sources"]["ids"])
        self.assertFalse(result["absolute_independence"])
        self.assertEqual(result["historical_file_identity"], "no_comprobada")
        self.assertEqual(result["by_target"]["rollcontainer"]["positive_exclusion"]["ids"], ["00007"])
        self.assertFalse(result["future_evaluation_limited_to_euro_pallet"])

    def test_per_order_request_id_uses_the_manifest_prefix(self):
        self.assertTrue(audit.request_ids_match_manifest_prefix(["00100"], ["bed-bpp-00100"]))
        self.assertFalse(audit.request_ids_match_manifest_prefix(["00100"], ["00100"]))

    def test_disallowed_archive_path_is_refused(self):
        path = Path("/tmp/online_policy_ml/versions/v1/data/train/transitions_p1s1.pkl")
        self.assertFalse(audit.is_allowed_transition_path(path))


if __name__ == "__main__":
    unittest.main()
