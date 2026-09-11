"""Política aprendida online: execute por model_path (entrenamiento aparte)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.api.main import app
from packing_services.datasets.bed_bpp import convert_order_to_pack_input
from packing_services.domain.enums import AlgorithmStatus, ProblemType
from packing_services.domain.models import AlgorithmConfig, Container, Item, PackingProblem
from packing_services.online.features import FEATURE_DIM
from packing_services.online.learned.checkpoint import greedy_like_linear_document
from packing_services.online.learned.production import (
    CINTA_MODEL_PATH,
    DEFAULT_MODEL_PATH,
    LINEAR_MODEL_PATH,
    PRODUCT_HOLDOUT_ORDER_IDS,
    default_learned_parameters,
)
from packing_services.utils.errors import InvalidInputError

client = TestClient(app)
REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
CHECKPOINT = EXAMPLES / "online_policy_linear_v1.json"
SAMPLE = EXAMPLES / "5_bed-bpp.json"
VAL_ORDERS = REPO / "online_policy_ml" / "data" / "val" / "bed_bpp_orders.json"
PROD_MLP = REPO / DEFAULT_MODEL_PATH
PROD_CINTA = REPO / CINTA_MODEL_PATH
PROD_LINEAR = REPO / LINEAR_MODEL_PATH
NON_HOLDOUT_ORDER_ID = "00101137"


def _tiny_problem(parameters: dict) -> PackingProblem:
    return PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=50, width=50, height=50, max_weight=1000)],
        items=[
            Item(id="I1", length=10, width=10, height=10, weight=1, arrival_index=1),
            Item(id="I2", length=10, width=10, height=10, weight=1, arrival_index=2),
        ],
        algorithm=AlgorithmConfig(name="drl_policy_3d_bpp", parameters=parameters),
    )


def test_shipped_linear_checkpoint_matches_encoder():
    assert CHECKPOINT.is_file()
    doc = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    assert doc["format"] == "packing-services-online-policy"
    assert len(doc["weights"]) == FEATURE_DIM
    assert doc["feature_dim"] == FEATURE_DIM


def test_missing_model_path_raises():
    try:
        DRLPolicy3DBPP().run(_tiny_problem({}))
        raise AssertionError("debía exigir model_path")
    except InvalidInputError as exc:
        assert "model_path" in str(exc)


def test_unknown_path_raises():
    try:
        DRLPolicy3DBPP().run(_tiny_problem({"model_path": "/tmp/no-existe-packing-policy.json"}))
        raise AssertionError("debía fallar la ruta")
    except InvalidInputError as exc:
        assert "No se encontró" in str(exc) or "model_path" in str(exc)


def test_linear_checkpoint_packs_valid():
    solution = DRLPolicy3DBPP().run(
        _tiny_problem({"model_path": str(CHECKPOINT), "lookahead_p": 1, "select_s": 1})
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == 2
    heuristic = Online3DBPPHeuristic().run(
        PackingProblem(
            problem_type="3D_BPP",
            containers=solution.packed_items and _tiny_problem({}).containers,
            items=_tiny_problem({}).items,
            algorithm=AlgorithmConfig(
                name="online_3d_bpp_heuristic",
                parameters={"selection": "best_fit", "lookahead_p": 1, "select_s": 1},
            ),
        )
    )
    # El placeholder linear imita rank_0 de EP; debe coincidir con el heurístico.
    assert [
        (p.item_id, p.position, p.orientation) for p in solution.packed_items
    ] == [
        (p.item_id, p.position, p.orientation) for p in heuristic.packed_items
    ]


def test_execute_empty_model_path_still_422():
    payload = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 50, "width": 50, "height": 50, "max_weight": 1000}],
        "items": [{"id": "I1", "length": 10, "width": 10, "height": 10, "weight": 1, "quantity": 1}],
        "packing_mode": "online",
        "parameters": {"model_path": ""},
    }
    missing = client.post("/api/v1/algorithms/drl_policy_3d_bpp/execute", json=payload)
    assert missing.status_code == 422
    payload["parameters"] = {"model_path": str(CHECKPOINT)}
    ok = client.post("/api/v1/algorithms/drl_policy_3d_bpp/execute", json=payload)
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["algorithm_name"] == "drl_policy_3d_bpp"
    assert body["solution"]["validation_report"]["is_valid"] is True
    assert body["solution"]["metrics"]["items_packed"] == 1


def test_dedicated_route_forces_online():
    payload = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 40, "width": 40, "height": 40, "max_weight": 500}],
        "items": [{"id": "A", "length": 8, "width": 8, "height": 8, "weight": 1, "quantity": 2}],
        "parameters": {"model_path": "examples/online_policy_linear_v1.json"},
    }
    response = client.post("/api/v1/online/learned/execute", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["algorithm_name"] == "drl_policy_3d_bpp"
    assert response.json()["solution"]["validation_report"]["is_valid"] is True


def test_dedicated_route_rejects_offline():
    payload = {
        "problem_type": "3D_BPP",
        "packing_mode": "offline",
        "containers": [{"id": "C1", "length": 20, "width": 20, "height": 20}],
        "items": [{"id": "A", "length": 5, "width": 5, "height": 5, "quantity": 1}],
        "parameters": {"model_path": str(CHECKPOINT)},
    }
    response = client.post("/api/v1/online/learned/execute", json=payload)
    assert response.status_code == 422


def test_execute_bed_bpp_with_model_path():
    orders = json.loads(SAMPLE.read_text(encoding="utf-8"))
    order_id = min(orders.items(), key=lambda kv: len(kv[1]["item_sequence"]))[0]
    payload = {
        "input_format": "bed_bpp",
        "order_id": order_id,
        "orders": orders,
        "problem_type": "PALLETIZATION",
        "packing_mode": "online",
        "parameters": {"model_path": str(CHECKPOINT), "lookahead_p": 1, "select_s": 1},
    }
    response = client.post("/api/v1/online/learned/execute", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["solution"]["validation_report"]["is_valid"] is True
    assert data["solution"]["metrics"]["items_packed"] >= 1
    converted = convert_order_to_pack_input(
        orders, order_id, problem_type=ProblemType.PALLETIZATION, packing_mode="online"
    )
    arrivals = {it["id"]: it["arrival_index"] for it in converted["items"]}
    packed_arrivals = [arrivals[p["item_id"]] for p in data["solution"]["packed_items"]]
    assert packed_arrivals == sorted(packed_arrivals)


def test_catalog_marks_drl_implemented():
    detail = client.get("/api/v1/algorithms/drl_policy_3d_bpp").json()
    assert detail["status"] == AlgorithmStatus.IMPLEMENTED.value
    assert detail["is_executable"] is True
    assert "model_path" in detail["parameters"]
    assert detail["default_parameters"]["model_path"] == DEFAULT_MODEL_PATH
    example = client.get(
        "/api/v1/algorithms/drl_policy_3d_bpp/input-example",
        params={"problem_type": "PALLETIZATION"},
    )
    assert example.status_code == 200, example.text
    body = example.json()
    assert body["packing_mode"] == "online"
    assert body["parameters"]["model_path"] == DEFAULT_MODEL_PATH


def test_greedy_like_document_is_stable():
    doc = greedy_like_linear_document()
    assert doc["feature_dim"] == FEATURE_DIM
    assert len(doc["weights"]) == FEATURE_DIM


def test_production_linear_checkpoint_matches_encoder():
    assert PROD_LINEAR.is_file()
    doc = json.loads(PROD_LINEAR.read_text(encoding="utf-8"))
    assert doc["format"] == "packing-services-online-policy"
    assert doc["feature_version"] == 1
    assert len(doc["weights"]) == FEATURE_DIM


def test_production_linear_execute_tiny():
    solution = DRLPolicy3DBPP().run(
        _tiny_problem(
            {"model_path": LINEAR_MODEL_PATH, "lookahead_p": 1, "select_s": 1}
        )
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == 2


def _skip_without_production_mlp() -> None:
    pytest.importorskip("torch")
    if not PROD_MLP.is_file():
        pytest.skip(f"falta checkpoint de producción {PROD_MLP}")


def test_execute_default_uses_production_mlp():
    _skip_without_production_mlp()
    payload = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 50, "width": 50, "height": 50, "max_weight": 1000}],
        "items": [{"id": "I1", "length": 10, "width": 10, "height": 10, "weight": 1, "quantity": 1}],
        "packing_mode": "online",
    }
    response = client.post("/api/v1/algorithms/drl_policy_3d_bpp/execute", json=payload)
    assert response.status_code == 200, response.text
    used = response.json()["solution"]["execution_metadata"]["parameters"]
    defaults = default_learned_parameters()
    for key, value in defaults.items():
        assert used[key] == value
    assert response.json()["solution"]["validation_report"]["is_valid"] is True


def test_dedicated_route_default_model_path():
    _skip_without_production_mlp()
    payload = {
        "problem_type": "3D_BPP",
        "containers": [{"id": "C1", "length": 40, "width": 40, "height": 40, "max_weight": 500}],
        "items": [{"id": "A", "length": 8, "width": 8, "height": 8, "weight": 1, "quantity": 2}],
    }
    response = client.post("/api/v1/online/learned/execute", json=payload)
    assert response.status_code == 200, response.text
    used = response.json()["solution"]["execution_metadata"]["parameters"]
    assert used["model_path"] == DEFAULT_MODEL_PATH


def test_production_mlp_holdout_00100408():
    _skip_without_production_mlp()
    orders = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert "00100408" in PRODUCT_HOLDOUT_ORDER_IDS
    payload = {
        "input_format": "bed_bpp",
        "order_id": "00100408",
        "orders": orders,
        "problem_type": "PALLETIZATION",
        "packing_mode": "online",
        "parameters": default_learned_parameters(),
    }
    response = client.post("/api/v1/online/learned/execute", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["solution"]["validation_report"]["is_valid"] is True
    n_items = len(orders["00100408"]["item_sequence"])
    assert data["solution"]["metrics"]["items_packed"] == n_items


def test_production_mlp_non_holdout_val_order():
    _skip_without_production_mlp()
    if not VAL_ORDERS.is_file():
        pytest.skip(f"falta split val {VAL_ORDERS}")
    orders = json.loads(VAL_ORDERS.read_text(encoding="utf-8"))
    assert NON_HOLDOUT_ORDER_ID in orders
    assert NON_HOLDOUT_ORDER_ID not in PRODUCT_HOLDOUT_ORDER_IDS
    payload = {
        "input_format": "bed_bpp",
        "order_id": NON_HOLDOUT_ORDER_ID,
        "orders": {NON_HOLDOUT_ORDER_ID: orders[NON_HOLDOUT_ORDER_ID]},
        "problem_type": "PALLETIZATION",
        "packing_mode": "online",
        "parameters": default_learned_parameters(),
    }
    response = client.post("/api/v1/algorithms/drl_policy_3d_bpp/execute", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["solution"]["validation_report"]["is_valid"] is True
    assert data["solution"]["metrics"]["items_packed"] >= 1
    converted = convert_order_to_pack_input(
        payload["orders"],
        NON_HOLDOUT_ORDER_ID,
        problem_type=ProblemType.PALLETIZATION,
        packing_mode="online",
    )
    arrivals = {it["id"]: it["arrival_index"] for it in converted["items"]}
    packed_arrivals = [arrivals[p["item_id"]] for p in data["solution"]["packed_items"]]
    assert packed_arrivals == sorted(packed_arrivals)


def test_production_cinta_mlp_loads_and_packs_tiny():
    pytest.importorskip("torch")
    if not PROD_CINTA.is_file():
        pytest.skip(f"falta checkpoint de cinta {PROD_CINTA}")
    solution = DRLPolicy3DBPP().run(
        _tiny_problem(
            {
                "model_path": CINTA_MODEL_PATH,
                "lookahead_p": 3,
                "select_s": 2,
            }
        )
    )
    assert solution.validation_report.is_valid
    assert solution.metrics.items_packed == 2


def test_example_file_online_learned_execute():
    _skip_without_production_mlp()
    payload = json.loads(
        (EXAMPLES / "algorithm_execute_online_learned.json").read_text(encoding="utf-8")
    )
    response = client.post("/api/v1/algorithms/drl_policy_3d_bpp/execute", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["solution"]["validation_report"]["is_valid"] is True
