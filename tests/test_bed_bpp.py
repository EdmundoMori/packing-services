"""Tests de integración BED-BPP → packing-services (execute / benchmark / API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packing_services.api.main import app
from packing_services.datasets.bed_bpp import (
    TARGET_SIZES_MM,
    convert_order_to_benchmark_input,
    convert_order_to_pack_input,
    looks_like_bed_bpp_orders,
    normalize_benchmark_payload,
    normalize_execute_payload,
    smallest_order_id,
)
from packing_services.domain.enums import ProblemType
from packing_services.utils.errors import InvalidInputError

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE = EXAMPLES / "5_bed-bpp.json"


@pytest.fixture(scope="module")
def bed_orders():
    assert SAMPLE.exists(), "Falta examples/5_bed-bpp.json"
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def test_sample_looks_like_bed_bpp(bed_orders):
    assert looks_like_bed_bpp_orders(bed_orders)
    assert len(bed_orders) == 5


def test_convert_order_euro_pallet(bed_orders):
    # pedido con euro-pallet en la muestra
    order_id = next(
        oid
        for oid, o in bed_orders.items()
        if o["properties"]["target"] == "euro-pallet"
    )
    payload = convert_order_to_pack_input(
        bed_orders, order_id, problem_type=ProblemType.PALLETIZATION
    )
    assert payload["problem_type"] == "PALLETIZATION"
    assert len(payload["containers"]) == 1
    c = payload["containers"][0]
    assert c["length"] == TARGET_SIZES_MM["euro-pallet"][0]
    assert c["width"] == TARGET_SIZES_MM["euro-pallet"][1]
    assert c["height"] == TARGET_SIZES_MM["euro-pallet"][2]
    assert len(payload["items"]) == len(bed_orders[order_id]["item_sequence"])
    assert all(it["quantity"] == 1 for it in payload["items"])
    assert all("length/mm" not in it for it in payload["items"])


def test_convert_order_rollcontainer(bed_orders):
    order_id = next(
        oid
        for oid, o in bed_orders.items()
        if o["properties"]["target"] == "rollcontainer"
    )
    payload = convert_order_to_pack_input(
        bed_orders, order_id, problem_type="SINGLE_CONTAINER_LOADING"
    )
    c = payload["containers"][0]
    assert (c["length"], c["width"], c["height"]) == TARGET_SIZES_MM["rollcontainer"]


def test_convert_unknown_order_raises(bed_orders):
    with pytest.raises(InvalidInputError):
        convert_order_to_pack_input(bed_orders, "no-existe")


def test_normalize_execute_wrapper(bed_orders):
    order_id = next(iter(bed_orders))
    wrapper = {
        "input_format": "bed_bpp",
        "order_id": order_id,
        "orders": bed_orders,
        "problem_type": "PALLETIZATION",
        "parameters": {"sort_strategy": "volume_desc"},
    }
    normalized = normalize_execute_payload(wrapper)
    assert "containers" in normalized and "items" in normalized
    assert "input_format" not in normalized
    assert "orders" not in normalized


def test_normalize_leaves_canonical_untouched():
    canonical = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 10, "width": 10, "height": 10}],
        "items": [{"id": "I1", "length": 1, "width": 1, "height": 1, "quantity": 1}],
    }
    assert normalize_execute_payload(canonical) is canonical or normalize_execute_payload(
        canonical
    ) == canonical


def test_api_sample_and_convert(bed_orders):
    sample = client.get("/api/v1/datasets/bed-bpp/sample")
    assert sample.status_code == 200
    assert sample.json()["n_orders"] == 5

    order_id = sample.json()["order_ids"][0]
    conv = client.post(
        "/api/v1/datasets/bed-bpp/convert",
        json={"order_id": order_id, "problem_type": "PALLETIZATION", "mode": "execute"},
    )
    assert conv.status_code == 200, conv.text
    body = conv.json()
    assert body["input"]["containers"]
    assert body["input"]["items"]
    assert body["details"]["order_id"] == order_id


def test_api_execute_with_bed_bpp_wrapper(bed_orders):
    order_id = next(
        oid
        for oid, o in bed_orders.items()
        if o["properties"]["target"] == "euro-pallet"
    )
    payload = {
        "input_format": "bed_bpp",
        "order_id": order_id,
        "orders": bed_orders,
        "problem_type": "PALLETIZATION",
        "parameters": {"sort_strategy": "volume_desc"},
    }
    response = client.post(
        "/api/v1/algorithms/layer_based_palletization/execute",
        json=payload,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["solution"]["packed_items"] or data["solution"]["unpacked_items"]
    assert data["solution"]["metrics"]["items_packed"] >= 0


def test_execute_bed_bpp_merges_default_parameters(bed_orders):
    """Sin parameters en el wrapper, el servicio rellena defaults seguros."""
    order_id = min(bed_orders.items(), key=lambda kv: len(kv[1]["item_sequence"]))[0]
    payload = {
        "input_format": "bed_bpp",
        "order_id": order_id,
        "orders": bed_orders,
        "problem_type": "PALLETIZATION",
    }
    response = client.post(
        "/api/v1/algorithms/layer_based_palletization/execute",
        json=payload,
    )
    assert response.status_code == 200, response.text
    detail = client.get("/api/v1/algorithms/layer_based_palletization")
    assert detail.status_code == 200
    assert "default_parameters" in detail.json()
    assert detail.json()["default_parameters"].get("sort_strategy")


def test_api_benchmark_with_bed_bpp_wrapper(bed_orders):
    order_id = next(
        oid
        for oid, o in bed_orders.items()
        if o["properties"]["target"] == "euro-pallet"
    )
    # Usar un pedido más pequeño si es posible para velocidad
    smallest = min(
        bed_orders.items(),
        key=lambda kv: len(kv[1]["item_sequence"]),
    )[0]
    payload = {
        "input_format": "bed_bpp",
        "order_id": smallest,
        "orders": bed_orders,
        "problem_type": "PALLETIZATION",
        "engines": [
            {"name": "layer_based_palletization", "parameters": {"sort_strategy": "volume_desc"}},
            {"name": "stack_based_palletization", "parameters": {"sort_strategy": "volume_desc"}},
        ],
    }
    response = client.post("/api/v1/benchmark", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["results"]) == 2
    assert body["ranking"]


def test_convert_benchmark_helper(bed_orders):
    order_id = next(iter(bed_orders))
    bench = convert_order_to_benchmark_input(
        bed_orders, order_id, problem_type="STACKING_AWARE", profile="constructive"
    )
    assert bench["profile"] == "constructive"
    assert bench["problem_type"] == "STACKING_AWARE"
    assert normalize_benchmark_payload(
        {
            "input_format": "bed_bpp",
            "order_id": order_id,
            "orders": bed_orders,
            "problem_type": "STACKING_AWARE",
            "profile": "constructive",
        }
    )["items"]


def test_smallest_order_id(bed_orders):
    assert smallest_order_id(bed_orders) == "00100408"


def test_target_override_forces_euro_pallet(bed_orders):
    roll_id = next(
        oid
        for oid, o in bed_orders.items()
        if o["properties"]["target"] == "rollcontainer"
    )
    payload = convert_order_to_pack_input(
        bed_orders,
        roll_id,
        problem_type=ProblemType.THREE_D_BPP,
        target_override="euro-pallet",
    )
    c = payload["containers"][0]
    assert (c["length"], c["width"], c["height"]) == TARGET_SIZES_MM["euro-pallet"]
    assert payload["details"]["target"] == "euro-pallet"
