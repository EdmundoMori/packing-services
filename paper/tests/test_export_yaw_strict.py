"""Contrato del adaptador yaw estricto. No usa el pedido real."""

from __future__ import annotations

import importlib.util
import itertools
import json
import tempfile
import unittest
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


yaw = _load("export_yaw_strict")
exported = _load("audit_exported_plan")


def _doc(original, oriented, flb=(0, 0, 0), item_id="box"):
    return {
        "order_id": "synthetic",
        "recipe": {"constraints": {"allow_rotation": True}},
        "containers": [{"id": "BIN", "length_mm": 100, "width_mm": 100, "height_mm": 100}],
        "input_items": [
            {
                "item_id": item_id,
                "length_mm": original[0],
                "width_mm": original[1],
                "height_mm": original[2],
                "allowed_orientations": "all",
            }
        ],
        "placements": [
            {
                "item_id": item_id,
                "container_id": "BIN",
                "flb_mm": list(flb),
                "original_lwh_mm": list(original),
                "oriented_lwh_mm": list(oriented),
                "weight_kg": 1.0,
            }
        ],
        "unpacked": [],
    }


class ExportYawStrictTests(unittest.TestCase):
    def test_six_distinct_permutations_two_representable(self):
        original = (30, 20, 10)
        representable = 0
        rejected = 0
        for perm in set(itertools.permutations(original)):
            report = yaw.assess_yaw_export(_doc(original, perm))
            if report["yaw_exportable"]:
                representable += 1
                self.assertIsNotNone(report["plan"])
            else:
                rejected += 1
                self.assertIsNone(report["plan"])
                self.assertEqual(report["incompatible_item_ids"], ["box"])
        self.assertEqual(representable, 2)
        self.assertEqual(rejected, 4)

    def test_repeated_dimensions_choose_zero_and_keep_geometry(self):
        report = yaw.assess_yaw_export(_doc((8, 8, 3), (8, 8, 3), (4, 5, 6)))
        self.assertTrue(report["yaw_exportable"])
        action = report["plan"]["synthetic"][0]
        self.assertEqual(action["orientation"], 0)
        self.assertEqual(action["item"]["length"], 8)
        self.assertEqual(action["item"]["width"], 8)
        self.assertEqual(action["item"]["height"], 3)
        self.assertEqual(action["flb_coordinates"], [4, 5, 6])

    def test_round_trip_preserves_placed_dimensions_and_position(self):
        report = yaw.assess_yaw_export(_doc((30, 10, 5), (10, 30, 5), (1, 2, 3)))
        self.assertEqual(report["plan"]["synthetic"][0]["orientation"], 1)
        rebuilt = exported.audit_actions(report["plan"]["synthetic"], (100, 100, 100))
        box = rebuilt["boxes"][0]
        self.assertEqual(box["oriented_lwh_mm"], [10.0, 30.0, 5.0])
        self.assertEqual(box["flb_mm"], [1.0, 2.0, 3.0])
        self.assertTrue(rebuilt["exported_plan_geometry_valid"])

    def test_invalid_geometry_is_not_exportable(self):
        document = _doc((10, 10, 10), (10, 10, 10))
        document["placements"].append(
            {
                "item_id": "other",
                "container_id": "BIN",
                "flb_mm": [0, 0, 0],
                "original_lwh_mm": [10, 10, 10],
                "oriented_lwh_mm": [10, 10, 10],
                "weight_kg": 1,
            }
        )
        document["input_items"].append(
            {
                "item_id": "other",
                "length_mm": 10,
                "width_mm": 10,
                "height_mm": 10,
                "allowed_orientations": "all",
            }
        )
        report = yaw.assess_yaw_export(document)
        self.assertFalse(report["internal_geometry_valid"])
        self.assertFalse(report["yaw_exportable"])
        self.assertIsNone(report["plan"])

    def test_failed_conversion_does_not_overwrite_an_existing_plan(self):
        document = _doc((30, 20, 10), (10, 20, 30))
        with tempfile.TemporaryDirectory() as folder:
            plan_path = Path(folder) / "plan.json"
            plan_path.write_text('{"sentinel": true}\n', encoding="utf-8")
            report_path = Path(folder) / "report.json"
            code = yaw.emit(document, report_path=report_path, plan_path=plan_path)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(plan_path.read_text()), {"sentinel": True})
            missing = Path(folder) / "missing.json"
            code_missing = yaw.emit(document, plan_path=missing)
            self.assertEqual(code_missing, 1)
            self.assertFalse(missing.exists())
            written = json.loads(report_path.read_text())
            self.assertNotIn("plan", written)
            self.assertGreater(written["n_incompatible_orientations"], 0)

    def test_same_resolved_path_does_not_change_an_existing_file(self):
        document = _doc((30, 20, 10), (30, 20, 10))
        with tempfile.TemporaryDirectory() as folder:
            shared = Path(folder) / "shared.json"
            original = '{"keep": "intact", "n": 7}\n'
            shared.write_text(original, encoding="utf-8")
            alias = Path(folder) / "alias.json"
            alias.symlink_to(shared)
            code = yaw.emit(document, report_path=shared, plan_path=alias)
            self.assertEqual(code, 2)
            self.assertEqual(shared.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
