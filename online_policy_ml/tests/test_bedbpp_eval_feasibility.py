"""Pruebas sintéticas C02 — semántica de factibilidad de bedbpp_eval."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "online_policy_ml" / "src_ml"))
sys.path.insert(0, str(REPO / "src"))

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

BIN = (100.0, 100.0, 100.0)


def _action(item_id: str, l: float, w: float, h: float, ori: int, flb: list[float]) -> dict:
    return {
        "item": {"id": item_id, "length": l, "width": w, "height": h, "weight": 1.0},
        "orientation": ori,
        "flb_coordinates": flb,
    }


def _problem_solution(
    items: list[tuple[str, float, float, float]],
    packed: list[tuple[str, float, float, float, float, float, float]],
    *,
    unpacked: list[str] | None = None,
    allow_rotation: bool = True,
    container_lwh: tuple[float, float, float] = BIN,
) -> tuple[PackingProblem, PackingSolution]:
    problem = PackingProblem(
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        containers=[
            Container(
                id="c0",
                length=container_lwh[0],
                width=container_lwh[1],
                height=container_lwh[2],
            )
        ],
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
    unpacked_items = [UnpackedItem(item_id=u) for u in (unpacked or [])]
    solution = PackingSolution(
        status=SolutionStatus.SUCCESS,
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        algorithm_name="test",
        packed_items=packed_items,
        unpacked_items=unpacked_items,
        metrics=Metrics(
            items_packed=len(packed_items),
            items_unpacked=len(unpacked_items),
        ),
        execution_metadata=ExecutionMetadata(
            algorithm="test",
            algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
            service_version="test",
        ),
    )
    return problem, solution


class TestFeasibilitySemanticsC02(unittest.TestCase):
    def test_full_overlap_geometry_invalid(self):
        actions = [
            _action("a", 10, 10, 10, 0, [0, 0, 0]),
            _action("b", 10, 10, 10, 0, [0, 0, 0]),
        ]
        out = ev.kpis_zhao_from_plan(actions, n_order=2, bin_lwh=BIN)
        self.assertFalse(out["non_overlap_valid"])
        self.assertFalse(out["geometry_valid"])
        self.assertFalse(out["feasible"])
        self.assertIsNone(out["uti"])
        self.assertIsNotNone(out["diagnostic_uti"])
        self.assertEqual(out["metric_status"], "diagnostic_only_geometry_invalid_or_incomplete_evidence")

    def test_face_contact_allowed(self):
        actions = [
            _action("a", 10, 10, 10, 0, [0, 0, 0]),
            _action("b", 10, 10, 10, 0, [10, 0, 0]),
        ]
        out = ev.kpis_zhao_from_plan(actions, n_order=2, bin_lwh=BIN)
        self.assertTrue(out["non_overlap_valid"])
        self.assertTrue(out["containment_valid"])
        self.assertTrue(out["geometry_valid"])
        self.assertTrue(out["feasible"])
        self.assertIsNotNone(out["uti"])
        self.assertNotIn("diagnostic_uti", out)

    def test_box_inside_and_outside(self):
        actions = [
            _action("in", 10, 10, 10, 0, [0, 0, 0]),
            _action("out", 10, 10, 10, 0, [95, 0, 0]),
        ]
        out = ev.kpis_zhao_from_plan(actions, n_order=2, bin_lwh=BIN)
        self.assertFalse(out["containment_valid"])
        self.assertFalse(out["geometry_valid"])
        self.assertEqual(out["n_fuera_bin"], 1)

    def test_partial_valid_packing(self):
        actions = [_action("a", 10, 10, 10, 0, [0, 0, 0])]
        out = ev.kpis_zhao_from_plan(actions, n_order=3, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertEqual(out["nu"], 2)
        self.assertTrue(out["feasible"])
        self.assertIsNotNone(out["uti"])

    def test_empty_plan_nonempty_order(self):
        out = ev.kpis_zhao_from_plan([], n_order=4, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertEqual(out["nu"], 4)
        self.assertEqual(out["uti"], 0.0)

    def test_duplicate_id(self):
        actions = [
            _action("a", 10, 10, 10, 0, [0, 0, 0]),
            _action("a", 10, 10, 10, 0, [20, 0, 0]),
        ]
        out = ev.kpis_zhao_from_plan(actions, n_order=2, bin_lwh=BIN)
        self.assertFalse(out["identity_valid"])
        self.assertFalse(out["geometry_valid"])
        self.assertEqual(out["duplicate_ids"], ["a"])

    def test_negative_nan_inf_dimensions(self):
        for bad in (-5.0, float("nan"), float("inf")):
            actions = [_action("a", bad, 10, 10, 0, [0, 0, 0])]
            out = ev.kpis_zhao_from_plan(actions, n_order=1, bin_lwh=BIN)
            self.assertFalse(out["geometry_valid"], bad)
            self.assertFalse(out["feasible"], bad)

    def test_incompatible_orientation_flag(self):
        actions = [_action("a", 10, 10, 10, 2, [0, 0, 0])]
        out = ev.kpis_zhao_from_plan(actions, n_order=1, bin_lwh=BIN)
        self.assertFalse(out["orientation_valid"])
        self.assertFalse(out["geometry_valid"])

    def test_incompatible_orientation_vs_original_solution(self):
        # Colocado con altura distinta: no es permutación del original 10×20×30.
        problem, solution = _problem_solution(
            [("a", 10, 20, 30)],
            [("a", 10, 20, 40, 0, 0, 0)],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertFalse(out["orientation_valid"])
        self.assertFalse(out["geometry_valid"])

    def test_published_without_plan_hn_le_H(self):
        out = ev.pct_zhao_publicado(n_order=26, eta_util=0.614, hn_m=1.9, nu=0, bin_lwh=ev.EURO_PALLET_MM)
        self.assertIsNone(out["geometry_valid"])
        self.assertIsNone(out["feasible"])
        self.assertIsNone(out["n_fuera_bin"])
        self.assertIsNone(out["uti"])
        self.assertFalse(out["evaluator_height_limit_exceeded"])
        self.assertTrue(out["all_items_packed"])
        self.assertTrue(out["estimated_volume_from_eta_hn"]["estimated"])

    def test_published_without_plan_hn_gt_H(self):
        out = ev.pct_zhao_publicado(n_order=26, eta_util=0.614, hn_m=2.105, nu=0, bin_lwh=ev.EURO_PALLET_MM)
        self.assertIsNone(out["geometry_valid"])
        self.assertIsNone(out["feasible"])
        self.assertTrue(out["evaluator_height_limit_exceeded"])
        self.assertIsNone(out["n_fuera_bin"])
        self.assertIn("no invalida", out["nota"])

    def test_nu_positive_not_geometry_invalid(self):
        out = ev.pct_zhao_publicado(n_order=10, eta_util=0.5, hn_m=1.5, nu=3, bin_lwh=ev.EURO_PALLET_MM)
        self.assertFalse(out["all_items_packed"])
        self.assertIsNone(out["geometry_valid"])
        self.assertIsNone(out["feasible"])
        self.assertEqual(out["nu"], 3)

    def test_non_homologated_comparison_no_superiority(self):
        ours = ev.kpis_zhao_from_plan(
            [_action("a", 10, 10, 10, 0, [0, 0, 0])], n_order=1, bin_lwh=BIN
        )
        pct = ev.pct_zhao_publicado(n_order=1, eta_util=0.5, hn_m=2.1, nu=0, bin_lwh=BIN)
        # Históricamente: feasible nuestro true + pct false ⇒ «supera». Ahora no.
        self.assertTrue(ours["geometry_valid"])
        verd = ev.veredicto_zhao(ours, pct)
        self.assertFalse(verd["comparison_valid"])
        self.assertEqual(verd["lado"], "no_compara")
        self.assertNotEqual(verd["lado"], "supera")
        tabla = ev.tabla_comparacion(ours, pct)
        self.assertFalse(tabla["comparison_valid"])
        self.assertIsNone(tabla["columna_decisoria"])

    def test_diagnostic_not_confused_with_validated(self):
        bad = ev.kpis_zhao_from_plan(
            [
                _action("a", 10, 10, 10, 0, [0, 0, 0]),
                _action("b", 10, 10, 10, 0, [0, 0, 0]),
            ],
            n_order=2,
            bin_lwh=BIN,
        )
        self.assertIsNone(bad["uti"])
        self.assertIn("diagnostic_uti", bad)
        good = ev.kpis_zhao_from_plan(
            [_action("a", 10, 10, 10, 0, [0, 0, 0])], n_order=1, bin_lwh=BIN
        )
        self.assertIsNotNone(good["uti"])
        self.assertNotIn("diagnostic_uti", good)
        self.assertIsNone(ev._validated_uti(bad))
        self.assertIsNotNone(ev._validated_uti(good))

    def test_homologated_flags_do_not_authorize_superiority(self):
        a = ev.kpis_zhao_from_plan([_action("a", 10, 10, 10, 0, [0, 0, 0])], n_order=1, bin_lwh=BIN)
        b = ev.kpis_zhao_from_plan([_action("b", 10, 10, 10, 0, [20, 0, 0])], n_order=1, bin_lwh=BIN)
        verd = ev.veredicto_zhao(
            a,
            b,
            protocols_homologated=True,
            shared_metric_contract="test_contract_v1",
            homologation_evidence={"container_lwh_mm": list(BIN)},
        )
        self.assertFalse(verd["comparison_valid"])
        self.assertEqual(verd["lado"], "no_compara")
        self.assertIsNotNone(verd["internal_uti_delta_diagnostic"])

    def test_published_with_flags_still_no_superiority(self):
        ours = ev.kpis_zhao_from_plan(
            [_action("a", 10, 10, 10, 0, [0, 0, 0])], n_order=1, bin_lwh=BIN
        )
        pct = ev.pct_zhao_publicado(n_order=1, eta_util=0.5, hn_m=2.1, nu=0, bin_lwh=BIN)
        verd = ev.veredicto_zhao(
            ours, pct, protocols_homologated=True, shared_metric_contract="fake"
        )
        self.assertFalse(verd["comparison_valid"])
        self.assertEqual(verd["lado"], "no_compara")
        self.assertIsNone(verd["internal_uti_delta_diagnostic"])

    def test_solution_overlap_detected(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [
                ("a", 10, 10, 10, 0, 0, 0),
                ("b", 10, 10, 10, 0, 0, 0),
            ],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertFalse(out["geometry_valid"])
        self.assertGreater(out["n_overlap_pairs"], 0)
        self.assertIs(out["feasible"], False)
        self.assertIsNone(out["uti"])

    def test_solution_partial_valid(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            unpacked=["b"],
        )
        out = ev.kpis_zhao(problem, solution)  # bin desde problem.containers[0]
        self.assertEqual(out["bin_lwh_source"], "problem.containers[0]")
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertIs(out["feasible"], True)
        self.assertIsNotNone(out["uti"])

    def test_rotation_forbidden_permutation_rejected(self):
        # Original 10×20×30; colocado 20×10×30 es permutación yaw pero rotación prohibida.
        problem, solution = _problem_solution(
            [("a", 10, 20, 30)],
            [("a", 20, 10, 30, 0, 0, 0)],
            allow_rotation=False,
        )
        out = ev.kpis_zhao(problem, solution)
        self.assertFalse(out["orientation_valid"])
        self.assertFalse(out["geometry_valid"])
        self.assertIs(out["feasible"], False)

    def test_unknown_id_identity_invalid(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10)],
            [("ghost", 10, 10, 10, 0, 0, 0)],
        )
        out = ev.kpis_zhao(problem, solution)
        self.assertIn("ghost", out["unknown_ids"])
        self.assertFalse(out["identity_valid"])
        self.assertFalse(out["geometry_valid"])

    def test_field_coherence_null_not_bool_false(self):
        pub = ev.pct_zhao_publicado(n_order=5, eta_util=0.5, hn_m=1.0, nu=1)
        self.assertIsNone(pub["geometry_valid"])
        self.assertIsNone(pub["feasible"])
        self.assertIsNone(pub["containment_valid"])
        self.assertIsNone(pub["n_fuera_bin"])
        # null no se interpreta como false en el veredicto vía bool()
        self.assertIsNot(pub["feasible"], False)
        self.assertFalse(pub["all_items_packed"])

    def test_empty_plan_not_complete(self):
        out = ev.kpis_zhao_from_plan([], n_order=2, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertEqual(out["nu"], 2)
        self.assertIs(out["feasible"], True)

    def test_reject_nonpositive_bin(self):
        with self.assertRaises(ValueError):
            ev.kpis_zhao_from_plan([], n_order=0, bin_lwh=(100, 0, 100))
        with self.assertRaises(ValueError):
            ev.kpis_zhao_from_plan([], n_order=0, bin_lwh=(100, float("nan"), 100))


if __name__ == "__main__":
    unittest.main()
