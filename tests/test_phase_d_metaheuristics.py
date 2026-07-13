"""Tests Fase D: metaheurísticas 3D-BPP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packing_services.algorithms.metaheuristic_3d_bpp import METAHEURISTIC_ALGORITHMS
from packing_services.algorithms.registry import get_default_registry
from packing_services.api.main import app
from packing_services.domain.enums import AlgorithmFamily, AlgorithmStatus
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem
from packing_services.services.benchmark_service import BenchmarkService
from packing_services.schemas.requests import BenchmarkRequest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
client = TestClient(app)

META_NAMES = [algo.metadata.name for algo in METAHEURISTIC_ALGORITHMS]


def _small_problem(name: str, *, seed: int = 7, iterations: int = 8) -> PackingProblem:
    return PackingProblem(
        problem_type="3D_BPP",
        containers=[
            Container(id="C1", length=80, width=60, height=70, max_weight=500),
            Container(id="C2", length=80, width=60, height=70, max_weight=500),
        ],
        items=[
            Item(id="A1", length=30, width=25, height=20, weight=4),
            Item(id="A2", length=35, width=20, height=18, weight=5),
            Item(id="A3", length=28, width=22, height=24, weight=4),
            Item(id="A4", length=40, width=15, height=15, weight=3),
            Item(id="A5", length=25, width=25, height=25, weight=6),
        ],
        algorithm=AlgorithmConfig(
            name=name,
            random_seed=seed,
            time_limit_seconds=5,
            parameters={
                "base_algorithm": "best_fit_decreasing_3d",
                "iterations": iterations,
            },
        ),
    )


@pytest.mark.parametrize("name", META_NAMES)
def test_metaheuristic_registry_executable(name):
    registry = get_default_registry()
    meta = registry.get_metadata(name)
    assert meta.status == AlgorithmStatus.IMPLEMENTED
    assert meta.algorithm_family == AlgorithmFamily.METAHEURISTIC
    assert registry.is_executable(name)


@pytest.mark.parametrize("algo", METAHEURISTIC_ALGORITHMS)
def test_metaheuristic_produces_valid_solution(algo):
    solution = algo.run(_small_problem(algo.metadata.name))
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0
    assert solution.execution_metadata.parameters["base_algorithm_used"] == "best_fit_decreasing_3d"
    assert "metaheuristic" in solution.execution_metadata.parameters
    assert solution.execution_metadata.parameters["evaluations"] >= 1


@pytest.mark.parametrize("name", ["simulated_annealing_3d_bpp", "grasp_3d_bpp"])
def test_metaheuristic_reproducible_with_seed(name):
    registry = get_default_registry()
    p1 = _small_problem(name, seed=99, iterations=6)
    p2 = _small_problem(name, seed=99, iterations=6)
    s1 = registry.execute(name, p1)
    s2 = registry.execute(name, p2)
    assert s1.metrics.items_packed == s2.metrics.items_packed
    assert s1.metrics.items_unpacked == s2.metrics.items_unpacked


def test_metaheuristic_execute_api():
    payload = json.loads((EXAMPLES / "algorithm_execute_3d_bpp.json").read_text())
    payload["parameters"] = {
        "base_algorithm": "best_fit_decreasing_3d",
        "iterations": 5,
    }
    payload["random_seed"] = 11
    payload["time_limit_seconds"] = 5
    response = client.post(
        "/api/v1/algorithms/simulated_annealing_3d_bpp/execute",
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["solution"]["algorithm_name"] == "simulated_annealing_3d_bpp"
    assert body["solution"]["validation_report"]["is_valid"] is True


def test_benchmark_metaheuristic_profile():
    payload = json.loads((EXAMPLES / "benchmark_request.json").read_text())
    payload.pop("engines", None)
    payload["profile"] = "metaheuristic"
    request = BenchmarkRequest.model_validate(payload)
    service = BenchmarkService()
    response = service.benchmark(request)
    names = {r.engine for r in response.results}
    assert "simulated_annealing_3d_bpp" in names
    assert "best_fit_decreasing_3d" in names
    assert len(response.results) >= 3
