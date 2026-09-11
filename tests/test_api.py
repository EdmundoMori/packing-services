"""Tests de la API FastAPI."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packing_services.api.main import app

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metadata():
    response = client.get("/api/v1/metadata")
    assert response.status_code == 200
    body = response.json()
    assert body["service_name"] == "packing-services"
    assert "heuristic_3d_bpp_v1" in body["implemented_algorithms"]


def test_list_algorithms():
    response = client.get("/api/v1/algorithms")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "heuristic_3d_bpp_v1" in names
    assert "first_fit_decreasing_3d" in names


def test_list_algorithms_filter_status():
    response = client.get("/api/v1/algorithms", params={"status": "implemented"})
    assert response.status_code == 200
    assert all(a["status"] == "implemented" for a in response.json())


def test_get_algorithm_detail():
    response = client.get("/api/v1/algorithms/heuristic_3d_bpp_v1")
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Volume First Candidate Placement"
    assert body["execution_endpoint"] == "POST /api/v1/algorithms/heuristic_3d_bpp_v1/execute"
    assert body["input_schema"] == "PackAlgorithmInput"
    assert body["output_schema"] == "AlgorithmExecuteResponse"


def test_get_unknown_algorithm_404():
    response = client.get("/api/v1/algorithms/nope")
    assert response.status_code == 404


def test_pack_endpoint():
    response = client.post("/api/v1/pack/3d-bpp", json=_load("3d_bpp_basic_request.json"))
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_name"] == "heuristic_3d_bpp_v1"
    assert body["validation_report"]["is_valid"] is True
    assert "volume_utilization" in body["metrics"]
    assert body["metrics"]["items_packed"] >= 1


def test_pack_future_algorithm_returns_400():
    payload = _load("3d_bpp_basic_request.json")
    payload["algorithm"]["name"] = "mip_3d_bpp_reference"
    response = client.post("/api/v1/pack/3d-bpp", json=payload)
    assert response.status_code == 400


def test_validate_valid():
    response = client.post("/api/v1/validate", json=_load("validation_request_valid.json"))
    assert response.status_code == 200
    assert response.json()["validation_report"]["is_valid"] is True


def test_validate_invalid_overlap():
    response = client.post(
        "/api/v1/validate", json=_load("validation_request_invalid_overlap.json")
    )
    assert response.status_code == 200
    report = response.json()["validation_report"]
    assert report["is_valid"] is False
    assert any(v["type"] == "OVERLAP" for v in report["violations"])


def test_benchmark_endpoint():
    data = _load("benchmark_request.json")
    response = client.post("/api/v1/benchmark", json=data)
    assert response.status_code == 200
    body = response.json()
    assert len(body["ranking"]) == len(data["engines"])
    assert body["ranking_explanation"]
    assert body["details"]["benchmark_group"] == "3D_BPP"
    # La instancia de benchmark debe diferenciar claramente los motores.
    utils = {r["engine"]: r["metrics"]["volume_utilization"] for r in body["results"]}
    assert len(set(round(u, 3) for u in utils.values())) >= 3
    assert body["ranking"][0] == "best_fit_decreasing_3d"


def test_benchmark_container_loading_endpoint():
    data = _load("benchmark_container_loading_request.json")
    response = client.post("/api/v1/benchmark", json=data)
    assert response.status_code == 200
    body = response.json()
    assert body["details"]["benchmark_group"] == "CONTAINER_LOADING"
    assert body["details"]["benchmark_profile"] == "constructive"
    assert len(body["results"]) == 4


def test_benchmark_cartonization_endpoint():
    data = _load("benchmark_cartonization_request.json")
    response = client.post("/api/v1/benchmark", json=data)
    assert response.status_code == 200
    body = response.json()
    assert body["details"]["benchmark_group"] == "CARTONIZATION"
    assert body["details"]["benchmark_profile"] == "box_selection"
    assert len(body["results"]) == 4
    boxes = {r["details"]["selected_box_id"] for r in body["results"]}
    assert len(boxes) >= 2


def test_benchmark_single_container_endpoint():
    data = _load("benchmark_single_container_request.json")
    response = client.post("/api/v1/benchmark", json=data)
    assert response.status_code == 200
    body = response.json()
    assert body["details"]["benchmark_group"] == "SINGLE_CONTAINER_LOADING"
    assert len(body["results"]) == 3


def test_benchmark_hybrid_endpoint():
    data = _load("benchmark_hybrid_request.json")
    response = client.post("/api/v1/benchmark", json=data)
    assert response.status_code == 200
    body = response.json()
    assert body["details"]["benchmark_group"] == "3D_BPP"
    assert len(body["results"]) == 3
    assert all(r["is_valid"] for r in body["results"])


def test_container_loading_endpoint():
    response = client.post(
        "/api/v1/pack/container-loading", json=_load("container_loading_request.json")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_name"] == "weight_aware_container_loading"
    assert body["validation_report"]["is_valid"] is True


def test_cartonization_endpoint():
    response = client.post(
        "/api/v1/pack/cartonization", json=_load("cartonization_request.json")
    )
    assert response.status_code == 200
    body = response.json()
    assert body["selected_box_id"] is not None
    assert body["solution"]["validation_report"]["is_valid"] is True
    assert len(body["evaluated_boxes"]) == 3


def test_services_dataspace_endpoint():
    response = client.get("/api/v1/services")
    assert response.status_code == 200
    body = response.json()
    assert body["dataspace_ready"] is True
    names = [s["service_name"] for s in body["services"]]
    assert "Cartonization Service" in names
    assert "Container Loading Service" in names


def test_metadata_lists_new_endpoints():
    response = client.get("/api/v1/metadata")
    body = response.json()
    assert "CARTONIZATION" in body["supported_problem_types"]
    assert "CONTAINER_LOADING" in body["supported_problem_types"]
    assert "PALLETIZATION" in body["supported_problem_types"]
    assert body["endpoints"]["pack_cartonization"].endswith("/pack/cartonization")
    assert "benchmark_profiles" in body["endpoints"]
    assert "benchmark_joint_single_container" in body["endpoints"]
    assert "bed_bpp_convert" in body["endpoints"]
    assert "packing_modes" in body["endpoints"]
