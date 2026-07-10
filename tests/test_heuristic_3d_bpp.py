"""Tests del algoritmo heuristic_3d_bpp_v1."""

from __future__ import annotations

from packing_services.domain.enums import SolutionStatus
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)
from packing_services.algorithms.heuristic_3d_bpp import Heuristic3DBPPv1


def _problem(items, containers=None):
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers or [Container(id="C1", length=100, width=100, height=100, max_weight=1000)],
        items=items,
        algorithm=AlgorithmConfig(name="heuristic_3d_bpp_v1"),
    )


def test_packs_all_items_that_fit():
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(8)]
    solution = Heuristic3DBPPv1().run(_problem(items))
    # 8 cubos de 50 caben exactamente en 100x100x100.
    assert solution.status == SolutionStatus.SUCCESS
    assert solution.metrics.items_packed == 8
    assert solution.metrics.items_unpacked == 0


def test_solution_is_always_valid():
    items = [Item(id=f"I{i}", length=40, width=30, height=20, weight=2) for i in range(10)]
    solution = Heuristic3DBPPv1().run(_problem(items))
    assert solution.validation_report is not None
    assert solution.validation_report.is_valid
    assert solution.metrics.constraint_violations == 0


def test_item_too_large_is_unpacked():
    items = [Item(id="TOO_BIG", length=200, width=200, height=200, weight=1)]
    solution = Heuristic3DBPPv1().run(_problem(items))
    assert solution.status == SolutionStatus.FAILED
    assert solution.metrics.items_unpacked == 1


def test_deterministic_output():
    items = [Item(id=f"I{i}", length=33, width=27, height=19, weight=1) for i in range(12)]
    s1 = Heuristic3DBPPv1().run(_problem(items))
    s2 = Heuristic3DBPPv1().run(_problem(items))
    assert s1.metrics.items_packed == s2.metrics.items_packed
    assert [p.position for p in s1.packed_items] == [p.position for p in s2.packed_items]


def test_weight_limit_respected():
    container = Container(id="C1", length=100, width=100, height=100, max_weight=25)
    items = [Item(id=f"I{i}", length=40, width=40, height=40, weight=10) for i in range(4)]
    solution = Heuristic3DBPPv1().run(_problem(items, [container]))
    assert solution.metrics.loaded_weight <= 25
    assert solution.validation_report.is_valid
