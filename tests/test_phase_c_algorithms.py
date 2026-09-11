"""Tests Fase C: palletization y stacking-aware."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packing_services.algorithms.layer_based_palletization import LayerBasedPalletization
from packing_services.algorithms.registry import get_default_registry
from packing_services.algorithms.stack_based_palletization import StackBasedPalletization
from packing_services.algorithms.stacking_aware_constructive import StackingAwareConstructive
from packing_services.api.main import app
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem
from packing_services.services.benchmark_service import BenchmarkService
from packing_services.services.palletization_service import PalletizationService
from packing_services.services.stacking_aware_service import StackingAwareService
from packing_services.schemas.requests import (
    BenchmarkRequest,
    PalletizationRequest,
    StackingAwareRequest,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
client = TestClient(app)


def _pallet_problem(items, algo_name, *, parameters=None):
    return PackingProblem(
        problem_type="PALLETIZATION",
        containers=[Container(id="P1", length=120, width=80, height=140, max_weight=800)],
        items=items,
        algorithm=AlgorithmConfig(name=algo_name, parameters=parameters or {}),
    )


def _stack_problem(items, algo_name, *, parameters=None, constraints=None):
    from packing_services.domain.models import ConstraintFlags

    return PackingProblem(
        problem_type="STACKING_AWARE",
        containers=[Container(id="P1", length=100, width=80, height=120, max_weight=500)],
        items=items,
        constraints=constraints
        or ConstraintFlags(basic_stability=True, load_bearing=True),
        algorithm=AlgorithmConfig(name=algo_name, parameters=parameters or {}),
    )


@pytest.mark.parametrize(
    "algo_cls,name",
    [
        (LayerBasedPalletization, "layer_based_palletization"),
        (StackBasedPalletization, "stack_based_palletization"),
    ],
)
def test_palletization_algorithms_valid(algo_cls, name):
    items = [Item(id=f"B{i}", length=35, width=28, height=22, weight=5) for i in range(6)]
    solution = algo_cls().run(_pallet_problem(items, name, parameters={"sort_strategy": "volume_desc"}))
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0
    assert solution.problem_type.value == "PALLETIZATION"


def test_stacking_aware_constructive_respects_load_bearing():
    items = [
        Item(id="BASE", length=50, width=40, height=20, weight=15, max_load_on_top=30),
        Item(id="LIGHT", length=40, width=30, height=15, weight=5),
        Item(id="HEAVY", length=40, width=30, height=15, weight=25),
    ]
    solution = StackingAwareConstructive().run(
        _stack_problem(
            items,
            "stacking_aware_constructive",
            parameters={"sort_strategy": "weight_desc", "min_support_ratio": 0.6},
        )
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed >= 2


def test_palletization_service_and_api():
    data = json.loads((EXAMPLES / "palletization_request.json").read_text())
    solution = PalletizationService().palletize(PalletizationRequest(**data))
    assert solution.validation_report.is_valid

    response = client.post("/api/v1/pack/palletization", json=data)
    assert response.status_code == 200
    assert response.json()["problem_type"] == "PALLETIZATION"


def test_stacking_aware_service_and_api():
    data = json.loads((EXAMPLES / "stacking_aware_request.json").read_text())
    solution = StackingAwareService().pack(StackingAwareRequest(**data))
    assert solution.validation_report.is_valid

    response = client.post("/api/v1/pack/stacking-aware", json=data)
    assert response.status_code == 200
    assert response.json()["problem_type"] == "STACKING_AWARE"


def test_algorithm_execute_palletization_and_stacking():
    for name, example in (
        ("layer_based_palletization", "algorithm_execute_palletization.json"),
        ("stacking_aware_constructive", "algorithm_execute_stacking_aware.json"),
    ):
        payload = json.loads((EXAMPLES / example).read_text())
        response = client.post(f"/api/v1/algorithms/{name}/execute", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["algorithm_name"] == name
        assert body["solution"]["validation_report"]["is_valid"] is True


def test_benchmark_palletization_and_stacking_profiles():
    for filename, group in (
        ("benchmark_palletization_request.json", "PALLETIZATION"),
        ("benchmark_stacking_aware_request.json", "STACKING_AWARE"),
    ):
        data = json.loads((EXAMPLES / filename).read_text())
        response = BenchmarkService().benchmark(BenchmarkRequest(**data))
        assert response.details["benchmark_group"] == group
        assert len(response.results) >= 2
        assert all(r.is_valid for r in response.results)


def test_registry_has_31_implemented():
    registry = get_default_registry()
    from packing_services.domain.enums import AlgorithmStatus

    implemented = registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED)
    assert len(implemented) == 31
