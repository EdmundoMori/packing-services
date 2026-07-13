"""Algoritmo ``orientation_improvement`` — mejora de orientaciones in situ."""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ._improvement_ops import apply_improvement_passes
from ._improvement_runner import run_improvement_layer
from .base import PackingAlgorithm
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="orientation_improvement",
    display_name="Orientation Improvement",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.IMPROVEMENT_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Constructivo base + prueba de orientaciones alternativas en la misma "
        "posición para cada pieza colocada."
    ),
    deterministic=True,
    supports_random_seed=False,
    supports_time_limit=False,
    supports_rotation=True,
    supports_multi_container=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
        Constraint.BASIC_STABILITY,
    ],
    unsupported_constraints=[
        Constraint.FRAGILITY,
        Constraint.LOAD_BEARING,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.UNLOADING_SEQUENCE,
        Constraint.ADVANCED_STABILITY,
    ],
    parameters={
        "base_algorithm": "Constructivo inicial (default según problem_type)",
        "improvement_passes": "Rondas sobre el layout (int, default 1)",
    },
    metrics=DEFAULT_METRICS,
    limitations=["Solo reorienta piezas ya colocadas; no replantea el layout"],
)


class OrientationImprovement(PackingAlgorithm):
    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        passes = int(params.get("improvement_passes", 1))

        def _improve(prob: PackingProblem, base: PackingSolution):
            improved, trace = apply_improvement_passes(
                base.packed_items,
                prob,
                passes=passes,
                op="orientation",
            )
            return improved, trace

        return run_improvement_layer(self, problem, _improve)
