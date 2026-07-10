"""Tests del servicio de benchmark/comparación."""

from __future__ import annotations

from packing_services.schemas.requests import (
    BenchmarkEngineConfig,
    BenchmarkRequest,
)
from packing_services.services.benchmark_service import BenchmarkService
from packing_services.domain.models import Container, Item


def _request(engines):
    return BenchmarkRequest(
        problem_type="3D_BPP",
        request_id="bench-test",
        containers=[Container(id="C1", length=100, width=100, height=100, max_weight=1000)],
        items=[
            Item(id="I1", length=40, width=40, height=40, weight=10, quantity=4),
            Item(id="I2", length=60, width=40, height=50, weight=15, quantity=3),
        ],
        engines=engines,
    )


def test_benchmark_compares_two_algorithms():
    request = _request(
        [
            BenchmarkEngineConfig(name="heuristic_3d_bpp_v1"),
            BenchmarkEngineConfig(name="first_fit_decreasing_3d"),
        ]
    )
    response = BenchmarkService().benchmark(request)
    assert len(response.results) == 2
    assert len(response.ranking) == 2
    assert response.ranking_explanation
    assert all(r.is_valid for r in response.results)


def test_benchmark_handles_failing_engine():
    # Un stub adapter no disponible debe reportarse como error, sin romper todo.
    request = _request(
        [
            BenchmarkEngineConfig(name="heuristic_3d_bpp_v1"),
            BenchmarkEngineConfig(name="skjolber_adapter"),
        ]
    )
    response = BenchmarkService().benchmark(request)
    statuses = {r.engine: r.status for r in response.results}
    assert statuses["skjolber_adapter"] == "error"
    # El motor válido debe quedar por delante del que falla.
    assert response.ranking[0] == "heuristic_3d_bpp_v1"


def test_ranking_prefers_valid_solutions():
    request = _request(
        [
            BenchmarkEngineConfig(name="skjolber_adapter"),
            BenchmarkEngineConfig(name="heuristic_3d_bpp_v1"),
        ]
    )
    response = BenchmarkService().benchmark(request)
    assert response.ranking[0] == "heuristic_3d_bpp_v1"
