"""Tests del endpoint POST /api/v1/algorithms/{algorithm_name}/execute."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from packing_services.algorithms.registry import get_default_registry
from packing_services.api.main import app
from packing_services.domain.enums import AlgorithmStatus, ProblemType
from packing_services.domain.packing_modes import ONLINE_ONLY_NAMES, PackingMode
from packing_services.services.algorithm_input_service import AlgorithmInputService

client = TestClient(app)
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
_input = AlgorithmInputService()


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text())


def _execute(algorithm_name: str, payload: dict):
    return client.post(f"/api/v1/algorithms/{algorithm_name}/execute", json=payload)


def _assert_pack_response(body: dict, algorithm_name: str, problem_type: str) -> None:
    assert body["algorithm_name"] == algorithm_name
    assert body["problem_type"] == problem_type
    assert body["cartonization"] is None
    assert body["solution"]["validation_report"]["is_valid"] is True
    assert body["solution"]["metrics"]["items_packed"] >= 1


def _assert_carton_response(body: dict, algorithm_name: str) -> None:
    assert body["algorithm_name"] == algorithm_name
    assert body["problem_type"] == "CARTONIZATION"
    assert body["cartonization"]["selected_box_ids"]
    assert body["solution"]["validation_report"]["is_valid"] is True


IMPLEMENTED_PACK_CASES = [
    ("heuristic_3d_bpp_v1", "3D_BPP"),
    ("first_fit_decreasing_3d", "3D_BPP"),
    ("best_fit_decreasing_3d", "SINGLE_CONTAINER_LOADING"),
    ("extreme_points_3d", "3D_BPP"),
    ("extreme_points_3d", "CONTAINER_LOADING"),
    ("maximal_spaces_3d", "3D_BPP"),
    ("maximal_spaces_3d", "CONTAINER_LOADING"),
    ("solution_compaction", "3D_BPP"),
    ("constructive_plus_local_search", "3D_BPP"),
    ("relocation_improvement", "3D_BPP"),
    ("swap_improvement", "3D_BPP"),
    ("orientation_improvement", "3D_BPP"),
    ("bin_reduction", "3D_BPP"),
    ("single_container_constructive", "SINGLE_CONTAINER_LOADING"),
    ("single_container_constructive", "CONTAINER_LOADING"),
    ("weight_aware_container_loading", "CONTAINER_LOADING"),
    ("weight_aware_container_loading", "3D_BPP"),
    ("wall_building_3d", "CONTAINER_LOADING"),
    ("layer_based_palletization", "PALLETIZATION"),
    ("stack_based_palletization", "PALLETIZATION"),
    ("stack_based_palletization", "STACKING_AWARE"),
    ("stacking_aware_constructive", "STACKING_AWARE"),
    ("online_3d_bpp_heuristic", "3D_BPP"),
    ("online_3d_bpp_heuristic", "PALLETIZATION"),
    ("online_3d_bpp_heuristic", "CONTAINER_LOADING"),
    ("online_3d_bpp_heuristic", "SINGLE_CONTAINER_LOADING"),
    ("online_3d_bpp_heuristic", "STACKING_AWARE"),
]

IMPLEMENTED_CARTON_CASES = [
    "smallest_feasible_box",
    "best_box_volume_utilization",
    "first_fit_box",
    "largest_feasible_box",
    "multi_box_cartonization",
]


@pytest.mark.parametrize("algorithm_name,problem_type", IMPLEMENTED_PACK_CASES)
def test_all_implemented_pack_algorithms_execute(algorithm_name: str, problem_type: str):
    mode = PackingMode.ONLINE if algorithm_name in ONLINE_ONLY_NAMES else None
    payload = _input.build_input_example(
        algorithm_name,
        problem_type=ProblemType(problem_type),
        packing_mode=mode,
    )
    response = _execute(algorithm_name, payload)
    assert response.status_code == 200, response.text
    _assert_pack_response(response.json(), algorithm_name, problem_type)


@pytest.mark.parametrize("algorithm_name", IMPLEMENTED_CARTON_CASES)
def test_all_implemented_cartonization_algorithms_execute(algorithm_name: str):
    payload = _input.build_input_example(algorithm_name)
    response = _execute(algorithm_name, payload)
    assert response.status_code == 200, response.text
    _assert_carton_response(response.json(), algorithm_name)


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
    response = _execute("mip_3d_bpp_reference", payload)
    assert response.status_code == 400


def test_algorithm_execute_rejects_algorithm_in_body():
    payload = _load("algorithm_execute_3d_bpp.json")
    payload["algorithm"] = {"name": "heuristic_3d_bpp_v1"}
    response = _execute("heuristic_3d_bpp_v1", payload)
    assert response.status_code == 422


def test_algorithm_detail_includes_execution_contract():
    response = client.get("/api/v1/algorithms/heuristic_3d_bpp_v1")
    assert response.status_code == 200
    body = response.json()
    assert body["execution_endpoint"] == "POST /api/v1/algorithms/heuristic_3d_bpp_v1/execute"
    assert body["input_schema"] == "PackAlgorithmInput"
    assert body["output_schema"] == "AlgorithmExecuteResponse"
    assert body["is_executable"] is True


def test_algorithm_input_example_endpoint():
    response = client.get(
        "/api/v1/algorithms/solution_compaction/input-example",
        params={"problem_type": "3D_BPP"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["problem_type"] == "3D_BPP"
    assert "algorithm" not in body
    assert body["parameters"]["base_algorithm"] == "best_fit_decreasing_3d"


def test_metadata_lists_algorithm_execute_endpoint():
    response = client.get("/api/v1/metadata")
    assert response.status_code == 200
    endpoints = response.json()["endpoints"]
    assert endpoints["algorithm_execute"] == "POST /api/v1/algorithms/{algorithm_name}/execute"
    assert endpoints["online_learned_execute"] == "POST /api/v1/online/learned/execute"
    assert endpoints["online_rl_execute"] == "POST /api/v1/online/rl/execute"
    assert endpoints["algorithm_input_example"] == (
        "GET /api/v1/algorithms/{algorithm_name}/input-example"
    )


def test_every_implemented_algorithm_has_execute_contract():
    registry = get_default_registry()
    for meta in registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED):
        detail = client.get(f"/api/v1/algorithms/{meta.name}").json()
        assert detail["execution_endpoint"].endswith(f"/{meta.name}/execute")
        assert detail["output_schema"] == "AlgorithmExecuteResponse"


def test_execute_reports_validation_for_requested_constraints():
    payload = _input.build_input_example(
        "stacking_aware_constructive", problem_type=ProblemType.STACKING_AWARE
    )
    payload["constraints"] = {
        "non_overlap": True,
        "containment": True,
        "allow_rotation": True,
        "max_weight": True,
        "basic_stability": True,
        "load_bearing": True,
    }
    response = _execute("stacking_aware_constructive", payload)
    assert response.status_code == 200, response.text
    report = response.json()["solution"]["validation_report"]
    assert report is not None
    assert "is_valid" in report
    assert isinstance(report["violations"], list)


def test_py3dbp_adapter_execute_api_when_installed():
    registry = get_default_registry()
    if not registry.is_executable("py3dbp_adapter"):
        pytest.skip("py3dbp no instalado")
    payload = _input.build_input_example("py3dbp_adapter", problem_type=ProblemType.THREE_D_BPP)
    response = _execute("py3dbp_adapter", payload)
    assert response.status_code == 200, response.text
    _assert_pack_response(response.json(), "py3dbp_adapter", "3D_BPP")
