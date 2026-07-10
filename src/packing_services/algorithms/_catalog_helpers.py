"""Helpers para declarar metadatos de algoritmos aún no implementados.

Los algoritmos "future" y "stub" no tienen implementación ejecutable todavía,
pero sí deben aparecer en el catálogo con metadatos completos para que el
roadmap sea descubrible desde la API (``GET /api/v1/algorithms``).
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from .metadata import DEFAULT_METRICS, AlgorithmMetadata


def catalog_metadata(
    name: str,
    display_name: str,
    problem_types: list[ProblemType],
    family: AlgorithmFamily,
    status: AlgorithmStatus,
    description: str,
    *,
    deterministic: bool = True,
    supports_random_seed: bool = False,
    supports_time_limit: bool = False,
    supported_constraints: list[Constraint] | None = None,
    unsupported_constraints: list[Constraint] | None = None,
    limitations: list[str] | None = None,
    external_engine: str | None = None,
    external_language: str | None = None,
    external_repository: str | None = None,
    parameters: dict[str, str] | None = None,
) -> AlgorithmMetadata:
    """Construye una ficha de metadatos del catálogo con valores por defecto."""

    return AlgorithmMetadata(
        name=name,
        display_name=display_name,
        problem_types=problem_types,
        algorithm_family=family,
        status=status,
        description=description,
        deterministic=deterministic,
        supports_random_seed=supports_random_seed,
        supports_time_limit=supports_time_limit,
        supported_constraints=supported_constraints or [],
        unsupported_constraints=unsupported_constraints or [],
        parameters=parameters or {},
        metrics=DEFAULT_METRICS,
        limitations=limitations or ["No implementado en la versión actual"],
        external_engine=external_engine,
        external_language=external_language,
        external_repository=external_repository,
    )
