"""Endpoint de benchmark/comparación de algoritmos."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import BenchmarkRequest
from ...schemas.responses import BenchmarkResponse
from ...services.benchmark_service import BenchmarkService

router = APIRouter(tags=["benchmark"])
_service = BenchmarkService()


@router.post("/benchmark", response_model=BenchmarkResponse)
def benchmark(request: BenchmarkRequest) -> BenchmarkResponse:
    """Ejecuta varios algoritmos sobre la misma instancia y los compara."""

    return _service.benchmark(request)
