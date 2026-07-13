"""Ejecución directa de servicios (sin API HTTP) para los notebooks."""

from __future__ import annotations

from typing import Any

from packing_services.domain.models import PackingSolution
from packing_services.schemas.requests import (
    BenchmarkRequest,
    CartonizationRequest,
    ContainerLoadingRequest,
    PackRequest,
    ValidateRequest,
)
from packing_services.schemas.responses import (
    BenchmarkResponse,
    CartonizationResponse,
    ValidateResponse,
)
from packing_services.services.algorithm_execution_service import AlgorithmExecutionService
from packing_services.services.benchmark_service import BenchmarkService
from packing_services.services.cartonization_service import CartonizationService
from packing_services.services.container_loading_service import ContainerLoadingService
from packing_services.services.dataspace_service import DataspaceService
from packing_services.services.packing_service import PackingService
from packing_services.services.validation_service import ValidationService
from packing_services.algorithms.registry import get_default_registry


def run_pack(data: dict[str, Any]) -> PackingSolution:
    return PackingService().pack(PackRequest(**data))


def run_container_loading(data: dict[str, Any]) -> PackingSolution:
    return ContainerLoadingService().load(ContainerLoadingRequest(**data))


def run_cartonization(data: dict[str, Any]) -> CartonizationResponse:
    return CartonizationService().cartonize(CartonizationRequest(**data))


def run_benchmark(data: dict[str, Any]) -> BenchmarkResponse:
    return BenchmarkService().benchmark(BenchmarkRequest(**data))


def run_validate(data: dict[str, Any]) -> ValidateResponse:
    return ValidationService().validate(ValidateRequest(**data))


def run_dataspace_catalog():
    return DataspaceService().catalog()


def list_algorithms(**filters):
    return get_default_registry().list_metadata(**filters)


def run_algorithm_execute(
    algorithm_name: str, data: dict[str, Any]
) -> PackingSolution | CartonizationResponse:
    """Ejecuta un algoritmo por nombre (equivalente a POST /algorithms/{name}/execute)."""

    return AlgorithmExecutionService().execute(algorithm_name, data)
