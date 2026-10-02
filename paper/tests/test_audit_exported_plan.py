"""Contrato geométrico del auditor 0/1. No usa el pedido real."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load_auditor():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_exported_plan.py"
    spec = importlib.util.spec_from_file_location("audit_exported_plan", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load_auditor()
BIN = (100.0, 100.0, 100.0)


def _action(item_id, length, width, height, orientation, flb):
    return {
        "item": {
            "id": item_id,
            "length": length,
            "width": width,
            "height": height,
            "weight": 1.0,
        },
        "orientation": orientation,
        "flb_coordinates": list(flb),
    }


class AuditExportedPlanTests(unittest.TestCase):
    def test_face_contact_is_not_overlap(self):
        actions = [
            _action("a", 10, 10, 10, 0, (0, 0, 0)),
            _action("b", 10, 10, 10, 0, (10, 0, 0)),
        ]
        result = audit.audit_actions(actions, BIN)
        self.assertEqual(result["n_overlap_pairs"], 0)
        self.assertTrue(result["exported_plan_geometry_valid"])
        self.assertIsNone(result["internal_solution_valid"])

    def test_positive_intersection_is_overlap(self):
        actions = [
            _action("a", 10, 10, 10, 0, (0, 0, 0)),
            _action("b", 10, 10, 10, 0, (5, 0, 0)),
        ]
        result = audit.audit_actions(actions, BIN)
        self.assertEqual(result["n_overlap_pairs"], 1)
        self.assertFalse(result["exported_plan_geometry_valid"])
        pair = result["pairs"][0]
        self.assertGreater(pair["intersection_mm"]["x"], audit.TOLERANCE_MM)
        self.assertTrue(pair["overlap"])

    def test_inside_and_outside_bin(self):
        actions = [
            _action("inside", 10, 10, 10, 0, (0, 0, 0)),
            _action("outside", 20, 10, 10, 0, (90, 0, 0)),
        ]
        result = audit.audit_actions(actions, BIN)
        by_id = {box["id"]: box for box in result["boxes"]}
        self.assertFalse(by_id["inside"]["outside_bin"])
        self.assertTrue(by_id["outside"]["outside_bin"])
        self.assertTrue(by_id["outside"]["upper_excess"]["x"])
        self.assertEqual(result["n_boxes_outside_bin"], 1)
        self.assertFalse(result["exported_plan_geometry_valid"])

    def test_yaw_swaps_length_and_width_only(self):
        actions = [_action("yaw", 30, 10, 5, 1, (0, 0, 0))]
        result = audit.audit_actions(actions, BIN)
        box = result["boxes"][0]
        self.assertEqual(box["oriented_lwh_mm"], [10.0, 30.0, 5.0])
        self.assertEqual(box["max_corner_mm"], [10.0, 30.0, 5.0])
        self.assertEqual(result["max_height_mm"], 5.0)
        self.assertTrue(result["exported_plan_geometry_valid"])

    def test_duplicate_id(self):
        actions = [
            _action("same", 10, 10, 10, 0, (0, 0, 0)),
            _action("same", 10, 10, 10, 0, (20, 0, 0)),
        ]
        result = audit.audit_actions(actions, BIN)
        self.assertEqual(result["duplicate_ids"], ["same"])
        self.assertFalse(result["exported_plan_geometry_valid"])

    def test_orientation_other_than_zero_or_one_is_rejected(self):
        actions = [_action("bad", 10, 10, 10, 2, (0, 0, 0))]
        result = audit.audit_actions(actions, BIN)
        self.assertEqual(result["n_boxes_parsed"], 0)
        self.assertEqual(len(result["parse_errors"]), 1)
        self.assertIn("0/1", result["parse_errors"][0]["error"])
        self.assertFalse(result["exported_plan_geometry_valid"])
        self.assertIsNone(result["internal_solution_valid"])

    def test_non_finite_bin_is_rejected(self):
        action = [_action("a", 10, 10, 10, 0, (0, 0, 0))]
        with self.assertRaises(ValueError):
            audit.audit_actions(action, (float("nan"), 100.0, 100.0))
        with self.assertRaises(ValueError):
            audit.audit_actions(action, (float("inf"), 100.0, 100.0))


if __name__ == "__main__":
    unittest.main()
