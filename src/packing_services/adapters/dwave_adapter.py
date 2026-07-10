"""Adaptador (stub documentado) para dwave-examples/3d-bin-packing.

Referencia matemática / benchmark basada en un Constrained Quadratic Model
(Apache-2.0). Depende del Leap hybrid CQM solver (servicio externo con
credenciales), por lo que NO es un motor operativo inicial. Queda documentado
como referencia avanzada de formulación.
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
    name="dwave_adapter",
    display_name="D-Wave CQM Adapter (dwave-examples/3d-bin-packing)",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.BENCHMARK],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Referencia matemática (Constrained Quadratic Model) y benchmark. "
        "Depende del Leap hybrid CQM solver (servicio externo con credenciales)."
    ),
    deterministic=False,
    supports_random_seed=True,
    supports_time_limit=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
    ],
    unsupported_constraints=[
        Constraint.ADVANCED_STABILITY,
        Constraint.FRAGILITY,
        Constraint.LOAD_BEARING,
        Constraint.CENTER_OF_GRAVITY,
    ],
    metrics=DEFAULT_METRICS,
    limitations=[
        "Stub documentado: referencia avanzada, no motor operativo inicial",
        "Requiere credenciales y el Leap hybrid CQM solver",
    ],
    external_engine="dwave-examples/3d-bin-packing",
    external_language="Python",
    external_repository="https://github.com/dwave-examples/3d-bin-packing",
)


class DWaveAdapter(ExternalAdapter):
    metadata = METADATA
    unavailable_hint = (
        "Adaptador stub: D-Wave es una referencia avanzada. Requiere "
        "credenciales del Leap hybrid CQM solver y no es un motor operativo "
        "inicial."
    )

    def _run_available(self, problem: PackingProblem) -> PackingSolution:  # pragma: no cover
        raise NotImplementedError
