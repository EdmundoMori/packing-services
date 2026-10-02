"""Contrato del auditor interno. No usa el pedido real."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_internal_solution.py"
    spec = importlib.util.spec_from_file_location("audit_internal_solution", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit = _load()


def _doc(placements, unpacked=None, inputs=None, containers=None):
    if inputs is None:
        inputs = []
        seen = set()
        for placement in placements:
            if placement["item_id"] not in seen:
                inputs.append(
                    {
                        "item_id": placement["item_id"],
                        "length_mm": placement["original_lwh_mm"][0],
                        "width_mm": placement["original_lwh_mm"][1],
                        "height_mm": placement["original_lwh_mm"][2],
                        "allowed_orientations": "all",
                    }
                )
                seen.add(placement["item_id"])
        for row in unpacked or []:
            if row["item_id"] not in seen:
                inputs.append(
                    {
                        "item_id": row["item_id"],
                        "length_mm": 10,
                        "width_mm": 10,
                        "height_mm": 10,
                        "allowed_orientations": "all",
                    }
                )
    return {
        "recipe": {"constraints": {"allow_rotation": True}},
        "containers": containers
        or [{"id": "EURO_PALLET", "length_mm": 100, "width_mm": 100, "height_mm": 100}],
        "input_items": inputs,
        "placements": placements,
        "unpacked": unpacked or [],
    }


def _place(item_id, original, oriented, flb, container="EURO_PALLET"):
    return {
        "item_id": item_id,
        "container_id": container,
        "flb_mm": list(flb),
        "original_lwh_mm": list(original),
        "oriented_lwh_mm": list(oriented),
    }


class AuditInternalSolutionTests(unittest.TestCase):
    def test_height_changing_permutation_is_compatible(self):
        result = audit.audit_document(_doc([_place("a", (30, 10, 5), (5, 10, 30), (0, 0, 0))]))
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["per_container"][0]["max_height_mm"], 30)
        self.assertTrue(result["internal_geometry_valid"])
        self.assertTrue(result["all_items_packed"])
        self.assertIsNone(result["physical_stability_verified"])

    def test_valid_geometry(self):
        result = audit.audit_document(
            _doc(
                [
                    _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0)),
                    _place("b", (10, 10, 10), (10, 10, 10), (10, 0, 0)),
                ]
            )
        )
        self.assertTrue(result["internal_geometry_valid"])
        self.assertEqual(result["n_overlap_pairs"], 0)

    def test_overlap_same_container(self):
        result = audit.audit_document(
            _doc(
                [
                    _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0)),
                    _place("b", (10, 10, 10), (10, 10, 10), (5, 0, 0)),
                ]
            )
        )
        self.assertEqual(result["n_overlap_pairs"], 1)
        self.assertFalse(result["internal_geometry_valid"])

    def test_different_container_is_not_overlap(self):
        result = audit.audit_document(
            _doc(
                [
                    _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0), "A"),
                    _place("b", (10, 10, 10), (10, 10, 10), (0, 0, 0), "B"),
                ],
                containers=[
                    {"id": "A", "length_mm": 100, "width_mm": 100, "height_mm": 100},
                    {"id": "B", "length_mm": 100, "width_mm": 100, "height_mm": 100},
                ],
            )
        )
        self.assertEqual(result["n_overlap_pairs"], 0)
        self.assertTrue(result["internal_geometry_valid"])

    def test_unknown_and_duplicate_ids(self):
        unknown = audit.audit_document(_doc([_place("missing", (10, 10, 10), (10, 10, 10), (0, 0, 0))], inputs=[]))
        self.assertFalse(unknown["internal_geometry_valid"])
        self.assertTrue(any("desconocido" in error for error in unknown["errors"]))
        duplicate = audit.audit_document(
            _doc(
                [
                    _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0)),
                    _place("a", (10, 10, 10), (10, 10, 10), (20, 0, 0)),
                ]
            )
        )
        self.assertTrue(any("duplicados" in error for error in duplicate["errors"]))

    def test_incomplete_partition(self):
        result = audit.audit_document(
            _doc(
                [_place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0))],
                inputs=[
                    {"item_id": "a", "length_mm": 10, "width_mm": 10, "height_mm": 10, "allowed_orientations": "all"},
                    {"item_id": "b", "length_mm": 10, "width_mm": 10, "height_mm": 10, "allowed_orientations": "all"},
                ],
            )
        )
        self.assertTrue(any("partición" in error for error in result["errors"]))
        self.assertFalse(result["internal_geometry_valid"])

    def test_incompatible_orientation(self):
        result = audit.audit_document(_doc([_place("a", (10, 20, 30), (1, 1, 1), (0, 0, 0))]))
        self.assertTrue(any("incompatible" in error for error in result["errors"]))
        self.assertFalse(result["internal_geometry_valid"])

    def test_non_finite_values(self):
        placement = _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0))
        placement["flb_mm"][2] = float("nan")
        result = audit.audit_document(_doc([placement]))
        self.assertTrue(any("finitos" in error for error in result["errors"]))
        self.assertFalse(result["internal_geometry_valid"])

    def test_partial_solution_can_be_geometrically_valid(self):
        result = audit.audit_document(
            _doc(
                [_place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0))],
                unpacked=[{"item_id": "b", "reason": "no cabe"}],
            )
        )
        self.assertTrue(result["internal_geometry_valid"])
        self.assertFalse(result["all_items_packed"])
        self.assertIsNone(result["physical_stability_verified"])

    def test_original_dimensions_permuted_against_input_are_rejected(self):
        result = audit.audit_document(
            _doc(
                [_place("a", (5, 10, 30), (5, 10, 30), (0, 0, 0))],
                inputs=[
                    {
                        "item_id": "a",
                        "length_mm": 30,
                        "width_mm": 10,
                        "height_mm": 5,
                        "allowed_orientations": "all",
                    }
                ],
            )
        )
        self.assertTrue(any("eje a eje" in error for error in result["errors"]))
        self.assertFalse(result["internal_geometry_valid"])
        self.assertEqual(result["boxes"], [])
        self.assertEqual(result["per_container"][0]["n_boxes"], 0)
        self.assertEqual(result["per_container"][0]["packed_volume_mm3"], 0)

    def test_vectors_whose_lengths_sum_to_nine_do_not_crash(self):
        placement = _place("a", (10, 10, 10), (10, 10), (0, 0, 0, 0))
        result = audit.audit_document(_doc([placement]))
        self.assertFalse(result["internal_geometry_valid"])
        self.assertEqual(result["boxes"], [])

    def test_non_finite_or_non_positive_input_dimensions_are_rejected(self):
        placement = _place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0))
        nan_doc = _doc(
            [placement],
            inputs=[{"item_id": "a", "length_mm": float("nan"), "width_mm": 10, "height_mm": 10, "allowed_orientations": "all"}],
        )
        negative = _doc(
            [placement],
            inputs=[{"item_id": "a", "length_mm": -10, "width_mm": 10, "height_mm": 10, "allowed_orientations": "all"}],
        )
        self.assertFalse(audit.audit_document(nan_doc)["internal_geometry_valid"])
        self.assertFalse(audit.audit_document(negative)["internal_geometry_valid"])
        self.assertFalse(audit.audit_document(["no-es-objeto"])["internal_geometry_valid"])

    def test_duplicate_container_ids_are_rejected(self):
        result = audit.audit_document(
            _doc(
                [_place("a", (10, 10, 10), (10, 10, 10), (0, 0, 0), "A")],
                containers=[
                    {"id": "A", "length_mm": 100, "width_mm": 100, "height_mm": 100},
                    {"id": "A", "length_mm": 50, "width_mm": 50, "height_mm": 50},
                ],
            )
        )
        self.assertTrue(any("contenedor duplicados" in error for error in result["errors"]))
        self.assertFalse(result["internal_geometry_valid"])
        self.assertEqual(result["per_container"], [])

    def test_historical_contrast_is_ids_and_flb_only(self):
        document = _doc([_place("a", (10, 10, 10), (10, 10, 10), (1, 2, 3))])
        historical = [{"item": {"id": "a", "length": 99, "width": 1, "height": 1}, "orientation": 1, "flb_coordinates": [1, 2, 3]}]
        contrast = audit.contrast_historical(document, historical)
        self.assertTrue(contrast["same_ordered_ids_and_flb"])
        self.assertIn("No incluye dimensiones", contrast["comparison_scope"])
        self.assertFalse(
            audit.legacy_actions_equal(
                historical,
                [{"item": {"id": "a", "length": 10, "width": 10, "height": 10}, "orientation": 0, "flb_coordinates": [1, 2, 3]}],
            )
        )


if __name__ == "__main__":
    unittest.main()
