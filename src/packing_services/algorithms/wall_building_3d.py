"""Algoritmo ``wall_building_3d`` — Wall-building Heuristic (Container Loading)."""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._wall_building import WallBuildingPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="wall_building_3d",
    display_name="Wall-building Heuristic",
    problem_types=[ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Construye paredes verticales sucesivas a lo largo de y: la primera "
        "en y=0 y las siguientes en el frente de la pared anterior, apilando "
        "en z y extendiendo en x. Heurística orientada a carga de camiones."
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
    parameters={"sort_strategy": "Orden de ítems (por defecto volume_desc)"},
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "Una vez cerrada una pared, no reabre huecos de paredes anteriores",
        "Sin estabilidad física avanzada ni secuencia de descarga",
    ],
)


class WallBuilding3D(PackingAlgorithm):
    """Carga por construcción de paredes verticales."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        packer = WallBuildingPacker(sort_strategy=sort_strategy)

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
