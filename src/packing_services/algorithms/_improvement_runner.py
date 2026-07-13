"""Plantilla común para algoritmos de mejora (segunda capa sobre un constructivo)."""

from __future__ import annotations

from typing import Callable

from ..domain.models import PackedItem, PackingProblem, PackingSolution
from ..utils.timing import measure_time
from ._compaction import positions_moved
from ._constructive_runner import resolve_base_algorithm, run_constructive_base
from .base import PackingAlgorithm, build_solution
from .metadata import AlgorithmMetadata


def run_improvement_layer(
    algorithm: PackingAlgorithm,
    problem: PackingProblem,
    improve_fn: Callable[
        [PackingProblem, PackingSolution],
        tuple[list[PackedItem], dict[str, object]],
    ],
) -> PackingSolution:
    """Ejecuta constructivo base + función de mejora; enriquece trazabilidad."""

    base_name = resolve_base_algorithm(problem)
    with measure_time() as elapsed:
        base_solution = run_constructive_base(problem, base_name)
        before = base_solution.packed_items
        improved, trace = improve_fn(problem, base_solution)
        moved = positions_moved(before, improved)

    meta: AlgorithmMetadata = algorithm.metadata
    solution = build_solution(
        problem=problem,
        metadata=meta,
        packed_items=improved,
        unpacked_items=base_solution.unpacked_items,
        execution_time_seconds=elapsed.seconds,
    )
    return solution.model_copy(
        update={
            "execution_metadata": solution.execution_metadata.model_copy(
                update={
                    "parameters": {
                        **solution.execution_metadata.parameters,
                        "items_relocated": moved,
                        "base_algorithm_used": base_name,
                        "base_items_packed": base_solution.metrics.items_packed,
                        **trace,
                    }
                }
            )
        }
    )
