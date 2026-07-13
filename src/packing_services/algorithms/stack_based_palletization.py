"""Algoritmo ``stack_based_palletization`` — Stack-based Palletization."""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._stack_pallet import StackPalletConfig, StackPalletPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="stack_based_palletization",
    display_name="Stack-based Palletization",
    problem_types=[ProblemType.PALLETIZATION, ProblemType.STACKING_AWARE],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Organiza ítems en columnas verticales sobre el pallet. Coloca cada "
        "pieza en la columna factible más compacta (bottom-left-back) sin "
        "exigir estabilidad avanzada."
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
    parameters={
        "sort_strategy": "Orden de ítems (por defecto volume_desc)",
        "min_support_ratio": "Umbral de soporte si basic_stability está activo (float)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "No aplica load_bearing salvo que se active en constraints",
    ],
)


class StackBasedPalletization(PackingAlgorithm):
    """Palletización por columnas verticales."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        min_support = float(problem.algorithm.parameters.get("min_support_ratio", 0.6))
        config = StackPalletConfig(
            sort_strategy=sort_strategy,
            enforce_stability=False,
            enforce_load_bearing=False,
            min_support_ratio=min_support,
        )
        packer = StackPalletPacker(config)

        with measure_time() as elapsed:
            packed, unpacked = packer.pack(problem)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
