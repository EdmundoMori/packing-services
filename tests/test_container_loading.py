"""Tests del Container Loading Service y weight_aware_container_loading."""

from __future__ import annotations

from packing_services.schemas.requests import ContainerLoadingRequest
from packing_services.services.container_loading_service import ContainerLoadingService


def _request(algorithm=None):
    return ContainerLoadingRequest(
        request_id="cl-test",
        containers=[
            {"id": "T1", "length": 200, "width": 100, "height": 100, "max_weight": 300}
        ],
        items=[
            {"id": "A", "length": 80, "width": 60, "height": 100, "weight": 120, "quantity": 2},
            {"id": "B", "length": 60, "width": 40, "height": 40, "weight": 20, "quantity": 5},
        ],
        constraints={"non_overlap": True, "containment": True, "allow_rotation": True, "max_weight": True},
        algorithm=algorithm,
    )


def test_default_algorithm_is_weight_aware():
    solution = ContainerLoadingService().load(_request())
    assert solution.algorithm_name == "weight_aware_container_loading"
    assert solution.validation_report.is_valid


def test_respects_max_weight():
    solution = ContainerLoadingService().load(_request())
    # max_weight=300; dos ítems A pesan 240, sumar B no debe superar 300.
    assert solution.metrics.loaded_weight <= 300
    assert solution.validation_report.is_valid
    assert solution.metrics.constraint_violations == 0


def test_explicit_algorithm_single_container():
    from packing_services.domain.models import AlgorithmConfig

    req = _request(algorithm=AlgorithmConfig(name="single_container_constructive"))
    solution = ContainerLoadingService().load(req)
    assert solution.algorithm_name == "single_container_constructive"
    assert solution.validation_report.is_valid
