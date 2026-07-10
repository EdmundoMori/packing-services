"""Adaptador (stub documentado) para skjolber/3d-bin-container-packing.

Motor principal FUTURO para 3D Bin Packing Offline (Java, Apache-2.0). La
integración real requeriría un wrapper por proceso externo (JVM) o un
microservicio Java. No se implementa integración real porque no hay repositorio
local verificado ni comando de ejecución confirmado.
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
    name="skjolber_adapter",
    display_name="skjolber 3d-bin-container-packing Adapter",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Motor principal futuro para 3D-BPP offline. Java; integración prevista "
        "vía proceso externo (JVM) o microservicio."
    ),
    supports_time_limit=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
    ],
    metrics=DEFAULT_METRICS,
    limitations=[
        "Stub documentado: no integrado en esta versión",
        "Requiere JVM y wrapper por proceso o microservicio Java",
        "Estabilidad/integridad estructural requieren controles personalizados",
    ],
    external_engine="skjolber/3d-bin-container-packing",
    external_language="Java",
    external_repository="https://github.com/skjolber/3d-bin-container-packing",
)


class SkjolberAdapter(ExternalAdapter):
    metadata = METADATA
    unavailable_hint = (
        "Adaptador stub: la integración con skjolber (Java) aún no está "
        "implementada. Requiere JVM y un wrapper por proceso o microservicio."
    )

    def _run_available(self, problem: PackingProblem) -> PackingSolution:  # pragma: no cover
        raise NotImplementedError
