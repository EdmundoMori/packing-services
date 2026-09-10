"""Metadatos homogéneos de algoritmos.

Misma ficha para implemented, adapter y future: listar, filtrar y ejecutar
por nombre. Sirve al catálogo y al benchmark, no a un espacio de datos.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    PackingMode,
    ProblemType,
)
from ..domain.packing_modes import modes_for_algorithm


class AlgorithmMetadata(BaseModel):
    """Ficha de metadatos de un algoritmo."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    problem_types: list[ProblemType]
    algorithm_family: AlgorithmFamily
    status: AlgorithmStatus
    description: str = ""

    deterministic: bool = True
    supports_random_seed: bool = False
    supports_time_limit: bool = False
    supports_rotation: bool = True
    supports_multi_container: bool = True

    supported_constraints: list[Constraint] = Field(default_factory=list)
    unsupported_constraints: list[Constraint] = Field(default_factory=list)

    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Nombre del parámetro -> descripción breve.",
    )
    metrics: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    # Información específica de adaptadores externos (opcional).
    external_engine: str | None = None
    external_language: str | None = None
    external_repository: str | None = None

    @computed_field
    @property
    def packing_modes(self) -> list[PackingMode]:
        """Modos (offline / online) en los que este algoritmo está disponible."""
        return list(
            modes_for_algorithm(self.name, self.algorithm_family, self.problem_types)
        )

    @property
    def is_executable(self) -> bool:
        """True si el algoritmo puede ejecutarse localmente en esta versión."""

        return self.status in (AlgorithmStatus.IMPLEMENTED, AlgorithmStatus.ADAPTER)


DEFAULT_METRICS = [
    "volume_utilization",
    "waste_volume",
    "containers_used",
    "items_packed",
    "items_unpacked",
    "packed_volume",
    "unpacked_volume",
    "total_item_volume",
    "loaded_weight",
    "execution_time_seconds",
    "constraint_violations",
]
