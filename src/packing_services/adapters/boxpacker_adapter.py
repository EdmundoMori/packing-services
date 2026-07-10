"""Adaptador (stub documentado) para dvdoug/BoxPacker.

Motor principal FUTURO para Cartonization / Order Packing (PHP, MIT). Requiere
un wrapper por proceso externo o un microservicio PHP separado. No se implementa
integración real en esta versión.
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
    name="boxpacker_adapter",
    display_name="BoxPacker Adapter (dvdoug/BoxPacker)",
    problem_types=[ProblemType.CARTONIZATION, ProblemType.THREE_D_BPP],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Motor principal futuro para cartonization. PHP; integración prevista "
        "como microservicio separado o wrapper por proceso."
    ),
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
    ],
    metrics=DEFAULT_METRICS,
    limitations=[
        "Stub documentado: no integrado en esta versión",
        "Requiere microservicio PHP o wrapper por proceso (fase posterior)",
    ],
    external_engine="dvdoug/BoxPacker",
    external_language="PHP",
    external_repository="https://github.com/dvdoug/BoxPacker",
)


class BoxPackerAdapter(ExternalAdapter):
    metadata = METADATA
    unavailable_hint = (
        "Adaptador stub: la integración con BoxPacker (PHP) es una fase "
        "posterior. Requiere un microservicio PHP o wrapper por proceso."
    )

    def _run_available(self, problem: PackingProblem) -> PackingSolution:  # pragma: no cover
        raise NotImplementedError
