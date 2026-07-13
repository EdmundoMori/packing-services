"""Tests del endpoint POST /api/v1/algorithms/{algorithm_name}/execute."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packing_services.api.main import app

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


def _execute(algorithm_name: str, payload: dict):
    return client.post(f"/api/v1/algorithms/{algorithm_name}/execute", json=payload)


def test_algorithm_execute_3d_bpp():
    payload = _load("algorithm_execute_3d_bpp.json")
    response = _execute("heuristic_3d_bpp_v1", payload)
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_name"] == "heuristic_3d_bpp_v1"
    assert body["problem_type"] == "3D_BPP"
    assert body["validation_report"]["is_valid"] is True
    assert body["metrics"]["items_packed"] >= 1


def test_algorithm_execute_container_loading():
    payload = _load("algorithm_execute_container_loading.json")
    response = _execute("weight_aware_container_loading", payload)
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_name"] == "weight_aware_container_loading"
    assert body["problem_type"] == "CONTAINER_LOADING"
    assert body["validation_report"]["is_valid"] is True


def test_algorithm_execute_single_container():
    payload = _load("algorithm_execute_single_container.json")
    response = _execute("best_fit_decreasing_3d", payload)
    assert response.status_code == 200
    body = response.json()
    assert body["problem_type"] == "SINGLE_CONTAINER_LOADING"
    assert body["validation_report"]["is_valid"] is True


def test_algorithm_execute_cartonization():
    payload = _load("algorithm_execute_cartonization.json")
    response = _execute("smallest_feasible_box", payload)
    assert response.status_code == 200
    body = response.json()
    assert body["selected_box_id"] is not None
    assert body["solution"]["validation_report"]["is_valid"] is True


def test_algorithm_execute_improvement():
    payload = _load("algorithm_execute_improvement.json")
    response = _execute("solution_compaction", payload)
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_name"] == "solution_compaction"
    assert body["validation_report"]["is_valid"] is True


def test_algorithm_execute_multi_type_requires_problem_type():
    """A3: algoritmos multi-tipo exigen problem_type en el body."""
    payload = _load("algorithm_execute_3d_bpp.json")
    del payload["problem_type"]
    response = _execute("extreme_points_3d", payload)
    assert response.status_code == 422
    assert "problem_type" in response.json()["error"]["message"].lower()


def test_algorithm_execute_incompatible_problem_type():
    payload = _load("algorithm_execute_cartonization.json")
    response = _execute("heuristic_3d_bpp_v1", payload)
    assert response.status_code == 422


def test_algorithm_execute_unknown_algorithm_404():
    payload = _load("algorithm_execute_3d_bpp.json")
    response = _execute("nope", payload)
    assert response.status_code == 404


def test_algorithm_execute_future_algorithm_400():
    payload = _load("algorithm_execute_3d_bpp.json")
    response = _execute("genetic_algorithm_3d_bpp", payload)
    assert response.status_code == 400


def test_algorithm_execute_rejects_algorithm_in_body():
    payload = _load("algorithm_execute_3d_bpp.json")
    payload["algorithm"] = {"name": "heuristic_3d_bpp_v1"}
    response = _execute("heuristic_3d_bpp_v1", payload)
    assert response.status_code == 422


def test_metadata_lists_algorithm_execute_endpoint():
    response = client.get("/api/v1/metadata")
    assert response.status_code == 200
    assert (
        response.json()["endpoints"]["algorithm_execute"]
        == "POST /api/v1/algorithms/{algorithm_name}/execute"
    )
