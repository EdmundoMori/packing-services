"""Tests de single_container_constructive."""

from __future__ import annotations

from packing_services.algorithms.single_container import SingleContainerConstructive
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)


def _problem(items, containers):
    return PackingProblem(
        problem_type="SINGLE_CONTAINER_LOADING",
        containers=containers,
        items=items,
        algorithm=AlgorithmConfig(name="single_container_constructive"),
    )


def test_uses_only_first_container():
    containers = [
        Container(id="C1", length=100, width=100, height=100, max_weight=100000),
        Container(id="C2", length=100, width=100, height=100, max_weight=100000),
    ]
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(8)]
    solution = SingleContainerConstructive().run(_problem(items, containers))
    used = {p.container_id for p in solution.packed_items}
    assert used == {"C1"}
    assert solution.metrics.containers_used == 1
    assert solution.validation_report.is_valid


def test_reports_unpacked_when_overflow():
    containers = [Container(id="C1", length=50, width=50, height=50, max_weight=100000)]
    # Solo cabe 1 cubo de 50; el resto queda sin cargar.
    items = [Item(id=f"I{i}", length=50, width=50, height=50, weight=1) for i in range(3)]
    solution = SingleContainerConstructive().run(_problem(items, containers))
    assert solution.metrics.items_packed == 1
    assert solution.metrics.items_unpacked == 2
    assert solution.validation_report.is_valid
