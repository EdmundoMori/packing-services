"""Algoritmo ``heuristic_3d_bpp_v1`` — Volume First Candidate Placement.

Heurística constructiva base del proyecto (Fase 4). Ordena los ítems por
volumen descendente y coloca cada uno en la mejor posición candidata disponible
siguiendo un criterio bottom-left-back global entre contenedores. Prueba las
rotaciones permitidas y valida contención, no solapamiento y peso antes de
aceptar cada colocación.

No garantiza optimalidad: es una heurística rápida y reproducible pensada como
primer motor de servicio y como baseline de comparación.
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
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

METADATA = AlgorithmMetadata(
    name="heuristic_3d_bpp_v1",
    display_name="Volume First Candidate Placement",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.SINGLE_CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Heurística constructiva: ordena ítems por volumen descendente, genera "
        "posiciones candidatas a partir de los ítems colocados y elige la "
        "posición bottom-left-back factible entre todos los contenedores."
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
        "position_strategy": "Orden de posiciones candidatas (bottom_left_back)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Algoritmo heurístico; no garantiza optimalidad",
        "Solo factibilidad geométrica básica",
        "Sin estabilidad física avanzada",
    ],
)


class Heuristic3DBPPv1(PackingAlgorithm):
    """Implementación de la heurística Volume First Candidate Placement."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        params = problem.algorithm.parameters
        sort_strategy = _resolve_sort_strategy(params.get("sort_strategy"))

        packer = ConstructivePacker(
            sort_strategy=sort_strategy,
            container_selection="global_blb",
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


def _resolve_sort_strategy(value: str | None) -> SortStrategy:
    if value is None:
        return SortStrategy.VOLUME_DESC
    try:
        return SortStrategy(value)
    except ValueError:
        return SortStrategy.VOLUME_DESC
