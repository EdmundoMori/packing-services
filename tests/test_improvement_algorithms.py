"""Tests de algoritmos de mejora local e híbridos (Semana 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packing_services.algorithms.best_fit_decreasing_3d import BestFitDecreasing3D
from packing_services.algorithms.constructive_plus_local_search import (
    ConstructivePlusLocalSearch,
)
from packing_services.algorithms.solution_compaction import SolutionCompaction
from packing_services.domain.enums import SolutionStatus
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)
from packing_services.schemas.requests import BenchmarkRequest
from packing_services.services.benchmark_service import BenchmarkService

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _problem(items, algo_name, *, parameters=None, containers=None):
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers
        or [Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
        items=items,
        algorithm=AlgorithmConfig(name=algo_name, parameters=parameters or {}),
    )


@pytest.mark.parametrize(
    "algo_cls,name",
    [
        (SolutionCompaction, "solution_compaction"),
        (ConstructivePlusLocalSearch, "constructive_plus_local_search"),
    ],
)
def test_improvement_algorithms_produce_valid_solutions(algo_cls, name):
    items = [Item(id=f"I{i}", length=37, width=29, height=23, weight=2) for i in range(12)]
    solution = algo_cls().run(_problem(items, name))
    assert solution.validation_report.is_valid
    assert solution.metrics.constraint_violations == 0
    assert solution.metrics.items_packed > 0


def test_compaction_moves_items_toward_origin():
    items = [Item(id=f"I{i}", length=30, width=25, height=20, weight=1) for i in range(6)]
    base = BestFitDecreasing3D().run(_problem(items, "best_fit_decreasing_3d"))
    compact = SolutionCompaction().run(
        _problem(
            items,
            "solution_compaction",
            parameters={"base_algorithm": "best_fit_decreasing_3d", "compaction_passes": 3},
        )
    )
    base_sum = sum(p.position.x + p.position.y + p.position.z for p in base.packed_items)
    compact_sum = sum(
        p.position.x + p.position.y + p.position.z for p in compact.packed_items
    )
    assert compact_sum <= base_sum + 1e-6
    assert compact.execution_metadata.parameters["items_relocated"] >= 0


def test_hybrid_keeps_same_packed_count_as_base_on_demo():
    items = [
        Item(id="P1", length=50, width=40, height=30, weight=6, quantity=1),
        Item(id="P2", length=60, width=30, height=40, weight=7, quantity=1),
        Item(id="P3", length=45, width=45, height=25, weight=5, quantity=1),
    ]
    containers = [
        Container(id="C1", length=100, width=80, height=80, max_weight=500),
        Container(id="C2", length=100, width=80, height=80, max_weight=500),
    ]
    base = BestFitDecreasing3D().run(
        _problem(items, "best_fit_decreasing_3d", containers=containers)
    )
    hybrid = ConstructivePlusLocalSearch().run(
        _problem(
            items,
            "constructive_plus_local_search",
            parameters={"base_algorithm": "best_fit_decreasing_3d"},
            containers=containers,
        )
    )
    assert hybrid.metrics.items_packed == base.metrics.items_packed
    assert hybrid.validation_report.is_valid


def test_benchmark_hybrid_example_runs():
    data = json.loads((EXAMPLES / "benchmark_hybrid_request.json").read_text())
    response = BenchmarkService().benchmark(BenchmarkRequest(**data))
    assert response.details["benchmark_group"] == "3D_BPP"
    assert len(response.results) == 3
    assert all(r.is_valid for r in response.results)
    by_engine = {r.engine: r for r in response.results}
    assert by_engine["best_fit_decreasing_3d"].metrics.items_packed == by_engine[
        "solution_compaction"
    ].metrics.items_packed


def test_compaction_deterministic():
    items = [Item(id=f"I{i}", length=31, width=27, height=19, weight=1) for i in range(10)]
    params = {"base_algorithm": "best_fit_decreasing_3d", "compaction_passes": 2}
    s1 = SolutionCompaction().run(_problem(items, "solution_compaction", parameters=params))
    s2 = SolutionCompaction().run(_problem(items, "solution_compaction", parameters=params))
    assert [p.position for p in s1.packed_items] == [p.position for p in s2.packed_items]
