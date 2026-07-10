"""Tests del Cartonization Service."""

from __future__ import annotations

import pytest

from packing_services.domain.models import AlgorithmConfig
from packing_services.schemas.requests import CartonizationRequest
from packing_services.services.cartonization_service import CartonizationService


def _request(algorithm_name):
    return CartonizationRequest(
        request_id="carton-test",
        items=[
            {"id": "SKU1", "length": 20, "width": 15, "height": 10, "weight": 2, "quantity": 2},
            {"id": "SKU2", "length": 30, "width": 10, "height": 10, "weight": 1, "quantity": 1},
        ],
        boxes=[
            {"id": "S", "length": 20, "width": 15, "height": 10, "max_weight": 20},
            {"id": "M", "length": 40, "width": 30, "height": 20, "max_weight": 30},
            {"id": "L", "length": 60, "width": 40, "height": 40, "max_weight": 50},
        ],
        constraints={"non_overlap": True, "containment": True, "allow_rotation": True, "max_weight": True},
        algorithm=AlgorithmConfig(name=algorithm_name),
    )


@pytest.mark.parametrize("algo", ["smallest_feasible_box", "best_box_volume_utilization"])
def test_selects_a_box_and_is_valid(algo):
    response = CartonizationService().cartonize(_request(algo))
    assert response.selected_box_id is not None
    assert response.solution.validation_report.is_valid
    assert response.status == "success"


def test_smallest_feasible_box_avoids_too_small():
    # La caja "S" no puede alojar todos los ítems; debe elegir una mayor.
    response = CartonizationService().cartonize(_request("smallest_feasible_box"))
    assert response.selected_box_id in {"M", "L"}
    assert response.solution.metrics.items_unpacked == 0


def test_evaluation_summary_present():
    response = CartonizationService().cartonize(_request("smallest_feasible_box"))
    assert len(response.evaluated_boxes) == 3
    for entry in response.evaluated_boxes:
        assert "box_id" in entry and "fits_all" in entry and "volume_utilization" in entry


def test_all_items_selected_box_chosen_by_utilization():
    response = CartonizationService().cartonize(_request("best_box_volume_utilization"))
    # Entre las cajas que alojan todo, la de mayor utilización debe ser la elegida.
    fitting = [b for b in response.evaluated_boxes if b["fits_all"]]
    assert fitting
    best = max(fitting, key=lambda b: b["volume_utilization"])
    assert response.selected_box_id == best["box_id"]
