"""Algoritmo ``best_fit_decreasing_3d`` — Best Fit Decreasing 3D.

Variante de la heurística por puntos extremos que, en lugar de elegir la
posición más bottom-left-back, selecciona la colocación que **mejor encaja**:
la que maximiza el área de contacto con las paredes del contenedor y con las
cajas ya colocadas (menor espacio residual alrededor del ítem).

Comparte motor (``ExtremePointPacker``), validador, métricas y formato de
salida con ``extreme_points_3d``, por lo que son directamente comparables. No
garantiza optimalidad.
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
from ._extreme_points import ExtremePointPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="best_fit_decreasing_3d",
    display_name="Best Fit Decreasing 3D",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.SINGLE_CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Ordena ítems de forma decreciente y coloca cada uno en el punto extremo "
        "que maximiza el contacto con paredes y cajas vecinas (mejor encaje / "
        "menor espacio residual)."
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
        "El criterio best-fit usa área de contacto como proxy del residuo",
        "Sin estabilidad física avanzada",
    ],
)


class BestFitDecreasing3D(PackingAlgorithm):
    """Implementación de Best Fit Decreasing 3D (selección por contacto)."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
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
