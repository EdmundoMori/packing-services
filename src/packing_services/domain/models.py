"""Modelos de dominio comunes (Pydantic v2).

Estos modelos son la representación canónica compartida por algoritmos,
validador, métricas y servicios. Los esquemas de la API (``schemas/``)
reutilizan y componen estos modelos para definir los contratos de entrada y
salida estandarizados descritos en los documentos de contexto.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import (
    AlgorithmFamily,
    Constraint,
    ProblemType,
    Severity,
    SolutionStatus,
)
from .geometry import Dimensions, Position

# Orientaciones permitidas por ítem. En la primera versión soportamos:
#   - "all": las 6 rotaciones axis-aligned.
#   - "none": ninguna rotación (se respeta l/w/h original).
AllowedOrientations = Literal["all", "none"]


class Item(BaseModel):
    """Ítem/caja a empacar. Las dimensiones son length(x), width(y), height(z)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    weight: float = Field(default=0.0, ge=0)
    quantity: int = Field(default=1, ge=1)
    allowed_orientations: AllowedOrientations = "all"
    # Campos opcionales previstos para fases stacking-aware (aún no optimizados).
    max_load_on_top: float | None = Field(default=None, ge=0)
    fragile: bool = False

    @property
    def dimensions(self) -> Dimensions:
        return Dimensions(self.length, self.width, self.height)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    @property
    def allow_rotation(self) -> bool:
        return self.allowed_orientations == "all"


class Container(BaseModel):
    """Contenedor/bin/pallet destino."""

    model_config = ConfigDict(extra="forbid")

    id: str
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    max_weight: float | None = Field(default=None, ge=0)

    @property
    def dimensions(self) -> Dimensions:
        return Dimensions(self.length, self.width, self.height)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height


class ConstraintFlags(BaseModel):
    """Restricciones declaradas por el usuario para una instancia.

    Las restricciones marcadas como ``False`` o no soportadas por un algoritmo
    se reportan como limitaciones, no como errores silenciosos.
    """

    model_config = ConfigDict(extra="forbid")

    non_overlap: bool = True
    containment: bool = True
    allow_rotation: bool = True
    max_weight: bool = True
    basic_stability: bool = False
    load_bearing: bool = False
    fragility: bool = False
    unloading_sequence: bool = False

    def active(self) -> list[Constraint]:
        """Lista de restricciones activas mapeadas al vocabulario común."""

        mapping = {
            Constraint.NON_OVERLAP: self.non_overlap,
            Constraint.CONTAINMENT: self.containment,
            Constraint.ORIENTATION: self.allow_rotation,
            Constraint.MAX_WEIGHT: self.max_weight,
            Constraint.BASIC_STABILITY: self.basic_stability,
            Constraint.LOAD_BEARING: self.load_bearing,
            Constraint.FRAGILITY: self.fragility,
            Constraint.UNLOADING_SEQUENCE: self.unloading_sequence,
        }
        return [c for c, enabled in mapping.items() if enabled]


class AlgorithmConfig(BaseModel):
    """Selección y parametrización del algoritmo a ejecutar."""

    model_config = ConfigDict(extra="forbid")

    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    time_limit_seconds: float | None = Field(default=None, gt=0)


class Orientation(BaseModel):
    """Dimensiones finales del ítem tras aplicar la rotación elegida."""

    model_config = ConfigDict(extra="forbid")

    length: float
    width: float
    height: float

    @property
    def dimensions(self) -> Dimensions:
        return Dimensions(self.length, self.width, self.height)


class Point3D(BaseModel):
    """Coordenada 3D (esquina min-corner de un ítem colocado)."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float

    @property
    def position(self) -> Position:
        return Position(self.x, self.y, self.z)


class PackedItem(BaseModel):
    """Ítem colocado dentro de un contenedor con posición y orientación finales."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    container_id: str
    position: Point3D
    orientation: Orientation
    weight: float = 0.0


class UnpackedItem(BaseModel):
    """Ítem que no pudo colocarse, con motivo opcional."""

    model_config = ConfigDict(extra="forbid")

    item_id: str
    reason: str | None = None


class Metrics(BaseModel):
    """Métricas comunes calculables desde cualquier solución."""

    model_config = ConfigDict(extra="forbid")

    volume_utilization: float = 0.0
    waste_volume: float = 0.0
    containers_used: int = 0
    items_packed: int = 0
    items_unpacked: int = 0
    packed_volume: float = 0.0
    unpacked_volume: float = 0.0
    total_item_volume: float = 0.0
    loaded_weight: float = 0.0
    execution_time_seconds: float = 0.0
    constraint_violations: int = 0


class Violation(BaseModel):
    """Violación estructurada reportada por el validador."""

    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    container_id: str | None = None
    item_ids: list[str] = Field(default_factory=list)
    severity: Severity = Severity.ERROR


class ValidationReport(BaseModel):
    """Resultado del validador geométrico."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    violations: list[Violation] = Field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.ERROR)


class ExecutionMetadata(BaseModel):
    """Trazabilidad de una ejecución concreta."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    algorithm_family: AlgorithmFamily | str
    parameters: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None
    service_version: str


class PackingProblem(BaseModel):
    """Instancia normalizada interna lista para ejecutar un algoritmo.

    A diferencia del request de la API, aquí los ítems ya vienen expandidos por
    ``quantity`` (cada unidad es un ítem individual con id único).
    """

    model_config = ConfigDict(extra="forbid")

    problem_type: ProblemType
    request_id: str | None = None
    containers: list[Container]
    items: list[Item]
    constraints: ConstraintFlags = Field(default_factory=ConstraintFlags)
    objective: str = "maximize_volume_utilization"
    algorithm: AlgorithmConfig

    @field_validator("containers")
    @classmethod
    def _non_empty_containers(cls, value: list[Container]) -> list[Container]:
        if not value:
            raise ValueError("Se requiere al menos un contenedor")
        return value


class PackingSolution(BaseModel):
    """Salida normalizada de un algoritmo de packing."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    status: SolutionStatus
    problem_type: ProblemType
    algorithm_name: str
    packed_items: list[PackedItem] = Field(default_factory=list)
    unpacked_items: list[UnpackedItem] = Field(default_factory=list)
    metrics: Metrics = Field(default_factory=Metrics)
    validation_report: ValidationReport | None = None
    execution_metadata: ExecutionMetadata
