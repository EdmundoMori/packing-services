"""Tests Fase B: multi_box_cartonization, wall_building_3d, py3dbp_adapter."""

from __future__ import annotations

import pytest

from packing_services.algorithms.multi_box_cartonization import MultiBoxCartonization
from packing_services.algorithms.registry import get_default_registry
from packing_services.algorithms.wall_building_3d import WallBuilding3D
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem
from packing_services.schemas.requests import BoxOption


def _pack_problem(items, algo_name, *, parameters=None, containers=None, problem_type="3D_BPP"):
    return PackingProblem(
        problem_type=problem_type,
        containers=containers
        or [Container(id="C1", length=120, width=80, height=100, max_weight=500)],
        items=items,
        algorithm=AlgorithmConfig(name=algo_name, parameters=parameters or {}),
    )


def test_wall_building_3d_valid():
    items = [
        Item(id=f"I{i}", length=30, width=20, height=25, weight=5, quantity=1)
        for i in range(8)
    ]
    solution = WallBuilding3D().run(
        _pack_problem(
            items,
            "wall_building_3d",
            problem_type="CONTAINER_LOADING",
            containers=[
                Container(id="T1", length=100, width=80, height=90, max_weight=200),
            ],
        )
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0
    for packed in solution.packed_items:
        assert packed.position.y >= -1e-6


def test_wall_building_opens_successive_walls():
    """La segunda pared debe arrancar en y > 0 cuando la primera se llena."""

    items = [
        Item(id=f"W{i}", length=40, width=20, height=40, weight=4, quantity=1)
        for i in range(4)
    ]
    solution = WallBuilding3D().run(
        _pack_problem(
            items,
            "wall_building_3d",
            problem_type="CONTAINER_LOADING",
            containers=[
                Container(id="T1", length=40, width=80, height=40, max_weight=200),
            ],
        )
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == 4
    wall_ys = {round(p.position.y, 6) for p in solution.packed_items}
    assert 0.0 in wall_ys
    assert any(y > 1e-6 for y in wall_ys)


def test_wall_building_3d_deterministic():
    items = [Item(id="A", length=40, width=30, height=20, weight=3)]
    problem = _pack_problem(
        items,
        "wall_building_3d",
        problem_type="CONTAINER_LOADING",
        containers=[Container(id="T", length=80, width=60, height=70, max_weight=50)],
    )
    a = WallBuilding3D().run(problem)
    b = WallBuilding3D().run(problem)
    assert a.packed_items == b.packed_items


def test_multi_box_cartonization_uses_multiple_boxes():
    boxes = [
        BoxOption(id="S", length=18, width=16, height=14, max_weight=10),
        BoxOption(id="M", length=40, width=30, height=25, max_weight=20),
    ]
    items = [
        Item(id="A", length=16, width=14, height=12, weight=2, quantity=4),
        Item(id="B", length=15, width=13, height=11, weight=1, quantity=3),
    ]
    problem = PackingProblem(
        problem_type="CARTONIZATION",
        containers=[b.to_container() for b in boxes],
        items=items,
        algorithm=AlgorithmConfig(
            name="multi_box_cartonization",
            parameters={"sort_strategy": "volume_desc", "box_selection": "smallest_first"},
        ),
    )
    solution = MultiBoxCartonization().run(problem)
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == len(items)
    box_ids = {p.container_id for p in solution.packed_items}
    assert len(box_ids) >= 2
    assert solution.execution_metadata.parameters["boxes_used"] >= 2


def test_multi_box_cartonization_best_utilization_strategy():
    boxes = [
        BoxOption(id="S", length=22, width=18, height=12, max_weight=8),
        BoxOption(id="L", length=50, width=40, height=30, max_weight=30),
    ]
    items = [Item(id="X", length=20, width=15, height=10, weight=1, quantity=5)]
    problem = PackingProblem(
        problem_type="CARTONIZATION",
        containers=[b.to_container() for b in boxes],
        items=items,
        algorithm=AlgorithmConfig(
            name="multi_box_cartonization",
            parameters={"sort_strategy": "volume_desc", "box_selection": "best_utilization"},
        ),
    )
    solution = MultiBoxCartonization().run(problem)
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0


def test_py3dbp_adapter_execute_when_installed():
    registry = get_default_registry()
    if not registry.is_executable("py3dbp_adapter"):
        pytest.skip("py3dbp no instalado")

    from packing_services.adapters.py3dbp_adapter import Py3dbpAdapter

    assert Py3dbpAdapter().is_available()

    problem = _pack_problem(
        [Item(id="I1", length=30, width=20, height=15, weight=2, quantity=3)],
        "py3dbp_adapter",
        parameters={"bigger_first": True, "distribute_items": True},
    )
    solution = registry.execute("py3dbp_adapter", problem)
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed > 0
