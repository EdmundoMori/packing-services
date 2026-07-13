"""Algoritmo ``multi_box_cartonization`` — Multi-box Cartonization.

Permite usar **más de una caja** del catálogo para empacar un pedido: en cada
iteración elige una plantilla de caja, instancia un contenedor con id único
(``BOX_S#1``, ``BOX_S#2``, …) y empaca el máximo de ítems pendientes. Repite
hasta empacar todo o quedarse sin progreso.
"""

from __future__ import annotations

from collections import defaultdict

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
    SortStrategy,
)
from ..domain.models import (
    AlgorithmConfig,
    Container,
    Item,
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


def _packed_volume(packed: list[PackedItem]) -> float:
    return sum(
        p.orientation.length * p.orientation.width * p.orientation.height for p in packed
    )


def _try_pack_in_box(
    problem: PackingProblem,
    box: Container,
    items: list[Item],
    sort_strategy: SortStrategy,
) -> tuple[list[PackedItem], list[UnpackedItem]]:
    sub = problem.model_copy(
        update={
            "containers": [box],
            "items": items,
            "algorithm": problem.algorithm.model_copy(
                update={"parameters": {"sort_strategy": sort_strategy.value}}
            ),
        }
    )
    packer = ExtremePointPacker(sort_strategy=sort_strategy, selection="best_fit")
    return packer.pack(sub)


def _select_box_template(
    problem: PackingProblem,
    remaining: list[Item],
    sort_strategy: SortStrategy,
    strategy: str,
) -> tuple[Container | None, list[PackedItem], list[UnpackedItem]]:
    """Elige la plantilla de caja para la siguiente iteración."""

    evaluations: list[tuple[Container, list[PackedItem], list[UnpackedItem], float]] = []
    for template in problem.containers:
        packed, unpacked = _try_pack_in_box(problem, template, remaining, sort_strategy)
        if not packed:
            continue
        util = _packed_volume(packed) / template.volume if template.volume > 0 else 0.0
        evaluations.append((template, packed, unpacked, util))

    if not evaluations:
        return None, [], remaining

    if strategy == "best_utilization":
        template, packed, unpacked, _ = max(
            evaluations,
            key=lambda r: (r[3], len(r[1]), -r[0].volume),
        )
    else:
        template, packed, unpacked, _ = min(
            evaluations,
            key=lambda r: (r[0].volume, -len(r[1])),
        )
    return template, packed, unpacked


class MultiBoxCartonization(PackingAlgorithm):
    """Cartonization greedy multi-caja."""

    metadata = AlgorithmMetadata(
        name="multi_box_cartonization",
        display_name="Multi-box Cartonization",
        problem_types=[ProblemType.CARTONIZATION],
        algorithm_family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.IMPLEMENTED,
        description=(
            "Empaca un pedido usando varias cajas del catálogo: en cada paso "
            "elige la plantilla más adecuada, instancia una caja con id único "
            "y coloca el máximo de ítems pendientes hasta completar el pedido."
        ),
        parameters={
            "sort_strategy": "Orden de ítems dentro de cada caja",
            "box_selection": "smallest_first | best_utilization (por defecto smallest_first)",
        },
        metrics=DEFAULT_METRICS,
        limitations=[
            "Heurística greedy; no garantiza el mínimo número de cajas",
            "La factibilidad depende del empaquetador interno por caja",
        ],
        **_CARTON_CONSTRAINTS,
    )

    def run(self, problem: PackingProblem) -> PackingSolution:
        sort_strategy = _resolve_sort_strategy(
            problem.algorithm.parameters.get("sort_strategy")
        )
        box_selection = str(
            problem.algorithm.parameters.get("box_selection", "smallest_first")
        )

        instances: list[Container] = []
        instance_counts: dict[str, int] = defaultdict(int)
        packed_all: list[PackedItem] = []
        remaining = list(problem.items)

        with measure_time() as elapsed:
            while remaining:
                template, packed, _ = _select_box_template(
                    problem, remaining, sort_strategy, box_selection
                )
                if template is None or not packed:
                    break

                instance_counts[template.id] += 1
                inst_id = f"{template.id}#{instance_counts[template.id]}"
                box = template.model_copy(update={"id": inst_id})
                instances.append(box)

                packed_ids = {p.item_id for p in packed}
                remapped = [
                    p.model_copy(update={"container_id": inst_id}) for p in packed
                ]
                packed_all.extend(remapped)
                remaining = [it for it in remaining if it.id not in packed_ids]

        unpacked_all = [
            UnpackedItem(item_id=it.id, reason="No cabe en ninguna caja del catálogo")
            for it in remaining
        ]

        params = dict(problem.algorithm.parameters)
        params["boxes_used"] = len(instances)
        params["box_instance_ids"] = [b.id for b in instances]

        effective = problem.model_copy(
            update={
                "containers": instances or list(problem.containers),
                "algorithm": AlgorithmConfig(
                    name=problem.algorithm.name,
                    parameters=params,
                    random_seed=problem.algorithm.random_seed,
                ),
            }
        )

        return build_solution(
            problem=effective,
            metadata=self.metadata,
            packed_items=packed_all,
            unpacked_items=unpacked_all,
            execution_time_seconds=elapsed.seconds,
        )
