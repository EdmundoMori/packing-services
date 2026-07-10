"""Interfaz base de algoritmos y utilidades compartidas de construcción de salida.

Todo algoritmo ejecutable implementa ``PackingAlgorithm``: expone su
``metadata`` y un método ``run(problem)`` que devuelve una ``PackingSolution``
normalizada. Las heurísticas constructivas comparten la lógica de generación de
métricas, validación y metadata de ejecución a través de ``build_solution``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .. import SERVICE_VERSION
from ..domain.enums import SolutionStatus
from ..domain.models import (
    ExecutionMetadata,
    PackedItem,
    PackingProblem,
    PackingSolution,
    UnpackedItem,
)
from ..metrics.metrics import compute_metrics
from ..validation.validator import PackingValidator
from .metadata import AlgorithmMetadata


class PackingAlgorithm(ABC):
    """Contrato mínimo de un algoritmo de packing ejecutable."""

    #: Metadatos declarativos del algoritmo (obligatorio en subclases).
    metadata: AlgorithmMetadata

    @abstractmethod
    def run(self, problem: PackingProblem) -> PackingSolution:
        """Ejecuta el algoritmo sobre una instancia y devuelve la solución."""


def build_solution(
    problem: PackingProblem,
    metadata: AlgorithmMetadata,
    packed_items: list[PackedItem],
    unpacked_items: list[UnpackedItem],
    execution_time_seconds: float,
    validate: bool = True,
) -> PackingSolution:
    """Ensambla una ``PackingSolution`` a partir de la colocación calculada.

    Se encarga de: validar la solución con el validador propio, recalcular las
    métricas comunes (incluyendo violaciones) y construir la metadata de
    ejecución para trazabilidad. Así todos los algoritmos producen salidas
    homogéneas.
    """

    validation_report = None
    violations_count = 0
    if validate:
        validator = PackingValidator()
        validation_report = validator.validate(
            containers=problem.containers,
            items=problem.items,
            packed_items=packed_items,
            constraints=problem.constraints,
            expected_unpacked_ids=[u.item_id for u in unpacked_items],
        )
        violations_count = validation_report.error_count

    metrics = compute_metrics(
        containers=problem.containers,
        items=problem.items,
        packed_items=packed_items,
        unpacked_items=unpacked_items,
        constraint_violations=violations_count,
        execution_time_seconds=execution_time_seconds,
    )

    if unpacked_items and packed_items:
        status = SolutionStatus.PARTIAL
    elif not packed_items:
        status = SolutionStatus.FAILED
    else:
        status = SolutionStatus.SUCCESS

    return PackingSolution(
        request_id=problem.request_id,
        status=status,
        problem_type=problem.problem_type,
        algorithm_name=metadata.name,
        packed_items=packed_items,
        unpacked_items=unpacked_items,
        metrics=metrics,
        validation_report=validation_report,
        execution_metadata=ExecutionMetadata(
            algorithm=metadata.name,
            algorithm_family=metadata.algorithm_family,
            parameters=dict(problem.algorithm.parameters),
            random_seed=problem.algorithm.random_seed,
            service_version=SERVICE_VERSION,
        ),
    )
