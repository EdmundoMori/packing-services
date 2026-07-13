"""Endpoint de benchmark/comparación de algoritmos."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...domain.enums import ProblemType
from ...schemas.requests import BenchmarkRequest
from ...schemas.responses import BenchmarkResponse
from ...services.benchmark_service import BenchmarkService

router = APIRouter(tags=["benchmark"])
_service = BenchmarkService()


@router.get("/benchmark/profiles")
def list_benchmark_profiles(
    problem_type: ProblemType | None = Query(default=None),
) -> dict:
    """Lista perfiles estándar de benchmark (motores comparables por tipo de problema)."""

    return {"profiles": _service.list_profiles(problem_type)}


@router.post("/benchmark", response_model=BenchmarkResponse)
def benchmark(request: BenchmarkRequest) -> BenchmarkResponse:
    """Ejecuta varios algoritmos sobre la misma instancia y los compara."""

    return _service.benchmark(request)
