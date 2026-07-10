"""Tests de extreme_points_3d y best_fit_decreasing_3d (motor de puntos extremos)."""

from __future__ import annotations

import pytest

from packing_services.algorithms.best_fit_decreasing_3d import BestFitDecreasing3D
from packing_services.algorithms.extreme_points_3d import ExtremePoints3D
from packing_services.domain.enums import SolutionStatus
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)


def _problem(items, algo_name, containers=None):
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers
        or [Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
        items=items,
        algorithm=AlgorithmConfig(name=algo_name),
    )


@pytest.mark.parametrize("algo_cls,name", [
    (ExtremePoints3D, "extreme_points_3d"),
    (BestFitDecreasing3D, "best_fit_decreasing_3d"),
])
def test_packs_all_items_that_fit(algo_cls, name):
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(8)]
    solution = algo_cls().run(_problem(items, name))
    assert solution.status == SolutionStatus.SUCCESS
    assert solution.metrics.items_packed == 8
    assert solution.validation_report.is_valid
    assert solution.metrics.constraint_violations == 0


@pytest.mark.parametrize("algo_cls,name", [
    (ExtremePoints3D, "extreme_points_3d"),
    (BestFitDecreasing3D, "best_fit_decreasing_3d"),
])
def test_solution_always_valid(algo_cls, name):
    items = [Item(id=f"I{i}", length=37, width=29, height=23, weight=2) for i in range(15)]
    solution = algo_cls().run(_problem(items, name))
    assert solution.validation_report.is_valid
    assert solution.metrics.constraint_violations == 0


@pytest.mark.parametrize("algo_cls,name", [
    (ExtremePoints3D, "extreme_points_3d"),
    (BestFitDecreasing3D, "best_fit_decreasing_3d"),
])
def test_deterministic(algo_cls, name):
    items = [Item(id=f"I{i}", length=31, width=27, height=19, weight=1) for i in range(12)]
    s1 = algo_cls().run(_problem(items, name))
    s2 = algo_cls().run(_problem(items, name))
    assert [p.position for p in s1.packed_items] == [p.position for p in s2.packed_items]


def test_first_item_placed_at_origin():
    items = [Item(id="I1", length=40, width=30, height=20, weight=1)]
    solution = ExtremePoints3D().run(_problem(items, "extreme_points_3d"))
    pos = solution.packed_items[0].position
    assert (pos.x, pos.y, pos.z) == (0, 0, 0)


def test_extreme_points_stacks_when_needed():
    # Contenedor plano en x/y pero alto: obliga a apilar en z.
    container = Container(id="C1", length=50, width=50, height=200, max_weight=100000)
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(4)]
    solution = ExtremePoints3D().run(_problem(items, "extreme_points_3d", [container]))
    assert solution.metrics.items_packed == 4
    zs = sorted(p.position.z for p in solution.packed_items)
    assert zs == [0, 50, 100, 150]  # apilados correctamente
    assert solution.validation_report.is_valid
