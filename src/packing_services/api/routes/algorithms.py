"""Endpoints del catálogo de algoritmos."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ...algorithms.metadata import AlgorithmMetadata
from ...domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ...schemas.responses import AlgorithmDetailResponse
from ...services.algorithm_catalog_service import AlgorithmCatalogService
from ...services.algorithm_input_service import AlgorithmInputService

router = APIRouter(tags=["algorithms"])
_service = AlgorithmCatalogService()
_input_service = AlgorithmInputService()


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


@router.get("/algorithms/{algorithm_name}", response_model=AlgorithmDetailResponse)
def get_algorithm(algorithm_name: str) -> AlgorithmDetailResponse:
    """Devuelve metadatos del algoritmo y su contrato de ejecución."""

    return _input_service.enrich_metadata(algorithm_name)


@router.get("/algorithms/{algorithm_name}/input-example")
def get_algorithm_input_example(
    algorithm_name: str,
    problem_type: ProblemType | None = Query(default=None),
) -> dict[str, Any]:
    """Devuelve un JSON de entrada normalizado listo para ``/execute``."""

    return _input_service.build_input_example(algorithm_name, problem_type)
