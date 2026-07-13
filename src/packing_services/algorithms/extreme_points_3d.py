"""Algoritmo ``extreme_points_3d`` — Extreme Points Heuristic.

Heurística constructiva que mantiene una lista persistente de puntos extremos
por contenedor y coloca cada ítem en el punto extremo factible más
bottom-left-back. Mejora la calidad frente a ``heuristic_3d_bpp_v1`` porque los
puntos extremos se proyectan sobre las superficies existentes y se depuran los
que quedan cubiertos.

Comparte validador, métricas y formato de salida con el resto de algoritmos.
No garantiza optimalidad.
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
    name="extreme_points_3d",
    display_name="Extreme Points Heuristic",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Mantiene una lista de puntos extremos por contenedor, proyectados sobre "
        "las superficies existentes, y coloca cada ítem en el punto extremo "
        "factible más bottom-left-back."
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
        "Variante simplificada de Extreme Points (proyección vertical)",
        "Sin estabilidad física avanzada",
    ],
)


class ExtremePoints3D(PackingAlgorithm):
    """Implementación de la heurística de puntos extremos (selección BLB)."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        packer = ExtremePointPacker(sort_strategy=sort_strategy, selection="blb")

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
