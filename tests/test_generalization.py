"""Validación de generalización: algoritmos funcionan con instancias arbitrarias por tipo."""

from __future__ import annotations

import pytest

from packing_services.algorithms.registry import get_default_registry
from packing_services.domain.enums import ProblemType
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem
from packing_services.schemas.requests import BoxOption
from packing_services.utils.errors import InvalidInputError


def _expand(items: list[Item]) -> list[Item]:
    out: list[Item] = []
    for it in items:
        if it.quantity == 1:
            out.append(it)
        else:
            for n in range(1, it.quantity + 1):
                out.append(it.model_copy(update={"id": f"{it.id}#{n}", "quantity": 1}))
    return out


def _problem(pt: ProblemType, containers, items, algo: str, **params):
    return PackingProblem(
        problem_type=pt,
        containers=containers,
        items=_expand(items),
        algorithm=AlgorithmConfig(name=algo, parameters=params),
    )


@pytest.mark.parametrize(
    "algo",
    [
        "heuristic_3d_bpp_v1",
        "first_fit_decreasing_3d",
        "best_fit_decreasing_3d",
        "extreme_points_3d",
    ],
)
def test_3d_bpp_works_with_arbitrary_instance(algo: str):
    registry = get_default_registry()
    problem = _problem(
        ProblemType.THREE_D_BPP,
        [Container(id="BIN", length=90, width=70, height=60, max_weight=400)],
        [Item(id="SKU", length=30, width=25, height=20, weight=2, quantity=5)],
        algo,
    )
    sol = registry.execute(algo, problem)
    assert sol.validation_report.is_valid
    assert sol.metrics.items_packed > 0


def test_container_loading_compaction_default_base():
    registry = get_default_registry()
    problem = _problem(
        ProblemType.CONTAINER_LOADING,
        [
            Container(id="T1", length=100, width=80, height=70, max_weight=300),
            Container(id="T2", length=100, width=80, height=70, max_weight=300),
        ],
        [Item(id="L1", length=40, width=30, height=25, weight=12, quantity=3)],
        "solution_compaction",
    )
    sol = registry.execute("solution_compaction", problem)
    assert sol.validation_report.is_valid
    assert sol.execution_metadata.parameters["base_algorithm_used"] == (
        "weight_aware_container_loading"
    )


@pytest.mark.parametrize(
    "algo",
    [
        "smallest_feasible_box",
        "best_box_volume_utilization",
        "first_fit_box",
        "largest_feasible_box",
    ],
)
def test_cartonization_with_arbitrary_catalog(algo: str):
    registry = get_default_registry()
    boxes = [
        BoxOption(id="S", length=35, width=25, height=20, max_weight=10),
        BoxOption(id="L", length=60, width=45, height=40, max_weight=25),
    ]
    problem = PackingProblem(
        problem_type=ProblemType.CARTONIZATION,
        containers=[b.to_container() for b in boxes],
        items=_expand([Item(id="O1", length=15, width=12, height=10, weight=1, quantity=3)]),
        algorithm=AlgorithmConfig(name=algo),
    )
    sol = registry.execute(algo, problem)
    assert sol.validation_report.is_valid


def test_registry_rejects_incompatible_problem_type():
    registry = get_default_registry()
    problem = _problem(
        ProblemType.THREE_D_BPP,
        [Container(id="C", length=50, width=50, height=50)],
        [Item(id="I", length=10, width=10, height=10)],
        "smallest_feasible_box",
    )
    with pytest.raises(InvalidInputError, match="no soporta problem_type"):
        registry.execute("smallest_feasible_box", problem)
