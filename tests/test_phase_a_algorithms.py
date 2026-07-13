"""Tests Fase A: maximal_spaces_3d + heurísticas de mejora."""

from __future__ import annotations

import pytest

from packing_services.algorithms.best_fit_decreasing_3d import BestFitDecreasing3D
from packing_services.algorithms.bin_reduction import BinReduction
from packing_services.algorithms.maximal_spaces_3d import MaximalSpaces3D
from packing_services.algorithms.orientation_improvement import OrientationImprovement
from packing_services.algorithms.relocation_improvement import RelocationImprovement
from packing_services.algorithms.swap_improvement import SwapImprovement
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem


def _problem(items, algo_name, *, parameters=None, containers=None):
    return PackingProblem(
        problem_type="3D_BPP",
        containers=containers
        or [Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
        items=items,
        algorithm=AlgorithmConfig(name=algo_name, parameters=parameters or {}),
    )


@pytest.mark.parametrize(
    "algo_cls,name,parameters",
    [
        (MaximalSpaces3D, "maximal_spaces_3d", {"sort_strategy": "volume_desc"}),
        (
            RelocationImprovement,
            "relocation_improvement",
            {"base_algorithm": "best_fit_decreasing_3d", "relocation_passes": 2},
        ),
        (
            SwapImprovement,
            "swap_improvement",
            {"base_algorithm": "best_fit_decreasing_3d", "improvement_passes": 1},
        ),
        (
            OrientationImprovement,
            "orientation_improvement",
            {"base_algorithm": "best_fit_decreasing_3d", "improvement_passes": 1},
        ),
        (
            BinReduction,
            "bin_reduction",
            {"base_algorithm": "best_fit_decreasing_3d", "improvement_passes": 1},
        ),
    ],
)
def test_phase_a_algorithms_valid(algo_cls, name, parameters):
    items = [Item(id=f"I{i}", length=37, width=29, height=23, weight=2) for i in range(10)]
    solution = algo_cls().run(_problem(items, name, parameters=parameters))
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0
    assert solution.algorithm_name == name


def test_maximal_spaces_deterministic():
    items = [Item(id=f"I{i}", length=30, width=25, height=20, weight=1) for i in range(8)]
    params = {"sort_strategy": "volume_desc", "selection": "best_fit"}
    s1 = MaximalSpaces3D().run(_problem(items, "maximal_spaces_3d", parameters=params))
    s2 = MaximalSpaces3D().run(_problem(items, "maximal_spaces_3d", parameters=params))
    assert [p.position for p in s1.packed_items] == [p.position for p in s2.packed_items]


def test_improvement_algorithms_preserve_packed_count():
    items = [
        Item(id="P1", length=50, width=40, height=30, weight=6, quantity=1),
        Item(id="P2", length=60, width=30, height=40, weight=7, quantity=1),
    ]
    containers = [
        Container(id="C1", length=100, width=80, height=80, max_weight=500),
        Container(id="C2", length=100, width=80, height=80, max_weight=500),
    ]
    base = BestFitDecreasing3D().run(
        _problem(items, "best_fit_decreasing_3d", containers=containers)
    )
    for algo_cls, name in (
        (RelocationImprovement, "relocation_improvement"),
        (SwapImprovement, "swap_improvement"),
        (OrientationImprovement, "orientation_improvement"),
    ):
        sol = algo_cls().run(
            _problem(
                items,
                name,
                parameters={"base_algorithm": "best_fit_decreasing_3d"},
                containers=containers,
            )
        )
        assert sol.metrics.items_packed == base.metrics.items_packed
        assert sol.validation_report.is_valid
