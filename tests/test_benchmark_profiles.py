"""Tests de perfiles estándar de benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packing_services.benchmark.profiles import list_profiles, resolve_profile_engines
from packing_services.domain.enums import ProblemType
from packing_services.schemas.requests import BenchmarkRequest
from packing_services.services.benchmark_service import BenchmarkService

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_list_profiles_includes_all_problem_types():
    profiles = list_profiles()
    problem_types = {p["problem_type"] for p in profiles}
    assert "3D_BPP" in problem_types
    assert "CONTAINER_LOADING" in problem_types
    assert "CARTONIZATION" in problem_types
    assert "SINGLE_CONTAINER_LOADING" in problem_types
    for p in profiles:
        assert p["engines_count"] >= 2


def test_resolve_profile_engines_minimum_two():
    engines = resolve_profile_engines(ProblemType.CARTONIZATION, "box_selection")
    assert len(engines) >= 2
    names = {e.name for e in engines}
    assert "smallest_feasible_box" in names
    assert "largest_feasible_box" in names


def test_benchmark_request_with_profile_only():
    data = {
        "problem_type": "CARTONIZATION",
        "profile": "box_selection",
        "items": [{"id": "P5", "length": 20, "width": 20, "height": 20, "weight": 2, "quantity": 6}],
        "boxes": [
            {"id": "BOX_S", "length": 40, "width": 30, "height": 25, "max_weight": 15},
            {"id": "BOX_M", "length": 55, "width": 45, "height": 40, "max_weight": 25},
            {"id": "BOX_L", "length": 70, "width": 55, "height": 60, "max_weight": 40},
        ],
    }
    req = BenchmarkRequest(**data)
    assert len(req.engines) >= 2


def test_benchmark_profile_cartonization_differentiates_boxes():
    data = json.loads((EXAMPLES / "benchmark_cartonization_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    boxes = {r.details["selected_box_id"] for r in response.results}
    assert "BOX_M" in boxes
    assert "BOX_L" in boxes
    assert len(boxes) >= 2


def test_benchmark_single_container_profile():
    data = json.loads((EXAMPLES / "benchmark_single_container_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    assert response.details["benchmark_group"] == "SINGLE_CONTAINER_LOADING"
    assert response.details["benchmark_profile"] == "constructive"
    assert len(response.results) == 3
    assert all(r.is_valid for r in response.results)


def test_resolve_profile_metaheuristic_3d_bpp():
    engines = resolve_profile_engines(ProblemType.THREE_D_BPP, "metaheuristic")
    assert len(engines) >= 3
    names = {e.name for e in engines}
    assert "simulated_annealing_3d_bpp" in names
    assert "best_fit_decreasing_3d" in names


def test_benchmark_request_requires_engines_or_profile():
    with pytest.raises(ValueError, match="engines"):
        BenchmarkRequest(
            problem_type="3D_BPP",
            containers=[{"id": "C1", "length": 10, "width": 10, "height": 10}],
            items=[{"id": "I1", "length": 5, "width": 5, "height": 5}],
        )
