"""Operaciones de mejora local genéricas (swap, orientación, reducción de bins)."""

from __future__ import annotations

from ..domain.geometry import EPS, unique_orientations
from ..domain.models import Orientation, PackedItem, PackingProblem, Point3D
from ._compaction import (
    _candidate_positions,
    _is_valid_placement,
    packed_to_aabb,
)


def _item_by_id(problem: PackingProblem) -> dict[str, object]:
    return {it.id: it for it in problem.items}


def _group_by_container(packed: list[PackedItem]) -> dict[str, list[PackedItem]]:
    groups: dict[str, list[PackedItem]] = {}
    for p in packed:
        groups.setdefault(p.container_id, []).append(p)
    return groups


def orientation_improvement_pass(
    packed: list[PackedItem],
    problem: PackingProblem,
) -> list[PackedItem]:
    """Prueba orientaciones alternativas en la misma posición."""

    require_support = problem.constraints.basic_stability
    items = _item_by_id(problem)
    container_by_id = {c.id: c for c in problem.containers}
    result = [p.model_copy() for p in packed]

    for idx, current in enumerate(result):
        item = items.get(current.item_id)
        if item is None:
            continue
        allow_rot = problem.constraints.allow_rotation and item.allow_rotation
        orientations = unique_orientations(item.dimensions, allow_rot)
        container = container_by_id[current.container_id]
        others = [
            packed_to_aabb(result[j]) for j in range(len(result)) if j != idx
        ]
        best = current
        best_score = _manhattan(current.position)

        for dims in orientations:
            trial = current.model_copy(
                update={
                    "orientation": Orientation(
                        length=dims.length, width=dims.width, height=dims.height
                    )
                }
            )
            if _is_valid_placement(
                trial, others, container, require_support=require_support
            ):
                score = _manhattan(trial.position)
                if score + EPS < best_score:
                    best_score = score
                    best = trial
        result[idx] = best

    return result


def _manhattan(pos: Point3D) -> float:
    return pos.x + pos.y + pos.z


def swap_improvement_pass(
    packed: list[PackedItem],
    problem: PackingProblem,
    *,
    max_attempts: int | None = None,
) -> tuple[list[PackedItem], int]:
    """Intercambia posiciones/orientaciones entre pares si mejora compactación."""

    require_support = problem.constraints.basic_stability
    container_by_id = {c.id: c for c in problem.containers}
    result = [p.model_copy() for p in packed]
    n = len(result)
    limit = max_attempts if max_attempts is not None else max(1, n * (n - 1) // 2)
    swaps = 0

    for attempt in range(limit):
        if n < 2:
            break
        i = attempt % n
        j = (attempt * 7 + 1) % n
        if i == j:
            continue

        a, b = result[i], result[j]
        if a.container_id != b.container_id:
            continue

        container = container_by_id[a.container_id]
        others = [packed_to_aabb(result[k]) for k in range(n) if k not in (i, j)]

        trial_a = b.model_copy(update={"item_id": a.item_id, "weight": a.weight})
        trial_b = a.model_copy(update={"item_id": b.item_id, "weight": b.weight})

        if not (
            _is_valid_placement(
                trial_a,
                others + [packed_to_aabb(trial_b)],
                container,
                require_support=require_support,
            )
            and _is_valid_placement(
                trial_b,
                others + [packed_to_aabb(trial_a)],
                container,
                require_support=require_support,
            )
        ):
            continue

        before_score = _manhattan(a.position) + _manhattan(b.position)
        after_score = _manhattan(trial_a.position) + _manhattan(trial_b.position)
        if after_score + EPS < before_score:
            result[i] = trial_a
            result[j] = trial_b
            swaps += 1

    return result, swaps


def bin_reduction_pass(
    packed: list[PackedItem],
    problem: PackingProblem,
) -> tuple[list[PackedItem], int]:
    """Intenta vaciar el último contenedor usado moviendo piezas a otros."""

    require_support = problem.constraints.basic_stability
    container_by_id = {c.id: c for c in problem.containers}
    container_order = [c.id for c in problem.containers]

    by_c = _group_by_container(packed)
    used = [cid for cid in container_order if by_c.get(cid)]
    if len(used) < 2:
        return packed, 0

    target_cid = used[-1]
    target_items = [p.model_copy() for p in by_c[target_cid]]
    rest = [p for p in packed if p.container_id != target_cid]
    moved_count = 0

    for item_packed in target_items:
        placed = False
        for dest_cid in used[:-1]:
            dest_container = container_by_id[dest_cid]
            dest_items = [p for p in rest if p.container_id == dest_cid]
            others = [packed_to_aabb(p) for p in dest_items]

            items = _item_by_id(problem)
            src_item = items.get(item_packed.item_id)
            if src_item is None:
                break
            allow_rot = problem.constraints.allow_rotation and src_item.allow_rotation
            orientations = unique_orientations(src_item.dimensions, allow_rot)

            for pos in _candidate_positions(others, dest_container):
                for dims in orientations:
                    trial = item_packed.model_copy(
                        update={
                            "container_id": dest_cid,
                            "position": pos,
                            "orientation": Orientation(
                                length=dims.length,
                                width=dims.width,
                                height=dims.height,
                            ),
                        }
                    )
                    if _is_valid_placement(
                        trial,
                        others,
                        dest_container,
                        require_support=require_support,
                    ):
                        if (
                            problem.constraints.max_weight
                            and dest_container.max_weight is not None
                        ):
                            loaded = sum(p.weight for p in dest_items) + trial.weight
                            if loaded > dest_container.max_weight + EPS:
                                continue
                        rest.append(trial)
                        moved_count += 1
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break

        if not placed:
            rest.append(item_packed)

    return rest, moved_count


def apply_improvement_passes(
    packed: list[PackedItem],
    problem: PackingProblem,
    *,
    passes: int,
    op: str,
    max_swap_attempts: int | None = None,
) -> tuple[list[PackedItem], dict[str, object]]:
    """Ejecuta ``passes`` rondas de la operación indicada."""

    result = packed
    trace: dict[str, object] = {"improvement_op": op, "passes_requested": passes}
    total_swaps = 0
    total_moved_bins = 0

    for _ in range(max(1, passes)):
        if op == "orientation":
            result = orientation_improvement_pass(result, problem)
        elif op == "swap":
            result, n = swap_improvement_pass(
                result, problem, max_attempts=max_swap_attempts
            )
            total_swaps += n
        elif op == "bin_reduction":
            result, n = bin_reduction_pass(result, problem)
            total_moved_bins += n
        else:
            raise ValueError(f"Operación de mejora desconocida: {op}")

    if op == "swap":
        trace["swap_count"] = total_swaps
    if op == "bin_reduction":
        trace["items_moved_between_containers"] = total_moved_bins

    return result, trace
