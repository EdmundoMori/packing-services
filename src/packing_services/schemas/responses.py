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
    """Metadatos del servicio, útiles para publicación en un espacio de datos."""

    model_config = ConfigDict(extra="forbid")

    service_name: str
    service_version: str
    description: str
    supported_problem_types: list[str]
    endpoints: dict[str, str]
    implemented_algorithms: list[str]
    limitations: list[str]


class ServiceDescriptor(BaseModel):
    """Descriptor publicable de un servicio (activo de espacio de datos).

    Reúne los metadatos recomendados en el estado del arte para publicar,
    descubrir, ejecutar, validar y comparar el servicio dentro de un espacio de
    datos.
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
    """Catálogo de servicios listo para publicación en un espacio de datos."""

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
    algorithm_name: str
    solution: PackingSolution
    evaluated_boxes: list[dict[str, Any]] = Field(default_factory=list)


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


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    results: list[BenchmarkEngineResult]
    ranking: list[str]
    ranking_explanation: str
    details: dict[str, Any] = Field(default_factory=dict)
