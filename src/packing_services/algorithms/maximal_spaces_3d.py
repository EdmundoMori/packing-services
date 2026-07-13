"""Algoritmo ``maximal_spaces_3d`` — Maximal Empty Spaces Heuristic."""

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
from ._maximal_spaces import MaximalSpacePacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="maximal_spaces_3d",
    display_name="Maximal Empty Spaces Heuristic",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Representa los espacios vacíos máximos por contenedor, actualizados con "
        "cortes guillotina tras cada colocación. Selección best-fit sobre el "
        "espacio (menor volumen residual)."
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
        "selection": "Criterio de espacio: best_fit | blb",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Heurístico; no garantiza optimalidad",
        "Partición guillotina simplificada de espacios libres",
    ],
)


class MaximalSpaces3D(PackingAlgorithm):
    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        sort_strategy = _resolve_sort_strategy(params.get("sort_strategy"))
        selection = str(params.get("selection", "best_fit")).lower()
        if selection not in ("best_fit", "blb"):
            selection = "best_fit"

        packer = MaximalSpacePacker(sort_strategy=sort_strategy, selection=selection)

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
