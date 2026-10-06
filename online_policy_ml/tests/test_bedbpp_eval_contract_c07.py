"""Pruebas sintéticas C07 — contrato moncontenedor e identidad de bedbpp_eval."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "online_policy_ml" / "src_ml"))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "paper" / "studies" / "learning_objectives" / "tools"))

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
from capture_actor_eval_metadata_v1 import (  # noqa: E402
    METADATA_VERSION,
    attach_actor_eval_mode,
    attach_from_policy,
)

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
    containers: list[tuple[str, float, float, float]] | None = None,
    packed_container_ids: list[str] | None = None,
    metrics_packed: int | None = None,
    metrics_unpacked: int | None = None,
) -> tuple[PackingProblem, PackingSolution]:
    if containers is None:
        container_models = [
            Container(
                id="c0",
                length=container_lwh[0],
                width=container_lwh[1],
                height=container_lwh[2],
            )
        ]
    else:
        container_models = [
            Container(id=cid, length=L, width=W, height=H) for cid, L, W, H in containers
        ]
    problem = PackingProblem(
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        containers=container_models,
        items=[Item(id=i, length=l, width=w, height=h) for i, l, w, h in items],
        constraints=ConstraintFlags(allow_rotation=allow_rotation),
        algorithm=AlgorithmConfig(name="test"),
    )
    cids = packed_container_ids or ["c0"] * len(packed)
    packed_items = [
        PackedItem(
            item_id=iid,
            container_id=cids[idx],
            position=Point3D(x=x, y=y, z=z),
            orientation=Orientation(length=ol, width=ow, height=oh),
        )
        for idx, (iid, ol, ow, oh, x, y, z) in enumerate(packed)
    ]
    unpacked_items = [UnpackedItem(item_id=u) for u in (unpacked or [])]
    mp = len(packed_items) if metrics_packed is None else metrics_packed
    mu = len(unpacked_items) if metrics_unpacked is None else metrics_unpacked
    solution = PackingSolution(
        status=SolutionStatus.SUCCESS,
        problem_type=ProblemType.SINGLE_CONTAINER_LOADING,
        algorithm_name="test",
        packed_items=packed_items,
        unpacked_items=unpacked_items,
        metrics=Metrics(items_packed=mp, items_unpacked=mu),
        execution_metadata=ExecutionMetadata(
            algorithm="test",
            algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
            service_version="test",
        ),
    )
    return problem, solution


class TestMonoContainerContractC07(unittest.TestCase):
    def test_unknown_container_id_structured_invalid(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            packed_container_ids=["ghost_bin"],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertFalse(out["container_contract_valid"])
        self.assertIn("ghost_bin", out["foreign_container_ids"])
        self.assertIsNot(out["geometry_valid"], True)
        self.assertIs(out["feasible"], False)

    def test_multiple_containers_raises_contract_error(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            containers=[("c0", 100, 100, 100), ("c1", 100, 100, 100)],
        )
        with self.assertRaises(ev.EvaluatorContractError):
            ev.kpis_zhao(problem, solution, bin_lwh=BIN)

    def test_zero_containers_raises_contract_error(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
        )
        # El dominio exige ≥1 contenedor al construir; forzamos 0 para el evaluador.
        object.__setattr__(problem, "containers", [])
        with self.assertRaises(ev.EvaluatorContractError):
            ev.kpis_zhao(problem, solution, bin_lwh=BIN)

    def test_invented_container_ids_do_not_hide_overlap(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [
                ("a", 10, 10, 10, 0, 0, 0),
                ("b", 10, 10, 10, 0, 0, 0),
            ],
            packed_container_ids=["binA", "binB"],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertGreater(out["n_overlap_pairs"], 0)
        self.assertFalse(out["non_overlap_valid"])
        self.assertIsNot(out["geometry_valid"], True)
        self.assertFalse(out["container_contract_valid"])

    def test_explicit_bin_lwh_still_identified(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            container_lwh=(1200, 800, 2000),
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertEqual(out["bin_lwh_source"], "caller_explicit")
        self.assertEqual(out["bin_mm"], list(BIN))
        self.assertTrue(out["geometry_valid"])

    def test_wrong_metrics_full_placement_geometry_ok(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [
                ("a", 10, 10, 10, 0, 0, 0),
                ("b", 10, 10, 10, 20, 0, 0),
            ],
            metrics_packed=99,
            metrics_unpacked=0,
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertTrue(out["all_items_packed"])
        self.assertFalse(out["metrics_counter_coherence"]["consistent_with_placements"])
        self.assertEqual(out["N"], 2)

    def test_metrics_hiding_missing_items(self):
        # metrics dicen N=1 empaquetado+0; en realidad falta b.
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            unpacked=["b"],
            metrics_packed=1,
            metrics_unpacked=0,
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertEqual(out["N"], 2)
        self.assertFalse(out["metrics_counter_coherence"]["consistent_with_placements"])

    def test_duplicate_input_ids(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("a", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertIn("a", out["duplicate_input_ids"])
        self.assertFalse(out["identity_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertIsNot(out["geometry_valid"], True)

    def test_partial_geometrically_valid(self):
        problem, solution = _problem_solution(
            [("a", 10, 10, 10), ("b", 10, 10, 10)],
            [("a", 10, 10, 10, 0, 0, 0)],
            unpacked=["b"],
        )
        out = ev.kpis_zhao(problem, solution, bin_lwh=BIN)
        self.assertTrue(out["geometry_valid"])
        self.assertFalse(out["all_items_packed"])
        self.assertTrue(out["feasible"])

    def test_plan_validation_scope_declared(self):
        out = ev.kpis_zhao_from_plan(
            [_action("a", 10, 10, 10, 0, [0, 0, 0])], n_order=1, bin_lwh=BIN
        )
        scope = out["plan_validation_scope"]
        self.assertFalse(scope["receives_source_order"])
        self.assertEqual(scope["identity_and_dimensions"], "within_plan_only")
        self.assertFalse(scope["verified_against_independent_instance"])
        self.assertFalse(scope["external_homologation"])
        self.assertEqual(scope["comparison_valid_policy"], "C02_block_preserved")
        # comparison_valid sigue bloqueado en veredicto
        other = ev.kpis_zhao_from_plan(
            [_action("b", 10, 10, 10, 0, [20, 0, 0])], n_order=1, bin_lwh=BIN
        )
        verd = ev.veredicto_zhao(out, other, protocols_homologated=True)
        self.assertFalse(verd["comparison_valid"])


class TestCaptureActorEvalMetadataC07(unittest.TestCase):
    def test_eval_observed_true(self):
        class _Model:
            training = False

        class _Policy:
            def __init__(self) -> None:
                self.model = _Model()

        doc = {"recipe": {"method": "preferences", "actor_eval_mode": False}}
        attach_from_policy(doc, _Policy(), is_actor_arm=True)
        self.assertIs(doc["recipe"]["actor_eval_mode"], True)
        self.assertEqual(doc["recipe"]["actor_eval_mode_metadata_version"], METADATA_VERSION)
        self.assertEqual(doc["recipe"]["actor_eval_mode_source"], "executor_explicit_c07")
        self.assertEqual(doc["recipe"]["actor_eval_mode_evidence"]["assignment"], "eval_observed")

    def test_training_observed_false(self):
        class _Model:
            training = True

        class _Policy:
            model = _Model()

        doc = {"recipe": {}}
        attach_from_policy(doc, _Policy(), is_actor_arm=True)
        self.assertIs(doc["recipe"]["actor_eval_mode"], False)
        self.assertEqual(doc["recipe"]["actor_eval_mode_evidence"]["assignment"], "training_observed")

    def test_actor_without_model_null(self):
        class _Policy:
            pass

        doc = {"recipe": {}}
        attach_from_policy(doc, _Policy(), is_actor_arm=True)
        self.assertIsNone(doc["recipe"]["actor_eval_mode"])
        ev = doc["recipe"]["actor_eval_mode_evidence"]
        self.assertFalse(ev["actor_model_present"])
        self.assertEqual(ev["assignment"], "insufficient_evidence")

    def test_model_without_training_attr_null(self):
        class _Model:
            pass

        class _Policy:
            model = _Model()

        doc = {"recipe": {}}
        attach_from_policy(doc, _Policy(), is_actor_arm=True)
        self.assertIsNone(doc["recipe"]["actor_eval_mode"])
        self.assertEqual(
            doc["recipe"]["actor_eval_mode_evidence"]["model_training_note"],
            "model_without_training_attr",
        )

    def test_none_not_converted_via_bool(self):
        class _Model:
            training = None

        class _Policy:
            model = _Model()

        doc = {"recipe": {}}
        attach_from_policy(doc, _Policy(), is_actor_arm=True)
        self.assertIsNone(doc["recipe"]["actor_eval_mode"])
        self.assertIsNot(doc["recipe"]["actor_eval_mode"], False)

    def test_greedy_arm_false(self):
        doc = {"recipe": {}}
        attach_actor_eval_mode(doc, actor_eval_mode=False, evidence={"arm": "greedy"})
        self.assertIs(doc["recipe"]["actor_eval_mode"], False)


if __name__ == "__main__":
    unittest.main()
