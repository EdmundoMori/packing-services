"""Esquemas de response de la API (contrato de salida estandarizado).

La respuesta de packing reutiliza directamente ``PackingSolution`` del dominio.
Aquí se definen las respuestas específicas de metadata, catálogo, validación y
benchmark.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..domain.models import (
    Metrics,
    PackingSolution,
    ValidationReport,
)

# Reexport para que los routers importen desde un único lugar.
PackResponse = PackingSolution


class HealthResponse(BaseModel):
    status: str = "ok"
    service_version: str


class ServiceMetadataResponse(BaseModel):
    """Metadatos globales del servicio (catálogo, execute, límites)."""

    model_config = ConfigDict(extra="forbid")

    service_name: str
    service_version: str
    description: str
    supported_problem_types: list[str]
    endpoints: dict[str, str]
    implemented_algorithms: list[str]
    limitations: list[str]


class ServiceDescriptor(BaseModel):
    """Descriptor de un servicio o algoritmo (también usable como ficha dataspace).

    No implica integración en un espacio de datos.
    """

    model_config = ConfigDict(extra="forbid")

    service_name: str
    service_version: str
    problem_type: str
    description: str
    algorithms: list[str]
    engine: str
    license: str
    input_schema: str
    output_schema: str
    supported_constraints: list[str]
    unsupported_constraints: list[str]
    metrics: list[str]
    execution_endpoint: str
    validation_endpoint: str
    metadata_endpoint: str
    traceability: list[str]
    limitations: list[str]


class DataspaceCatalogResponse(BaseModel):
    """Listado de descriptores. El flag dataspace_ready no significa integración real."""

    model_config = ConfigDict(extra="forbid")

    service_version: str
    dataspace_ready: bool
    services: list[ServiceDescriptor]
    notes: list[str] = Field(default_factory=list)


class ValidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    validation_report: ValidationReport
    recomputed_metrics: Metrics


class CartonizationResponse(BaseModel):
    """Respuesta del Cartonization Service."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    status: str
    selected_box_id: str | None = None
    selected_box_ids: list[str] = Field(default_factory=list)
    algorithm_name: str
    solution: PackingSolution
    evaluated_boxes: list[dict[str, Any]] = Field(default_factory=list)


class CartonizationExtras(BaseModel):
    """Campos adicionales de cartonization en la respuesta estandarizada."""

    model_config = ConfigDict(extra="forbid")

    selected_box_id: str | None = None
    selected_box_ids: list[str] = Field(default_factory=list)
    evaluated_boxes: list[dict[str, Any]] = Field(default_factory=list)


class AlgorithmExecuteResponse(BaseModel):
    """Salida estandarizada de ``POST /api/v1/algorithms/{algorithm_name}/execute``.

    Todos los algoritmos devuelven la misma envoltura: la solución de packing
    canónica en ``solution`` y, solo para cartonization, metadatos en
    ``cartonization``.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    algorithm_name: str
    problem_type: str
    status: str
    solution: PackingSolution
    cartonization: CartonizationExtras | None = None

    @classmethod
    def from_pack(cls, solution: PackingSolution) -> AlgorithmExecuteResponse:
        return cls(
            request_id=solution.request_id,
            algorithm_name=solution.algorithm_name,
            problem_type=solution.problem_type.value,
            status=solution.status.value,
            solution=solution,
        )

    @classmethod
    def from_cartonization(cls, response: CartonizationResponse) -> AlgorithmExecuteResponse:
        return cls(
            request_id=response.request_id,
            algorithm_name=response.algorithm_name,
            problem_type="CARTONIZATION",
            status=response.status,
            solution=response.solution,
            cartonization=CartonizationExtras(
                selected_box_id=response.selected_box_id,
                selected_box_ids=response.selected_box_ids,
                evaluated_boxes=response.evaluated_boxes,
            ),
        )


class AlgorithmDetailResponse(BaseModel):
    """Metadatos de algoritmo enriquecidos con contrato API de ejecución."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    problem_types: list[str]
    algorithm_family: str
    status: str
    description: str = ""
    deterministic: bool = True
    supports_random_seed: bool = False
    supports_time_limit: bool = False
    supports_rotation: bool = True
    supports_multi_container: bool = True
    supported_constraints: list[str] = Field(default_factory=list)
    unsupported_constraints: list[str] = Field(default_factory=list)
    parameters: dict[str, str] = Field(default_factory=dict)
    default_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Valores por defecto seguros si el cliente no envía parameters.",
    )
    packing_modes: list[str] = Field(
        default_factory=list,
        description="Modos de packing en los que el algoritmo está disponible.",
    )
    metrics: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    external_engine: str | None = None
    external_language: str | None = None
    external_repository: str | None = None
    execution_endpoint: str
    input_schema: str
    output_schema: str = "AlgorithmExecuteResponse"
    is_executable: bool


class BenchmarkEngineResult(BaseModel):
    """Resultado de un motor concreto dentro de un benchmark."""

    model_config = ConfigDict(extra="forbid")

    engine: str
    status: str
    is_valid: bool
    metrics: Metrics
    validation_report: ValidationReport | None = None
    solution: PackingSolution | None = None
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    results: list[BenchmarkEngineResult]
    ranking: list[str]
    ranking_explanation: str
    details: dict[str, Any] = Field(default_factory=dict)
