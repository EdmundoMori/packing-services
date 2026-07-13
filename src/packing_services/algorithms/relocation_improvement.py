"""Algoritmo ``relocation_improvement`` — reubicación local sobre solución base."""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ._compaction import improve_solution
from ._improvement_runner import run_improvement_layer
from .base import PackingAlgorithm
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="relocation_improvement",
    display_name="Relocation Improvement",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.IMPROVEMENT_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Ejecuta un constructivo base y aplica reubicación local hacia posiciones "
        "candidatas más compactas (sin cambiar el conjunto de ítems empacados)."
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
        "relocation_passes": "Pases de reubicación (int, default 2)",
        "compaction_passes": "Pases de compactación final (int, default 1)",
    },
    metrics=DEFAULT_METRICS,
    limitations=["Mejora local; no garantiza optimalidad"],
)


class RelocationImprovement(PackingAlgorithm):
    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        relocation_passes = int(params.get("relocation_passes", 2))
        compaction_passes = int(params.get("compaction_passes", 1))

        def _improve(prob: PackingProblem, base: PackingSolution):
            improved = base.packed_items
            for _ in range(max(1, relocation_passes)):
                improved = improve_solution(
                    improved,
                    prob.containers,
                    prob.constraints,
                    compaction_passes=0,
                    relocation=True,
                )
            if compaction_passes > 0:
                improved = improve_solution(
                    improved,
                    prob.containers,
                    prob.constraints,
                    compaction_passes=compaction_passes,
                    relocation=False,
                )
            return improved, {
                "relocation_passes": relocation_passes,
                "compaction_passes": compaction_passes,
            }

        return run_improvement_layer(self, problem, _improve)
