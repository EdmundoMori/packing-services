"""Algoritmo ``stacking_aware_constructive`` — Stacking-aware Constructive Packing."""

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
    name="stacking_aware_constructive",
    display_name="Stacking-aware Constructive Packing",
    problem_types=[ProblemType.STACKING_AWARE],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Coloca ítems en columnas verticales verificando superficie de soporte "
        "y carga máxima soportada (``max_load_on_top``) durante la construcción."
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
        Constraint.LOAD_BEARING,
    ],
    unsupported_constraints=[
        Constraint.CENTER_OF_GRAVITY,
        Constraint.ADVANCED_STABILITY,
        Constraint.FRAGILITY,
        Constraint.UNLOADING_SEQUENCE,
    ],
    parameters={
        "sort_strategy": "Orden de ítems (por defecto weight_desc)",
        "min_support_ratio": "Superficie mínima de apoyo (float, por defecto 0.6)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "Load-bearing solo si los ítems declaran max_load_on_top",
        "Sin centro de gravedad ni estabilidad avanzada",
    ],
)


class StackingAwareConstructive(PackingAlgorithm):
    """Constructivo con reglas de apilamiento."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy", "weight_desc")
        )
        min_support = float(problem.algorithm.parameters.get("min_support_ratio", 0.6))
        config = StackPalletConfig(
            sort_strategy=sort_strategy,
            enforce_stability=True,
            enforce_load_bearing=True,
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
