"""Algoritmo ``layer_based_palletization`` — Layer-based Palletization."""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._layer_pallet import LayerPalletPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="layer_based_palletization",
    display_name="Layer-based Palletization",
    problem_types=[ProblemType.PALLETIZATION],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Construye capas horizontales sobre el pallet: dentro de cada capa "
        "coloca ítems en el plano (x, y) con criterio bottom-left-back y "
        "avanza en z cuando la capa se llena."
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
        Constraint.BASIC_STABILITY,
        Constraint.LOAD_BEARING,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.ADVANCED_STABILITY,
        Constraint.FRAGILITY,
        Constraint.UNLOADING_SEQUENCE,
    ],
    parameters={"sort_strategy": "Orden de ítems (por defecto volume_desc)"},
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "No modela estabilidad ni carga máxima soportada entre ítems",
    ],
)


class LayerBasedPalletization(PackingAlgorithm):
    """Palletización constructiva por capas."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        packer = LayerPalletPacker(sort_strategy=sort_strategy)

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
