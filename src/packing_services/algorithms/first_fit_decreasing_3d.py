"""Algoritmo ``first_fit_decreasing_3d`` — First Fit Decreasing 3D.

Segundo algoritmo local (Fase 5). Ordena los ítems por volumen descendente (o
por peso / dimensión mayor según parámetro) y coloca cada ítem en el primer
contenedor y la primera posición factible, llenando un contenedor antes de
pasar al siguiente. Comparte validador, métricas y formato de salida con
``heuristic_3d_bpp_v1``, por lo que ambos son directamente comparables.
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
from ._constructive import ConstructivePacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="first_fit_decreasing_3d",
    display_name="First Fit Decreasing 3D",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.SINGLE_CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Ordena ítems de forma decreciente y coloca cada uno en el primer "
        "contenedor y primera posición factible (first-fit), llenando un "
        "contenedor antes de abrir el siguiente."
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
        Constraint.FRAGILITY,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.LOAD_BEARING,
        Constraint.UNLOADING_SEQUENCE,
        Constraint.ADVANCED_STABILITY,
    ],
    parameters={
        "sort_strategy": "Orden de ítems: volume_desc | weight_desc | longest_dim_desc | input_order",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "First-fit puede usar más contenedores que una estrategia global",
        "Sin estabilidad física avanzada",
    ],
)


class FirstFitDecreasing3D(PackingAlgorithm):
    """Implementación de First Fit Decreasing 3D."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        sort_strategy = _resolve_sort_strategy(params.get("sort_strategy"))

        packer = ConstructivePacker(
            sort_strategy=sort_strategy,
            container_selection="first_fit",
        )

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
