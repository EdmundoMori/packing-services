"""Endpoints del catálogo de algoritmos."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...algorithms.metadata import AlgorithmMetadata
from ...domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ...services.algorithm_catalog_service import AlgorithmCatalogService

router = APIRouter(tags=["algorithms"])
_service = AlgorithmCatalogService()


@router.get("/algorithms", response_model=list[AlgorithmMetadata])
def list_algorithms(
    problem_type: ProblemType | None = Query(default=None),
    family: AlgorithmFamily | None = Query(default=None),
    status: AlgorithmStatus | None = Query(default=None),
    supported_constraint: Constraint | None = Query(default=None),
) -> list[AlgorithmMetadata]:
    """Lista el catálogo completo de algoritmos con filtros opcionales."""

    return _service.list(
        problem_type=problem_type,
        family=family,
        status=status,
        supported_constraint=supported_constraint,
    )


@router.get("/algorithms/{algorithm_name}", response_model=AlgorithmMetadata)
def get_algorithm(algorithm_name: str) -> AlgorithmMetadata:
    """Devuelve los metadatos detallados de un algoritmo."""

    return _service.get(algorithm_name)
