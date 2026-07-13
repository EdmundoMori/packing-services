"""Algoritmo ``solution_compaction`` — Compaction (mejora local).

Toma una solución constructiva inicial (por defecto ``best_fit_decreasing_3d``)
y **compacta** las piezas hacia el origen del contenedor deslizándolas en los
ejes X, Y y Z sin violar contención ni solapamiento. Es una segunda capa de
mejora local sobre una colocación ya válida.

No garantiza optimalidad; puede mejorar la utilización o liberar espacio para
futuras extensiones, pero mantiene el mismo conjunto de ítems empacados.
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
    name="solution_compaction",
    display_name="Compaction",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.IMPROVEMENT_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Ejecuta un algoritmo constructivo base y aplica compactación local: "
        "desliza piezas hacia el origen (bottom-left-back) en varios pases."
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
        "base_algorithm": (
            "Constructivo inicial (default por tipo: best_fit en 3D_BPP, "
            "weight_aware en CONTAINER_LOADING)"
        ),
        "sort_strategy": "Orden de ítems del constructivo base",
        "compaction_passes": "Número de pases de compactación (int, por defecto 3)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "No cambia el conjunto de ítems empacados respecto al constructivo base",
        "Mejora local; no garantiza optimalidad global",
    ],
)


class SolutionCompaction(PackingAlgorithm):
    """Compactación local sobre una solución constructiva inicial."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        base_name = resolve_base_algorithm(problem)
        compaction_passes = int(params.get("compaction_passes", 3))

        with measure_time() as elapsed:
            base_solution = run_constructive_base(problem, base_name)
            before = base_solution.packed_items
            improved = improve_solution(
                before,
                problem.containers,
                problem.constraints,
                compaction_passes=compaction_passes,
                relocation=False,
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
