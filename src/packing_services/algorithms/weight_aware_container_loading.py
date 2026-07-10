"""Algoritmo ``weight_aware_container_loading`` — Weight-aware Container Loading.

Carga constructiva multi-contenedor que prioriza los ítems más pesados y respeta
el peso máximo de cada contenedor además de la geometría. Reutiliza el motor de
puntos extremos con selección best-fit y ordenamiento por peso descendente.

La distribución fina de peso, el centro de gravedad y la estabilidad avanzada
quedan documentados como fase posterior (no se optimizan aquí).
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
    SortStrategy,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._extreme_points import ExtremePointPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="weight_aware_container_loading",
    display_name="Weight-aware Container Loading",
    problem_types=[ProblemType.CONTAINER_LOADING, ProblemType.THREE_D_BPP],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Carga constructiva multi-contenedor que prioriza ítems pesados y respeta "
        "el peso máximo de cada contenedor (best-fit por contacto)."
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
    ],
    unsupported_constraints=[
        Constraint.CENTER_OF_GRAVITY,
        Constraint.ADVANCED_STABILITY,
        Constraint.FRAGILITY,
        Constraint.LOAD_BEARING,
        Constraint.UNLOADING_SEQUENCE,
    ],
    parameters={
        "sort_strategy": "Orden de ítems (por defecto weight_desc)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "No optimiza distribución de peso ni centro de gravedad",
        "Sin estabilidad física avanzada",
    ],
)


class WeightAwareContainerLoading(PackingAlgorithm):
    """Carga de contenedores consciente del peso."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        # Por defecto prioriza los ítems más pesados.
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy", SortStrategy.WEIGHT_DESC.value)
        )
        packer = ExtremePointPacker(sort_strategy=sort_strategy, selection="best_fit")

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
