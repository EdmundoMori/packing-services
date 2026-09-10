"""Experimento conjunto: un euro-pallet, cuatro tipos de servicio, input_order."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packing_services.api.main import app
from packing_services.benchmark.joint_single_container import (
    DEFAULT_SORT,
    JOINT_ENGINES,
    JOINT_PROBLEM_TYPES,
    build_joint_instance,
    run_joint_single_container,
)
from packing_services.datasets.bed_bpp import TARGET_SIZES_MM, smallest_order_id
from packing_services.domain.enums import ProblemType

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE = EXAMPLES / "5_bed-bpp.json"


def _orders() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_smallest_order_is_euro_pallet_sample():
    orders = _orders()
    assert smallest_order_id(orders) == "00100408"
    assert orders["00100408"]["properties"]["target"] == "euro-pallet"


def test_build_joint_instance_forces_euro_pallet():
    orders = _orders()
    order_id, payload = build_joint_instance(orders, target="euro-pallet")
    assert order_id == "00100408"
    assert len(payload["containers"]) == 1
    c = payload["containers"][0]
    assert (c["length"], c["width"], c["height"]) == TARGET_SIZES_MM["euro-pallet"]
    assert payload["parameters"]["sort_strategy"] == "volume_desc"
    assert payload["packing_mode"] == "offline"
    assert len(payload["items"]) == len(orders[order_id]["item_sequence"])


def test_joint_single_container_same_instance_validator_and_metrics():
    orders = _orders()
    response = run_joint_single_container(orders, target="euro-pallet")

    assert response.details["benchmark_group"] == "JOINT_SINGLE_CONTAINER"
    assert response.details["order_id"] == "00100408"
    assert response.details["target"] == "euro-pallet"
    assert response.details["sort_strategy"] == "volume_desc"
    assert response.details["packing_mode"] == "offline"
    assert response.details["container_size"] == list(TARGET_SIZES_MM["euro-pallet"])
    assert response.details["n_items"] == 26
    assert set(response.details["problem_types"]) == {p.value for p in JOINT_PROBLEM_TYPES}
    assert response.details["engines_total"] == len(JOINT_ENGINES)
    assert response.details["engines_error"] == 0
    assert len(response.ranking) == len(JOINT_ENGINES)

    metric_fields = {
        "volume_utilization",
        "items_packed",
        "items_unpacked",
        "containers_used",
        "execution_time_seconds",
        "constraint_violations",
    }
    types_seen: set[str] = set()
    for result in response.results:
        assert result.status != "error", result.error
        assert result.validation_report is not None
        assert result.solution is not None
        assert result.details["sort_strategy"] == "volume_desc"
        assert result.solution.execution_metadata.parameters["sort_strategy"] == "volume_desc"
        assert metric_fields.issubset(result.metrics.model_dump())
        types_seen.add(result.details["problem_type"])
        packed_containers = {p.container_id for p in result.solution.packed_items}
        assert packed_containers <= {response.details["container_id"]}

    assert types_seen == {p.value for p in JOINT_PROBLEM_TYPES}
    assert all(r.is_valid for r in response.results)
    assert response.ranking[0] == response.details["best_engine"]


def test_joint_forces_euro_pallet_on_rollcontainer_order():
    orders = _orders()
    roll_id = next(
        oid
        for oid, o in orders.items()
        if o["properties"]["target"] == "rollcontainer"
    )
    order_id, payload = build_joint_instance(
        orders, order_id=roll_id, target="euro-pallet"
    )
    assert order_id == roll_id
    c = payload["containers"][0]
    assert (c["length"], c["width"], c["height"]) == TARGET_SIZES_MM["euro-pallet"]
    assert payload["details"]["target"] == "euro-pallet"


def test_build_joint_instance_online_uses_input_order():
    orders = _orders()
    _, payload = build_joint_instance(orders, packing_mode="online")
    assert payload["packing_mode"] == "online"
    assert payload["parameters"]["sort_strategy"] == "input_order"


def test_joint_single_container_api():
    response = client.post("/api/v1/benchmark/joint-single-container", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["details"]["order_id"] == "00100408"
    assert body["details"]["sort_strategy"] == "volume_desc"
    assert body["details"]["packing_mode"] == "offline"
    assert len(body["results"]) == len(JOINT_ENGINES)
    assert body["details"]["engines_error"] == 0
    assert "3D_BPP" in body["details"]["problem_types"]
    assert ProblemType.CARTONIZATION.value not in body["details"]["problem_types"]
