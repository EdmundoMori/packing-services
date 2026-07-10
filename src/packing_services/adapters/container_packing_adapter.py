"""Adaptador (stub documentado) para davidmchapman/3DContainerPacking.

Motor principal FUTURO para Container Loading (C#, MIT). Implementa EB-AFIT. La
integración se contempla solo si se verifica el repositorio local o su
documentación; requiere wrapper por proceso (.NET) o microservicio C#.
"""

from __future__ import annotations

from ..algorithms.metadata import DEFAULT_METRICS, AlgorithmMetadata
from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from .base import ExternalAdapter

METADATA = AlgorithmMetadata(
    name="container_packing_adapter",
    display_name="3DContainerPacking Adapter (EB-AFIT)",
    problem_types=[ProblemType.CONTAINER_LOADING, ProblemType.THREE_D_BPP],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Motor principal futuro para Container Loading. C#; implementa EB-AFIT. "
        "Integración prevista vía proceso .NET o microservicio."
    ),
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.ORIENTATION,
    ],
    unsupported_constraints=[
        Constraint.MAX_WEIGHT,
        Constraint.LOAD_BEARING,
        Constraint.FRAGILITY,
        Constraint.UNLOADING_SEQUENCE,
    ],
    metrics=DEFAULT_METRICS,
    limitations=[
        "Stub documentado: no integrado en esta versión",
        "EB-AFIT no expone restricciones avanzadas de peso/estabilidad por defecto",
        "Requiere runtime .NET y wrapper por proceso o microservicio C#",
    ],
    external_engine="davidmchapman/3DContainerPacking",
    external_language="C#",
    external_repository="https://github.com/davidmchapman/3DContainerPacking",
)


class ContainerPackingAdapter(ExternalAdapter):
    metadata = METADATA
    unavailable_hint = (
        "Adaptador stub: la integración con 3DContainerPacking (C#/EB-AFIT) es "
        "una fase posterior. Requiere runtime .NET y wrapper por proceso."
    )

    def _run_available(self, problem: PackingProblem) -> PackingSolution:  # pragma: no cover
        raise NotImplementedError
