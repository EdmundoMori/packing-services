"""Algoritmos de Cartonization / Order Packing.

A diferencia del 3D-BPP (que usa todos los contenedores), la cartonization
**selecciona una única caja** de un catálogo de cajas candidatas para empacar un
pedido. Estos algoritmos tratan ``problem.containers`` como el catálogo de cajas
candidatas y eligen una según la estrategia:

- ``smallest_feasible_box``: la caja de menor volumen donde caben todos los ítems.
- ``best_box_volume_utilization``: entre las cajas donde caben todos los ítems,
  la de mayor utilización volumétrica (equivale a la más ajustada).

Ambos producen una ``PackingSolution`` estándar (con la caja elegida como
contenedor), por lo que pasan por el validador, las métricas y el benchmark igual
que cualquier otro algoritmo. No garantizan optimalidad.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
    SortStrategy,
)
from ..domain.models import (
    Container,
    PackedItem,
    PackingProblem,
    PackingSolution,
    UnpackedItem,
)
from ..utils.timing import measure_time
from ._extreme_points import ExtremePointPacker
from .base import PackingAlgorithm, build_solution
from .heuristic_3d_bpp import _resolve_sort_strategy
from .metadata import DEFAULT_METRICS, AlgorithmMetadata

_CARTON_CONSTRAINTS = dict(
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
    ],
    unsupported_constraints=[
        Constraint.FRAGILITY,
        Constraint.LOAD_BEARING,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.UNLOADING_SEQUENCE,
        Constraint.ADVANCED_STABILITY,
    ],
)


def _pack_single_box(
    problem: PackingProblem, box: Container, sort_strategy: SortStrategy
) -> tuple[list[PackedItem], list[UnpackedItem]]:
    """Empaqueta todos los ítems del pedido en una única caja candidata."""

    sub_problem = problem.model_copy(update={"containers": [box]})
    packer = ExtremePointPacker(sort_strategy=sort_strategy, selection="best_fit")
    return packer.pack(sub_problem)


def _evaluate_boxes(problem: PackingProblem, sort_strategy: SortStrategy):
    """Evalúa cada caja candidata y devuelve resultados por caja.

    Cada resultado: (box, packed, unpacked, fits_all).
    """

    results = []
    for box in problem.containers:
        packed, unpacked = _pack_single_box(problem, box, sort_strategy)
        results.append((box, packed, unpacked, len(unpacked) == 0))
    return results


class _CartonizationBase(PackingAlgorithm):
    """Lógica común: evalúa cajas y ensambla la solución de la caja elegida."""

    def _solve(self, problem: PackingProblem, select) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        with measure_time() as elapsed:
            evaluated = _evaluate_boxes(problem, sort_strategy)
            box, packed, unpacked = select(evaluated)

        # La instancia efectiva usa solo la caja elegida (para métricas/validación).
        chosen_problem = problem.model_copy(update={"containers": [box]})
        return build_solution(
            problem=chosen_problem,
            metadata=self.metadata,
            packed_items=packed,
            unpacked_items=unpacked,
            execution_time_seconds=elapsed.seconds,
        )


class SmallestFeasibleBox(_CartonizationBase):
    """Elige la caja más pequeña donde caben todos los ítems."""

    metadata = AlgorithmMetadata(
        name="smallest_feasible_box",
        display_name="Smallest Feasible Box",
        problem_types=[ProblemType.CARTONIZATION],
        algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.IMPLEMENTED,
        description=(
            "Ordena las cajas candidatas por volumen ascendente y selecciona la "
            "primera donde caben todos los ítems del pedido."
        ),
        parameters={"sort_strategy": "Orden de ítems dentro de la caja"},
        metrics=DEFAULT_METRICS,
        limitations=[
            "Selecciona una sola caja (baseline); no combina varias cajas",
            "Algoritmo heurístico; la factibilidad depende del empaquetador interno",
        ],
        **_CARTON_CONSTRAINTS,
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return self._solve(problem, self._select)

    @staticmethod
    def _select(evaluated):
        # Cajas ordenadas por volumen ascendente.
        by_volume = sorted(evaluated, key=lambda r: r[0].volume)
        for box, packed, unpacked, fits_all in by_volume:
            if fits_all:
                return box, packed, unpacked
        # Ninguna caja aloja todo: elegir la que empaca más ítems (menor volumen).
        best = max(by_volume, key=lambda r: (len(r[1]), -r[0].volume))
        return best[0], best[1], best[2]


class BestBoxVolumeUtilization(_CartonizationBase):
    """Elige la caja que maximiza la utilización volumétrica alojando todos los ítems."""

    metadata = AlgorithmMetadata(
        name="best_box_volume_utilization",
        display_name="Best Box by Volume Utilization",
        problem_types=[ProblemType.CARTONIZATION],
        algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.IMPLEMENTED,
        description=(
            "Evalúa todas las cajas candidatas y selecciona, entre las que alojan "
            "todos los ítems, la de mayor utilización volumétrica."
        ),
        parameters={"sort_strategy": "Orden de ítems dentro de la caja"},
        metrics=DEFAULT_METRICS,
        limitations=[
            "Selecciona una sola caja (baseline); no combina varias cajas",
            "Algoritmo heurístico; la factibilidad depende del empaquetador interno",
        ],
        **_CARTON_CONSTRAINTS,
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        return self._solve(problem, self._select)

    @staticmethod
    def _packed_volume(packed: list[PackedItem]) -> float:
        return sum(
            p.orientation.length * p.orientation.width * p.orientation.height
            for p in packed
        )

    def _select(self, evaluated):
        feasible = [r for r in evaluated if r[3]]
        if feasible:
            # Mayor utilización = menor volumen de caja que aloja todo.
            best = max(
                feasible,
                key=lambda r: self._packed_volume(r[1]) / r[0].volume,
            )
            return best[0], best[1], best[2]
        # Ninguna aloja todo: maximizar ítems empacados, luego utilización.
        best = max(
            evaluated,
            key=lambda r: (
                len(r[1]),
                self._packed_volume(r[1]) / r[0].volume,
            ),
        )
        return best[0], best[1], best[2]
