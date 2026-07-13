"""Motor de compactación y mejora local sobre soluciones empacadas.

Opera como segunda capa sobre una colocación ya factible: desliza piezas hacia
el origen (bottom-left-back) sin violar contención ni solapamiento, y opcionalmente
reubica ítems en posiciones candidatas más compactas.
"""

from __future__ import annotations

from copy import deepcopy

from ..domain.geometry import (
    EPS,
    AABB,
    Dimensions,
    Position,
    fits_within,
    overlaps,
    supported_area_ratio,
)
from ..domain.models import (
    Container,
    ConstraintFlags,
    PackedItem,
    Point3D,
)


def packed_to_aabb(packed: PackedItem) -> AABB:
    return AABB(
        Position(packed.position.x, packed.position.y, packed.position.z),
        Dimensions(
            packed.orientation.length,
            packed.orientation.width,
            packed.orientation.height,
        ),
    )


def _support_z(
    x0: float, y0: float, x1: float, y1: float, placed: list[AABB]
) -> float:
    """Altura de apoyo para una huella [x0,x1]×[y0,y1]."""

    best = 0.0
    for box in placed:
        bx0, by0, _ = box.min_corner
        bx1, by1, bz1 = box.max_corner
        overlap_x = min(x1, bx1) - max(x0, bx0)
        overlap_y = min(y1, by1) - max(y0, by0)
        if overlap_x > EPS and overlap_y > EPS:
            best = max(best, bz1)
    return best


def _min_along_axis(
    aabb: AABB,
    others: list[AABB],
    container: Dimensions,
    axis: int,
    *,
    floor: float = 0.0,
) -> float:
    """Máximo desplazamiento negativo permitido en un eje (hacia el origen)."""

    current = aabb.min_corner[axis]
    if current <= floor + EPS:
        return current

    lo, hi = floor, current
    best = current
    dims = aabb.dimensions
    pos = list(aabb.min_corner)

    for _ in range(48):
        mid = (lo + hi) / 2.0
        pos[axis] = mid
        trial = AABB(Position(pos[0], pos[1], pos[2]), dims)
        if fits_within(trial, container) and not any(overlaps(trial, o) for o in others):
            best = mid
            hi = mid
        else:
            lo = mid
    return best


def _slide_item(
    packed: PackedItem,
    others: list[AABB],
    container: Container,
    *,
    require_support: bool,
) -> PackedItem:
    """Desliza un ítem hacia (0,0,0) respetando apoyo si se exige."""

    aabb = packed_to_aabb(packed)
    dims = aabb.dimensions
    pos = list(aabb.min_corner)

    # Eje X
    pos[0] = _min_along_axis(aabb, others, container.dimensions, 0)
    aabb = AABB(Position(pos[0], pos[1], pos[2]), dims)

    # Eje Y
    pos[1] = _min_along_axis(aabb, others, container.dimensions, 1)
    aabb = AABB(Position(pos[0], pos[1], pos[2]), dims)

    # Eje Z (con apoyo mínimo)
    x0, y0, z0 = aabb.min_corner
    x1, y1, _ = aabb.max_corner
    floor_z = (
        _support_z(x0, y0, x1, y1, others) if require_support else 0.0
    )
    pos[2] = _min_along_axis(
        aabb, others, container.dimensions, 2, floor=floor_z
    )

    return packed.model_copy(
        update={"position": Point3D(x=pos[0], y=pos[1], z=pos[2])}
    )


def _is_valid_placement(
    packed: PackedItem,
    others: list[AABB],
    container: Container,
    *,
    require_support: bool,
) -> bool:
    trial = packed_to_aabb(packed)
    if not fits_within(trial, container.dimensions):
        return False
    if any(overlaps(trial, o) for o in others):
        return False
    if require_support and trial.min_corner[2] > EPS:
        ratio = supported_area_ratio(trial, others)
        if ratio < 0.5 - EPS:
            return False
    return True


def _manhattan(position: Point3D) -> float:
    return position.x + position.y + position.z


