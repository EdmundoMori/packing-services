"""Servicio de catálogo de algoritmos.

Expone el registro homogéneo con filtros por tipo de problema, familia, estado
y restricción soportada.
"""

from __future__ import annotations

from ..algorithms.metadata import AlgorithmMetadata
from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    PackingMode,
    ProblemType,
)


class AlgorithmCatalogService:
    """Consultas de solo lectura sobre el catálogo de algoritmos."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def list(
        self,
        problem_type: ProblemType | None = None,
        family: AlgorithmFamily | None = None,
        status: AlgorithmStatus | None = None,
        supported_constraint: Constraint | None = None,
        packing_mode: PackingMode | None = None,
    ) -> list[AlgorithmMetadata]:
        return self.registry.list_metadata(
            problem_type=problem_type,
            family=family,
            status=status,
            supported_constraint=supported_constraint,
            packing_mode=packing_mode,
        )

    def get(self, name: str) -> AlgorithmMetadata:
        return self.registry.get_metadata(name)
