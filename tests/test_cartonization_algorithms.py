"""Tests de algoritmos de cartonization."""

from __future__ import annotations

import pytest

from packing_services.algorithms.cartonization import (
    BestBoxVolumeUtilization,
    FirstFitBox,
    LargestFeasibleBox,
    SmallestFeasibleBox,
)
from packing_services.domain.models import (
    AlgorithmConfig,
    Container,
    Item,
    PackingProblem,
)


def _carton_problem(items, algo_name, boxes=None):
    boxes = boxes or [
        Container(id="BOX_S", length=40, width=30, height=25, max_weight=15),
        Container(id="BOX_M", length=55, width=45, height=40, max_weight=25),
        Container(id="BOX_L", length=70, width=55, height=60, max_weight=40),
    ]
    expanded: list[Item] = []
    for item in items:
        if item.quantity == 1:
            expanded.append(item)
        else:
            for n in range(1, item.quantity + 1):
                expanded.append(item.model_copy(update={"id": f"{item.id}#{n}", "quantity": 1}))
    return PackingProblem(
        problem_type="CARTONIZATION",
        containers=boxes,
        items=expanded,
        algorithm=AlgorithmConfig(name=algo_name),
    )


@pytest.mark.parametrize(
    "algo_cls,name",
    [
        (SmallestFeasibleBox, "smallest_feasible_box"),
        (BestBoxVolumeUtilization, "best_box_volume_utilization"),
        (FirstFitBox, "first_fit_box"),
        (LargestFeasibleBox, "largest_feasible_box"),
    ],
)
def test_cartonization_algorithms_valid(algo_cls, name):
    items = [Item(id="P5", length=20, width=20, height=20, weight=2, quantity=6)]
    solution = algo_cls().run(_carton_problem(items, name))
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == 6


def test_smallest_vs_largest_pick_different_boxes():
    items = [Item(id="P5", length=20, width=20, height=20, weight=2, quantity=6)]
    small = SmallestFeasibleBox().run(_carton_problem(items, "smallest_feasible_box"))
    large = LargestFeasibleBox().run(_carton_problem(items, "largest_feasible_box"))
    small_box = small.packed_items[0].container_id
    large_box = large.packed_items[0].container_id
    assert small_box == "BOX_M"
    assert large_box == "BOX_L"
    assert small.metrics.volume_utilization > large.metrics.volume_utilization