def _candidate_positions(
    others: list[AABB], container: Container
) -> list[Point3D]:
    """Genera posiciones candidatas a partir del origen y caras de cajas vecinas."""

    seen: set[tuple[float, float, float]] = {(0.0, 0.0, 0.0)}
    candidates = [Point3D(x=0.0, y=0.0, z=0.0)]

    for box in others:
        x0, y0, z0 = box.min_corner
        x1, y1, z1 = box.max_corner
        raw = [
            (x1, y0, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x0, y1, z1),
        ]
        for x, y, z in raw:
            key = (round(x, 6), round(y, 6), round(z, 6))
            if key not in seen:
                seen.add(key)
                candidates.append(Point3D(x=x, y=y, z=z))

    # Proyectar candidatos en Z al apoyo disponible (suelo u otras cajas).
    projected: list[Point3D] = []
    proj_seen: set[tuple[float, float, float]] = set()
    for c in candidates:
        # Huella mínima en el origen para estimar apoyo; se refina al probar tamaños.
        z = _support_z(c.x, c.y, c.x + EPS, c.y + EPS, others)
        key = (round(c.x, 6), round(c.y, 6), round(z, 6))
        if key not in proj_seen:
            proj_seen.add(key)
            projected.append(Point3D(x=c.x, y=c.y, z=z))
    return projected


def compact_container_items(
    packed: list[PackedItem],
    container: Container,
    *,
    max_passes: int = 3,
    require_support: bool = False,
) -> list[PackedItem]:
    """Compacta los ítems de un contenedor deslizándolos hacia el origen."""

    if not packed:
        return packed

    result = [p.model_copy() for p in packed]
    for _ in range(max_passes):
        changed = False
        order = sorted(
            range(len(result)),
            key=lambda i: (
                result[i].position.z,
                result[i].position.y,
                result[i].position.x,
            ),
            reverse=True,
        )
        for idx in order:
            others = [packed_to_aabb(result[j]) for j in range(len(result)) if j != idx]
            before = result[idx].position
            result[idx] = _slide_item(
                result[idx],
                others,
                container,
                require_support=require_support,
            )
            after = result[idx].position
            if (
                abs(before.x - after.x) > EPS
                or abs(before.y - after.y) > EPS
                or abs(before.z - after.z) > EPS
            ):
                changed = True
        if not changed:
            break
    return result


def relocation_pass(
    packed: list[PackedItem],
    container: Container,
    *,
    require_support: bool = False,
) -> list[PackedItem]:
    """Intenta reubicar ítems en posiciones candidatas más cercanas al origen."""

    if len(packed) < 2:
        return packed

    result = [p.model_copy() for p in packed]
    order = sorted(
        range(len(result)),
        key=lambda i: _manhattan(result[i].position),
        reverse=True,
    )

    for idx in order:
        current = result[idx]
        others = [packed_to_aabb(result[j]) for j in range(len(result)) if j != idx]
        best = current
        best_score = _manhattan(current.position)

        for pos in _candidate_positions(others, container):
            trial = current.model_copy(update={"position": pos})
            if _is_valid_placement(
                trial, others, container, require_support=require_support
            ):
                score = _manhattan(pos)
                if score + EPS < best_score:
                    best_score = score
                    best = trial
        result[idx] = best

    return result


def improve_solution(
    packed: list[PackedItem],
    containers: list[Container],
    constraints: ConstraintFlags,
    *,
    compaction_passes: int = 3,
    relocation: bool = False,
) -> list[PackedItem]:
    """Aplica compactación (y opcionalmente reubicación) por contenedor."""

    require_support = constraints.basic_stability
    by_container: dict[str, list[PackedItem]] = {}
    for p in packed:
        by_container.setdefault(p.container_id, []).append(p)

    container_by_id = {c.id: c for c in containers}
    improved: list[PackedItem] = []

    for cid, items in by_container.items():
        container = container_by_id[cid]
        compacted = compact_container_items(
            items,
            container,
            max_passes=compaction_passes,
            require_support=require_support,
        )
        if relocation:
            compacted = relocation_pass(
                compacted,
                container,
                require_support=require_support,
            )
            compacted = compact_container_items(
                compacted,
                container,
                max_passes=1,
                require_support=require_support,
            )
        improved.extend(compacted)

    return improved


def positions_moved(before: list[PackedItem], after: list[PackedItem]) -> int:
    """Cuenta ítems cuya posición cambió (útil para trazabilidad)."""

    after_by_id = {p.item_id: p.position for p in after}
    moved = 0
    for p in before:
        pos = after_by_id.get(p.item_id)
        if pos is None:
            continue
        if (
            abs(p.position.x - pos.x) > EPS
            or abs(p.position.y - pos.y) > EPS
            or abs(p.position.z - pos.z) > EPS
        ):
            moved += 1
    return moved
