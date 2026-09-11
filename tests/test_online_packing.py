"""Packing online: bucle general, heurístico ejecutable y BED-BPP."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packing_services.algorithms.best_fit_decreasing_3d import BestFitDecreasing3D
from packing_services.algorithms.extreme_points_3d import ExtremePoints3D
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.algorithms.registry import get_default_registry
from packing_services.api.main import app
from packing_services.datasets.bed_bpp import convert_order_to_pack_input
from packing_services.domain.enums import AlgorithmStatus, ProblemType, SortStrategy
from packing_services.domain.models import (
    AlgorithmConfig,
    ConstraintFlags,
    Container,
    Item,
    PackingProblem,
)
from packing_services.online.budget import InformationBudget

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE = EXAMPLES / "5_bed-bpp.json"


def _problem(items, *, parameters=None, containers=None, problem_type="3D_BPP", constraints=None):
    return PackingProblem(
        problem_type=problem_type,
        containers=containers
        or [Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
        items=items,
        constraints=constraints or ConstraintFlags(),
        algorithm=AlgorithmConfig(
            name="online_3d_bpp_heuristic",
            parameters=parameters or {},
        ),
    )


def test_registry_marks_heuristic_implemented():
    registry = get_default_registry()
    meta = registry.get_metadata("online_3d_bpp_heuristic")
    assert meta.status == AlgorithmStatus.IMPLEMENTED
    assert registry.is_executable("online_3d_bpp_heuristic")
    assert [m.value for m in meta.packing_modes] == ["online"]
    assert ProblemType.PALLETIZATION in meta.problem_types


def test_information_budget_clamps_and_sees_buffer():
    budget = InformationBudget.from_parameters({"lookahead_p": 0, "select_s": "2"})
    assert budget.observe_p == 1
    assert budget.select_s == 2
    s, p = budget.window(5)
    assert s == 2
    assert p == 2  # se observa al menos el buffer


def test_o3dbp_blb_matches_extreme_points_input_order():
    items = [
        Item(id=f"I{i}", length=31, width=27, height=19, weight=1, arrival_index=i)
        for i in range(1, 13)
    ]
    online = Online3DBPPHeuristic().run(
        _problem(items, parameters={"selection": "blb", "lookahead_p": 1, "select_s": 1})
    )
    offline_same_order = ExtremePoints3D().run(
        PackingProblem(
            problem_type="3D_BPP",
            containers=[Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
            items=items,
            algorithm=AlgorithmConfig(
                name="extreme_points_3d",
                parameters={"sort_strategy": SortStrategy.INPUT_ORDER.value},
            ),
        )
    )
    assert online.validation_report.is_valid
    assert [
        (p.item_id, p.position, p.orientation) for p in online.packed_items
    ] == [
        (p.item_id, p.position, p.orientation) for p in offline_same_order.packed_items
    ]


def test_o3dbp_best_fit_matches_bfd_input_order():
    items = [
        Item(id=f"I{i}", length=37, width=29, height=23, weight=2, arrival_index=i)
        for i in range(1, 11)
    ]
    online = Online3DBPPHeuristic().run(
        _problem(
            items,
            parameters={"selection": "best_fit", "lookahead_p": 1, "select_s": 1},
        )
    )
    bfd = BestFitDecreasing3D().run(
        PackingProblem(
            problem_type="3D_BPP",
            containers=[Container(id="C1", length=100, width=100, height=100, max_weight=100000)],
            items=items,
            algorithm=AlgorithmConfig(
                name="best_fit_decreasing_3d",
                parameters={"sort_strategy": SortStrategy.INPUT_ORDER.value},
            ),
        )
    )
    assert online.validation_report.is_valid
    assert [
        (p.item_id, p.position, p.orientation) for p in online.packed_items
    ] == [
        (p.item_id, p.position, p.orientation) for p in bfd.packed_items
    ]


def test_select_s_can_pack_later_item_first():
    """s=1 coloca I1 (6) y deja un hueco de 4; I2/I3 (5) no caben. s=2 elige I2+I3."""

    containers = [Container(id="C1", length=10, width=10, height=10, max_weight=1000)]
    items = [
        Item(id="I1", length=6, width=10, height=10, weight=1, arrival_index=1),
        Item(id="I2", length=5, width=10, height=10, weight=1, arrival_index=2),
        Item(id="I3", length=5, width=10, height=10, weight=1, arrival_index=3),
    ]
    no_rot = ConstraintFlags(allow_rotation=False)
    strict = Online3DBPPHeuristic().run(
        _problem(
            items,
            parameters={"lookahead_p": 1, "select_s": 1, "selection": "blb"},
            containers=containers,
            constraints=no_rot,
        )
    )
    buffered = Online3DBPPHeuristic().run(
        _problem(
            items,
            parameters={"lookahead_p": 3, "select_s": 2, "selection": "blb"},
            containers=containers,
            constraints=no_rot,
        )
    )
    assert strict.metrics.items_packed == 1
    assert {p.item_id for p in strict.packed_items} == {"I1"}
    assert buffered.metrics.items_packed == 2
    assert {p.item_id for p in buffered.packed_items} == {"I2", "I3"}
    assert buffered.packed_items[0].item_id == "I2"
    assert buffered.validation_report.is_valid


def test_online_respects_arrival_and_is_deterministic():
    items = [
        Item(id="B", length=20, width=20, height=20, weight=1, arrival_index=2),
        Item(id="A", length=20, width=20, height=20, weight=1, arrival_index=1),
        Item(id="C", length=20, width=20, height=20, weight=1, arrival_index=3),
    ]
    params = {"lookahead_p": 1, "select_s": 1, "selection": "best_fit"}
    s1 = Online3DBPPHeuristic().run(_problem(items, parameters=params))
    s2 = Online3DBPPHeuristic().run(_problem(items, parameters=params))
    assert [p.item_id for p in s1.packed_items] == ["A", "B", "C"]
    assert [p.position for p in s1.packed_items] == [p.position for p in s2.packed_items]
    assert s1.validation_report.is_valid


def test_execute_requires_online_mode():
    payload = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 50, "width": 50, "height": 50, "max_weight": 1000}],
        "items": [{"id": "I1", "length": 10, "width": 10, "height": 10, "weight": 1, "quantity": 1}],
    }
    # Algoritmo solo-online: si no envía packing_mode, el execute usa online.
    omitted = client.post("/api/v1/algorithms/online_3d_bpp_heuristic/execute", json=payload)
    assert omitted.status_code == 200, omitted.text
    payload["packing_mode"] = "offline"
    denied = client.post("/api/v1/algorithms/online_3d_bpp_heuristic/execute", json=payload)
    assert denied.status_code == 422
    payload["packing_mode"] = "online"
    ok = client.post("/api/v1/algorithms/online_3d_bpp_heuristic/execute", json=payload)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["solution"]["validation_report"]["is_valid"] is True
    assert body["solution"]["metrics"]["items_packed"] == 1
    used = body["solution"]["execution_metadata"]["parameters"]
    assert used["sort_strategy"] == "input_order"
    assert used["lookahead_p"] == 1
    assert used["select_s"] == 1


def test_execute_bed_bpp_online_heuristic():
    orders = json.loads(SAMPLE.read_text(encoding="utf-8"))
    order_id = min(orders.items(), key=lambda kv: len(kv[1]["item_sequence"]))[0]
    converted = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=ProblemType.PALLETIZATION,
        packing_mode="online",
        parameters={"lookahead_p": 1, "select_s": 1, "selection": "best_fit"},
    )
    payload = {
        "input_format": "bed_bpp",
        "order_id": order_id,
        "orders": orders,
        "problem_type": "PALLETIZATION",
        "packing_mode": "online",
        "parameters": {"lookahead_p": 1, "select_s": 1, "selection": "best_fit"},
    }
    response = client.post(
        "/api/v1/algorithms/online_3d_bpp_heuristic/execute",
        json=payload,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["solution"]["validation_report"]["is_valid"] is True
    assert data["solution"]["metrics"]["items_packed"] >= 1
    arrivals = {it["id"]: it["arrival_index"] for it in converted["items"]}
    packed_arrivals = [
        arrivals[p["item_id"]] for p in data["solution"]["packed_items"]
    ]
    assert packed_arrivals == sorted(packed_arrivals)


def test_catalog_online_lists_executable_heuristic():
    response = client.get(
        "/api/v1/algorithms",
        params={"packing_mode": "online", "status": "implemented"},
    )
    assert response.status_code == 200
    names = {a["name"] for a in response.json()}
    assert "online_3d_bpp_heuristic" in names
    detail = client.get("/api/v1/algorithms/online_3d_bpp_heuristic").json()
    assert detail["is_executable"] is True
    assert detail["packing_modes"] == ["online"]
    assert detail["status"] == "implemented"
