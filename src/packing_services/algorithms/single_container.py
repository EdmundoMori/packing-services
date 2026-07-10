"""Algoritmo ``single_container_constructive`` — Single Container Constructive Loading.

Baseline local para Container Loading / Single Container Loading: intenta
maximizar el volumen cargado en **un único contenedor**. Reutiliza la heurística
constructiva por puntos extremos con best-fit sobre el primer contenedor de la
instancia (ignora el resto si se proporcionan varios) y reporta ítems cargados,
no cargados, coordenadas y utilización.
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
    name="single_container_constructive",
    display_name="Single Container Constructive Loading",
    problem_types=[ProblemType.SINGLE_CONTAINER_LOADING, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
    status=AlgorithmStatus.IMPLEMENTED,
    description=(
        "Maximiza el volumen cargado en un único contenedor reutilizando la "
        "heurística por puntos extremos (best-fit). Si se pasan varios "
        "contenedores, solo se usa el primero."
    ),
    deterministic=True,
    supports_random_seed=False,
    supports_time_limit=False,
    supports_rotation=True,
    supports_multi_container=False,
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
        "sort_strategy": "Orden de ítems: volume_desc | weight_desc | longest_dim_desc",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Usa un solo contenedor; ignora contenedores adicionales",
        "Algoritmo heurístico; no garantiza optimalidad",
        "Sin restricciones logísticas avanzadas",
    ],
)


class SingleContainerConstructive(PackingAlgorithm):
    """Carga constructiva de un único contenedor."""

    metadata = METADATA

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )

        # Restringir la instancia al primer contenedor.
        single = problem.model_copy(update={"containers": problem.containers[:1]})

        packer = ExtremePointPacker(sort_strategy=sort_strategy, selection="best_fit")
        with measure_time() as elapsed:
            packed, unpacked = packer.pack(single)

        return build_solution(
            problem=single,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )
