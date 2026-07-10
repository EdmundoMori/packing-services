"""Tests del algoritmo first_fit_decreasing_3d."""

from __future__ import annotations

from packing_services.algorithms.first_fit_decreasing_3d import FirstFitDecreasing3D
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)


def _problem(items, containers):
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers,
        items=items,
        algorithm=AlgorithmConfig(name="first_fit_decreasing_3d"),
    )


def test_first_fit_fills_first_container_first():
    containers = [
        Container(id="C1", length=100, width=100, height=100, max_weight=1000),
        Container(id="C2", length=100, width=100, height=100, max_weight=1000),
    ]
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(4)]
    solution = FirstFitDecreasing3D().run(_problem(items, containers))
    # 4 cubos de 50 caben en un solo contenedor (2x2x1 en la base).
    used = {p.container_id for p in solution.packed_items}
    assert used == {"C1"}
    assert solution.validation_report.is_valid


def test_overflow_uses_second_container():
    containers = [
        Container(id="C1", length=100, width=100, height=50, max_weight=1000),
        Container(id="C2", length=100, width=100, height=50, max_weight=1000),
    ]
    # 8 cubos de 50: 4 por contenedor de altura 50.
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(8)]
    solution = FirstFitDecreasing3D().run(_problem(items, containers))
    assert solution.metrics.items_packed == 8
    assert solution.metrics.containers_used == 2
    assert solution.validation_report.is_valid
