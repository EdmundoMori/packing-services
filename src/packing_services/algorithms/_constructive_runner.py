"""Utilidad para ejecutar el algoritmo constructivo base en híbridos/mejora."""

from __future__ import annotations

from ..domain.enums import ProblemType
from ..domain.models import PackingProblem, PackingSolution
from ..utils.errors import AlgorithmNotFoundError
from .best_fit_decreasing_3d import BestFitDecreasing3D
from .extreme_points_3d import ExtremePoints3D
from .first_fit_decreasing_3d import FirstFitDecreasing3D
from .heuristic_3d_bpp import Heuristic3DBPPv1
from .single_container import SingleContainerConstructive
from .weight_aware_container_loading import WeightAwareContainerLoading

_CONSTRUCTIVES = {
    "heuristic_3d_bpp_v1": Heuristic3DBPPv1,
    "first_fit_decreasing_3d": FirstFitDecreasing3D,
    "extreme_points_3d": ExtremePoints3D,
    "best_fit_decreasing_3d": BestFitDecreasing3D,
    "single_container_constructive": SingleContainerConstructive,
    "weight_aware_container_loading": WeightAwareContainerLoading,
}

_DEFAULT_BASE_BY_PROBLEM: dict[ProblemType, str] = {
    ProblemType.THREE_D_BPP: "best_fit_decreasing_3d",
    ProblemType.SINGLE_CONTAINER_LOADING: "best_fit_decreasing_3d",
    ProblemType.CONTAINER_LOADING: "weight_aware_container_loading",
}


def default_base_algorithm(problem_type: ProblemType) -> str:
    """Constructivo base por defecto según el tipo de problema."""

    return _DEFAULT_BASE_BY_PROBLEM.get(
        problem_type, "best_fit_decreasing_3d"
    )


def resolve_base_algorithm(problem: PackingProblem) -> str:
    """Resuelve el constructivo base desde parámetros o el default del tipo."""

    explicit = problem.algorithm.parameters.get("base_algorithm")
    if explicit:
        return str(explicit)
    return default_base_algorithm(problem.problem_type)


def run_constructive_base(problem: PackingProblem, base_name: str) -> PackingSolution:
    """Ejecuta un constructivo interno reutilizando los parámetros del problema."""

    cls = _CONSTRUCTIVES.get(base_name)
    if cls is None:
        raise AlgorithmNotFoundError(
            f"Algoritmo constructivo base no soportado para mejora local: {base_name}"
        )
    meta = cls.metadata
    if problem.problem_type not in meta.problem_types:
        raise AlgorithmNotFoundError(
            f"El constructivo base '{base_name}' no soporta problem_type="
            f"{problem.problem_type.value}"
        )
    return cls().run(problem)
