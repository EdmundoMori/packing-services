"""Dos modos de packing (offline / online) sobre el mismo contrato de entrada."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from packing_services.algorithms.registry import get_default_registry
from packing_services.api.main import app
from packing_services.domain.enums import AlgorithmFamily, PackingMode
from packing_services.domain.packing_modes import (
    DEFAULT_PACKING_MODE,
    modes_for_algorithm,
)

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_default_mode_is_offline():
    assert DEFAULT_PACKING_MODE is PackingMode.OFFLINE


def test_packing_modes_endpoint():
    response = client.get("/api/v1/packing-modes")
    assert response.status_code == 200
    body = response.json()
    assert body["default"] == "offline"
    assert body["same_input"] is True
    ids = [m["id"] for m in body["modes"]]
    assert ids == ["offline", "online"]


def test_catalog_filter_packing_mode():
    offline = client.get("/api/v1/algorithms", params={"packing_mode": "offline"})
    online = client.get("/api/v1/algorithms", params={"packing_mode": "online"})
    assert offline.status_code == 200
    assert online.status_code == 200
    off_names = {a["name"] for a in offline.json()}
    on_names = {a["name"] for a in online.json()}
    assert "simulated_annealing_3d_bpp" in off_names
    assert "simulated_annealing_3d_bpp" not in on_names
    assert "smallest_feasible_box" in off_names
    assert "smallest_feasible_box" not in on_names
    assert "heuristic_3d_bpp_v1" in off_names
    assert "heuristic_3d_bpp_v1" in on_names
    assert "online_3d_bpp_heuristic" in on_names
    assert "online_3d_bpp_heuristic" not in off_names
    assert "drl_policy_3d_bpp" in on_names


def test_algorithm_detail_includes_packing_modes():
    response = client.get("/api/v1/algorithms/heuristic_3d_bpp_v1")
    assert response.status_code == 200
    body = response.json()
    assert set(body["packing_modes"]) == {"offline", "online"}
    sa = client.get("/api/v1/algorithms/simulated_annealing_3d_bpp").json()
    assert sa["packing_modes"] == ["offline"]


def test_classification_matches_families():
    registry = get_default_registry()
    meta = registry.get_metadata("constructive_plus_local_search")
    assert modes_for_algorithm(
        meta.name, meta.algorithm_family, meta.problem_types
    ) == (PackingMode.OFFLINE,)
    assert meta.algorithm_family == AlgorithmFamily.HYBRID


def test_online_rejects_metaheuristic():
    payload = json.loads((EXAMPLES / "algorithm_execute_3d_bpp.json").read_text())
    payload["packing_mode"] = "online"
    response = client.post(
        "/api/v1/algorithms/simulated_annealing_3d_bpp/execute",
        json=payload,
    )
    assert response.status_code == 422
    assert "packing_mode=online" in response.json()["error"]["message"]


def test_online_rejects_cartonization():
    payload = json.loads((EXAMPLES / "algorithm_execute_cartonization.json").read_text())
    payload["packing_mode"] = "online"
    response = client.post(
        "/api/v1/algorithms/smallest_feasible_box/execute",
        json=payload,
    )
    assert response.status_code == 422


def test_online_constructive_forces_input_order():
    payload = json.loads((EXAMPLES / "algorithm_execute_3d_bpp.json").read_text())
    payload["packing_mode"] = "online"
    payload["parameters"] = {"sort_strategy": "volume_desc"}
    response = client.post(
        "/api/v1/algorithms/heuristic_3d_bpp_v1/execute",
        json=payload,
    )
    assert response.status_code == 422


def test_online_constructive_runs_input_order():
    payload = json.loads((EXAMPLES / "algorithm_execute_3d_bpp.json").read_text())
    payload["packing_mode"] = "online"
    payload.pop("parameters", None)
    response = client.post(
        "/api/v1/algorithms/heuristic_3d_bpp_v1/execute",
        json=payload,
    )
    assert response.status_code == 200, response.text
    used = response.json()["solution"]["execution_metadata"]["parameters"]
    assert used["sort_strategy"] == "input_order"


def test_offline_benchmark_rejects_nothing_on_metaheuristic_profile():
    payload = json.loads((EXAMPLES / "benchmark_request.json").read_text())
    payload["packing_mode"] = "offline"
    response = client.post("/api/v1/benchmark", json=payload)
    assert response.status_code == 200


def test_online_benchmark_rejects_metaheuristic_engine():
    payload = json.loads((EXAMPLES / "benchmark_request.json").read_text())
    payload["packing_mode"] = "online"
    payload["engines"] = [
        {"name": "heuristic_3d_bpp_v1"},
        {"name": "simulated_annealing_3d_bpp", "parameters": {"iterations": 5}},
    ]
    response = client.post("/api/v1/benchmark", json=payload)
    assert response.status_code == 422
