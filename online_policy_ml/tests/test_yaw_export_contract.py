"""C03 — contrato de exportación yaw 0/1 estricta (`packing_plan_actions`)."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "online_policy_ml" / "src_ml"))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "paper" / "tools"))

from packing_services.domain.enums import AlgorithmFamily, ProblemType, SolutionStatus  # noqa: E402
from packing_services.domain.models import (  # noqa: E402
    AlgorithmConfig,
    ConstraintFlags,
    Container,
    ExecutionMetadata,
    Item,
    Metrics,
    Orientation,
    PackedItem,
    PackingProblem,
    PackingSolution,
    Point3D,
    UnpackedItem,
)

import bedbpp_eval as ev  # noqa: E402
import capture_internal_solution as capture_mod  # noqa: E402

BIN = (200.0, 200.0, 200.0)
EPS = ev.YAW_EXPORT_TOLERANCE_MM


def _solution(
    items: list[tuple[str, float, float, float]],
    packed: list[tuple[str, float, float, float, float, float, float]],
    *,
    allow_rotation: bool = True,
) -> tuple[PackingProblem, PackingSolution]:
    problem = PackingProblem(
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        containers=[Container(id="c0", length=BIN[0], width=BIN[1], height=BIN[2])],
        items=[Item(id=i, length=l, width=w, height=h) for i, l, w, h in items],
        constraints=ConstraintFlags(allow_rotation=allow_rotation),
        algorithm=AlgorithmConfig(name="test"),
    )
    packed_items = [
        PackedItem(
            item_id=iid,
            container_id="c0",
            position=Point3D(x=x, y=y, z=z),
            orientation=Orientation(length=ol, width=ow, height=oh),
        )
        for iid, ol, ow, oh, x, y, z in packed
    ]
    solution = PackingSolution(
        status=SolutionStatus.SUCCESS,
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        algorithm_name="test",
        packed_items=packed_items,
        unpacked_items=[],
        metrics=Metrics(items_packed=len(packed_items), items_unpacked=0),
        execution_metadata=ExecutionMetadata(
            algorithm="test",
            algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
            service_version="test",
        ),
    )
    return problem, solution


class TestYawExportContractC03(unittest.TestCase):
    def test_original_orientation_representable(self):
        problem, solution = _solution([("a", 30, 20, 10)], [("a", 30, 20, 10, 1, 2, 3)])
        actions = ev.packing_plan_actions(problem, solution)
        self.assertEqual(actions[0]["orientation"], 0)
        self.assertEqual(actions[0]["flb_coordinates"], [1.0, 2.0, 3.0])

    def test_yaw_90_representable(self):
        problem, solution = _solution([("a", 30, 10, 5)], [("a", 10, 30, 5, 4, 5, 6)])
        actions = ev.packing_plan_actions(problem, solution)
        self.assertEqual(actions[0]["orientation"], 1)
        decoded = ev.decode_yaw01_oriented_lwh((30, 10, 5), 1)
        self.assertTrue(ev._yaw_axis_match(decoded, (10, 30, 5)))

    def test_original_length_less_than_width(self):
        # orientation=0 es (L,W,H) almacenado, no «lado mayor primero».
        problem, solution = _solution([("a", 10, 40, 5)], [("a", 10, 40, 5, 0, 0, 0)])
        actions = ev.packing_plan_actions(problem, solution)
        self.assertEqual(actions[0]["orientation"], 0)
        self.assertEqual(actions[0]["item"]["length"], 10)
        self.assertEqual(actions[0]["item"]["width"], 40)
        yaw = ev.packing_plan_actions(
            *_solution([("b", 10, 40, 5)], [("b", 40, 10, 5, 0, 0, 0)])
        )
        self.assertEqual(yaw[0]["orientation"], 1)

    def test_square_base_tie_breaks_to_zero(self):
        problem, solution = _solution([("a", 8, 8, 3)], [("a", 8, 8, 3, 4, 5, 6)])
        actions = ev.packing_plan_actions(problem, solution)
        self.assertEqual(actions[0]["orientation"], 0)

    def test_repeated_dims_deterministic_tiebreak(self):
        # Todas las dims iguales: 0 y 1 coinciden → desempate 0.
        problem, solution = _solution([("a", 5, 5, 5)], [("a", 5, 5, 5, 0, 0, 0)])
        self.assertEqual(ev.packing_plan_actions(problem, solution)[0]["orientation"], 0)

    def test_height_changing_rotation_rejected(self):
        problem, solution = _solution([("a", 30, 20, 10)], [("a", 30, 10, 20, 0, 0, 0)])
        with self.assertRaises(ev.YawExportError) as ctx:
            ev.packing_plan_actions(problem, solution)
        self.assertEqual(ctx.exception.incompatible[0]["item_id"], "a")
        self.assertIn("no_representable", ctx.exception.incompatible[0]["reason"])

    def test_mixed_plan_one_incompatible_rejects_all(self):
        problem, solution = _solution(
            [("a", 10, 20, 30), ("b", 10, 20, 30)],
            [
                ("a", 10, 20, 30, 0, 0, 0),
                ("b", 30, 20, 10, 10, 0, 0),  # cambia altura
            ],
        )
        with self.assertRaises(ev.YawExportError) as ctx:
            ev.packing_plan_actions(problem, solution)
        ids = {row["item_id"] for row in ctx.exception.incompatible}
        self.assertEqual(ids, {"b"})

    def test_unknown_id_rejected(self):
        problem, solution = _solution([("a", 10, 10, 10)], [("ghost", 10, 10, 10, 0, 0, 0)])
        with self.assertRaises(ev.YawExportError) as ctx:
            ev.packing_plan_actions(problem, solution)
        self.assertEqual(ctx.exception.incompatible[0]["reason"], "id_inexistente_en_problem")

    def test_invalid_dimensions_rejected(self):
        problem, solution = _solution([("a", 10, 10, 10)], [("a", -1, 10, 10, 0, 0, 0)])
        with self.assertRaises(ev.YawExportError):
            ev.packing_plan_actions(problem, solution)

    def test_tolerance_documented(self):
        self.assertEqual(ev.YAW_EXPORT_TOLERANCE_MM, 1e-6)
        L, W, H = 10.0, 20.0, 30.0
        oriented = (10.0 + EPS * 0.5, 20.0, 30.0)
        self.assertEqual(ev.yaw_orientation_flag((L, W, H), oriented), 0)
        oriented_bad = (10.0 + EPS * 2, 20.0, 30.0)
        self.assertIsNone(ev.yaw_orientation_flag((L, W, H), oriented_bad))

    def test_round_trip_preserves_id_flb_oriented(self):
        problem, solution = _solution([("a", 30, 10, 5)], [("a", 10, 30, 5, 1, 2, 3)])
        before = copy.deepcopy(solution.model_dump(mode="json"))
        actions = ev.packing_plan_actions(problem, solution)
        after = solution.model_dump(mode="json")
        self.assertEqual(before, after)
        act = actions[0]
        self.assertEqual(act["item"]["id"], "a")
        decoded = ev.decode_yaw01_oriented_lwh(
            (act["item"]["length"], act["item"]["width"], act["item"]["height"]),
            act["orientation"],
        )
        self.assertTrue(ev._yaw_axis_match(decoded, (10.0, 30.0, 5.0)))
        self.assertEqual(act["flb_coordinates"], [1.0, 2.0, 3.0])

    def test_rotation_forbidden_rejects_yaw_one(self):
        problem, solution = _solution(
            [("a", 30, 10, 5)],
            [("a", 10, 30, 5, 0, 0, 0)],
            allow_rotation=False,
        )
        with self.assertRaises(ev.YawExportError) as ctx:
            ev.packing_plan_actions(problem, solution)
        self.assertIn("rotacion_prohibida", ctx.exception.incompatible[0]["reason"])

    def test_legacy_unsafe_not_used_as_fallback(self):
        problem, solution = _solution([("a", 30, 20, 10)], [("a", 30, 10, 20, 0, 0, 0)])
        with self.assertRaises(ev.YawExportError):
            ev.packing_plan_actions(problem, solution)
        legacy = ev.packing_plan_actions_legacy_unsafe_yaw(problem, solution)
        self.assertTrue(legacy[0]["legacy_unsafe_yaw_export"])
        # El legacy aún «exporta» pero no es fiel: decode ≠ oriented interno.
        decoded = ev.decode_yaw01_oriented_lwh((30, 20, 10), legacy[0]["orientation"])
        self.assertFalse(ev._yaw_axis_match(decoded, (30, 10, 20)))

    def test_mixed_plan_reports_all_incompatibilities(self):
        problem, solution = _solution(
            [("a", 10, 20, 30), ("b", 10, 20, 30), ("c", 5, 5, 5)],
            [
                ("a", 30, 20, 10, 0, 0, 0),  # altura
                ("b", 20, 30, 10, 10, 0, 0),  # altura
                ("c", 5, 5, 5, 20, 0, 0),  # ok
            ],
        )
        with self.assertRaises(ev.YawExportError) as ctx:
            ev.packing_plan_actions(problem, solution)
        ids = {row["item_id"] for row in ctx.exception.incompatible}
        self.assertEqual(ids, {"a", "b"})

    def test_path_collision_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            shared = Path(folder) / "same.json"
            shared.write_text('{"keep": true}\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                capture_mod.assert_distinct_write_paths(shared, shared)
            self.assertIn("coinciden", str(ctx.exception))
            self.assertEqual(shared.read_text(encoding="utf-8"), '{"keep": true}\n')

            out = Path(folder) / "capture.json"
            yaw = Path(folder) / "yaw.json"
            out.write_text("sentinel-capture\n", encoding="utf-8")
            yaw.write_text("sentinel-yaw\n", encoding="utf-8")
            # Distinct paths OK
            capture_mod.assert_distinct_write_paths(out, yaw)
            self.assertEqual(out.read_text(), "sentinel-capture\n")
            self.assertEqual(yaw.read_text(), "sentinel-yaw\n")

    def test_strict_reject_does_not_create_plan_file(self):
        problem, solution = _solution([("a", 30, 20, 10)], [("a", 30, 10, 20, 0, 0, 0)])
        with tempfile.TemporaryDirectory() as folder:
            yaw_path = Path(folder) / "subdir" / "yaw.json"
            preexisting = Path(folder) / "existing.json"
            preexisting.write_text('{"old": 1}\n', encoding="utf-8")
            report = capture_mod.write_strict_yaw_export(
                problem, solution, "oid", preexisting
            )
            self.assertFalse(report["ok"])
            self.assertFalse(report["file_created_or_modified"])
            self.assertFalse(report["wrote_plan"])
            self.assertEqual(preexisting.read_text(encoding="utf-8"), '{"old": 1}\n')
            self.assertFalse(yaw_path.exists())
            self.assertIn("No se invocó packing_plan_actions_legacy_unsafe_yaw", report["note"])

            # Legacy solo si se pide explícitamente (ruta distinta).
            unsafe_path = Path(folder) / "unsafe.json"
            unsafe = capture_mod.write_legacy_unsafe_yaw_export(
                problem, solution, "oid", unsafe_path
            )
            self.assertTrue(unsafe["legacy_unsafe_yaw_export"])
            payload = json.loads(unsafe_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["_legacy_unsafe_yaw_export"])
            self.assertIn("oid", payload)


if __name__ == "__main__":
    unittest.main()
