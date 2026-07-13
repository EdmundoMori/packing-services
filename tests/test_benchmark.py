"""Tests del servicio de benchmark/comparación."""

from __future__ import annotations

import json
from pathlib import Path

from packing_services.schemas.requests import (
    BenchmarkEngineConfig,
    BenchmarkRequest,
)
from packing_services.services.benchmark_service import BenchmarkService
from packing_services.domain.models import Container, Item
from packing_services.algorithms.registry import get_default_registry


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


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
    assert response.details["benchmark_group"] == "3D_BPP"
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


def test_benchmark_example_differentiates_algorithms():
    """El ejemplo ``benchmark_request.json`` debe separar motores en calidad."""

    data = json.loads((EXAMPLES / "benchmark_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    by_engine = {r.engine: r for r in response.results}

    assert by_engine["best_fit_decreasing_3d"].metrics.items_packed > by_engine["extreme_points_3d"].metrics.items_packed
    assert (
        by_engine["best_fit_decreasing_3d"].metrics.volume_utilization
        > by_engine["extreme_points_3d"].metrics.volume_utilization
    )
    internal = [
        r
        for r in response.results
        if r.engine
        in {
            "heuristic_3d_bpp_v1",
            "first_fit_decreasing_3d",
            "extreme_points_3d",
            "best_fit_decreasing_3d",
        }
    ]
    assert all(r.is_valid for r in internal)
    assert response.ranking[0] == "best_fit_decreasing_3d"


def test_benchmark_container_loading_group():
    data = json.loads((EXAMPLES / "benchmark_container_loading_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    assert response.details["benchmark_group"] == "CONTAINER_LOADING"
    assert response.details["benchmark_profile"] == "constructive"
    assert len(response.results) == 4
    engines = {r.engine: r for r in response.results}
    assert engines["single_container_constructive"].is_valid
    assert engines["weight_aware_container_loading"].is_valid
    # Deben diferenciarse en piezas empacadas o utilización.
    assert (
        engines["single_container_constructive"].metrics.items_packed
        != engines["weight_aware_container_loading"].metrics.items_packed
        or engines["single_container_constructive"].metrics.volume_utilization
        != engines["weight_aware_container_loading"].metrics.volume_utilization
    )


def test_benchmark_cartonization_group():
    data = json.loads((EXAMPLES / "benchmark_cartonization_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    assert response.details["benchmark_group"] == "CARTONIZATION"
    assert response.details["benchmark_profile"] == "box_selection"
    assert len(response.results) == 4
    for r in response.results:
        assert r.is_valid
        assert r.details.get("selected_box_id")
        assert r.details.get("evaluated_boxes")


def test_benchmark_includes_py3dbp_when_installed():
    registry = get_default_registry()
    if not registry.is_executable("py3dbp_adapter"):
        return

    data = json.loads((EXAMPLES / "benchmark_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    engines = {r.engine for r in response.results}
    assert "py3dbp_adapter" in engines
    py3 = next(r for r in response.results if r.engine == "py3dbp_adapter")
    assert py3.status != "error"
    assert py3.is_valid
