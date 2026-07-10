"""Adaptador (stub documentado) para fontanf/packingsolver.

Motor avanzado FUTURO para benchmark, stacking-aware packing y palletization
(C++ con scripts Python, MIT). Funciona principalmente por CLI y archivos. Se
prepara la interfaz, pero no se inventan comandos: la integración real exige
verificar el binario y su formato de archivos localmente.
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
    name="packingsolver_adapter",
    display_name="PackingSolver Adapter (fontanf/packingsolver)",
    problem_types=[
        ProblemType.THREE_D_BPP,
        ProblemType.STACKING_AWARE,
        ProblemType.PALLETIZATION,
        ProblemType.BENCHMARK,
    ],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Motor avanzado futuro (tipos box/boxstacks). C++/CLI; integración por "
        "archivos de ítems/bins/parámetros y certificados de salida."
    ),
    supports_time_limit=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
        Constraint.LOAD_BEARING,
        Constraint.UNLOADING_SEQUENCE,
    ],
    metrics=DEFAULT_METRICS,
    limitations=[
        "Stub documentado: no integrado en esta versión",
        "Funciona por CLI/archivos; comandos deben verificarse localmente",
    ],
    external_engine="fontanf/packingsolver",
    external_language="C++",
    external_repository="https://github.com/fontanf/packingsolver",
)


class PackingSolverAdapter(ExternalAdapter):
    metadata = METADATA
    unavailable_hint = (
        "Adaptador stub: la integración con PackingSolver (C++/CLI) es una fase "
        "avanzada. Requiere compilar el binario y verificar el formato de "
        "archivos y comandos localmente."
    )

    def _run_available(self, problem: PackingProblem) -> PackingSolution:  # pragma: no cover
        raise NotImplementedError
