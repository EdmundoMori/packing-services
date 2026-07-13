"""Algoritmo ``constructive_plus_local_search`` — Constructivo + mejora local.

Combina una heurística constructiva (por defecto ``best_fit_decreasing_3d``) con
una fase de **mejora local**: compactación multi-pase y un pase de reubicación
que prueba posiciones candidatas más cercanas al origen.

Demuestra la arquitectura en dos fases (construir → mejorar) alineada con el
estado del arte, sin pasar a metaheurísticas.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._compaction import improve_solution, positions_moved
from ._constructive_runner import resolve_base_algorithm, run_constructive_base
from .base import PackingAlgorithm, build_solution
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="constructive_plus_local_search",
    display_name="Constructive Heuristic + Local Improvement",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.HYBRID,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Heurística constructiva seguida de mejora local: compactación y "
        "reubicación de piezas hacia posiciones más compactas."
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
        "base_algorithm": "Constructivo inicial (por defecto best_fit_decreasing_3d)",
        "sort_strategy": "Orden de ítems del constructivo base",
        "compaction_passes": "Pases de compactación (int, por defecto 3)",
        "relocation_pass": "Aplicar reubicación local (bool, por defecto true)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Mejora local determinista; no garantiza optimalidad",
        "No intenta empacar ítems adicionales respecto al constructivo base",
    ],
)


class ConstructivePlusLocalSearch(PackingAlgorithm):
    """Constructivo + compactación + reubicación local."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        base_name = resolve_base_algorithm(problem)
        compaction_passes = int(params.get("compaction_passes", 3))
        relocation = bool(params.get("relocation_pass", True))

        with measure_time() as elapsed:
            base_solution = run_constructive_base(problem, base_name)
            before = base_solution.packed_items
            improved = improve_solution(
                before,
                problem.containers,
                problem.constraints,
                compaction_passes=compaction_passes,
                relocation=relocation,
            )
            moved = positions_moved(before, improved)

        solution = build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=improved,
            unpacked_items=base_solution.unpacked_items,
            execution_time_seconds=elapsed.seconds,
        )
        solution = solution.model_copy(
            update={
                "execution_metadata": solution.execution_metadata.model_copy(
                    update={
                        "parameters": {
                            **solution.execution_metadata.parameters,
                            "items_relocated": moved,
                            "base_algorithm_used": base_name,
                            "base_items_packed": base_solution.metrics.items_packed,
                        }
                    }
                )
            }
        )
        return solution
