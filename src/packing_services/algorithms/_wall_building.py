"""Motor de heurística wall-building para Container Loading.

Coloca ítems formando **paredes verticales** contra la cara trasera del
contenedor (``y = 0``): cada ítem toca el plano de la pared o se apila sobre
otro ítem que ya forma parte de la misma pared. Se extiende en ``x`` a lo largo
de la pared y en ``z`` hacia arriba.

No garantiza optimalidad; opera sobre cualquier instancia normalizada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import SortStrategy
from ..domain.geometry import (
    EPS,
    AABB,
    Dimensions,
    Position,
    fits_within,
    overlaps,
    unique_orientations,
)
from ..domain.models import (
    Container,
    Item,
    Orientation,
    PackedItem,
    PackingProblem,
    Point3D,
    UnpackedItem,
)
from ._constructive import _sort_key


@dataclass
class _WallBinState:
    container: Container
    placed: list[AABB] = field(default_factory=list)
    loaded_weight: float = 0.0


def _touches_wall(box: AABB) -> bool:
    return box.position.y <= EPS


def _wall_anchors(state: _WallBinState) -> list[Position]:
    """Genera posiciones candidatas sobre la pared (``y = 0``)."""

    anchors: list[tuple[float, float]] = [(0.0, 0.0)]
    for box in state.placed:
        if not _touches_wall(box):
            continue
        x0, _, z0 = box.min_corner
        x1, _, z1 = box.max_corner
        anchors.extend([(x0, z1), (x1, z0)])

    unique: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for x, z in anchors:
        key = (round(x, 6), round(z, 6))
        if key not in seen:
            seen.add(key)
            unique.append((x, z))
    return [Position(x, 0.0, z) for x, z in sorted(unique, key=lambda t: (t[1], t[0]))]


class WallBuildingPacker:
    """Empaquetador constructivo por paredes verticales."""

    def __init__(self, sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC) -> None:
        self.sort_strategy = sort_strategy

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation

        states = [_WallBinState(container=c) for c in problem.containers]
        ordered = sorted(problem.items, key=lambda it: _sort_key(it, self.sort_strategy))

        packed: list[PackedItem] = []
        unpacked: list[UnpackedItem] = []

        for item in ordered:
            orientations = unique_orientations(
                item.dimensions, allow_rotation and item.allow_rotation
            )
            placement = self._best_wall_placement(item, states, orientations, constraints)
            if placement is None:
                unpacked.append(
                    UnpackedItem(
                        item_id=item.id,
                        reason="No se encontró posición factible en pared",
                    )
                )
                continue

            bin_index, position, dims = placement
            self._place(states[bin_index], position, dims, item)
            packed.append(
                PackedItem(
                    item_id=item.id,
                    container_id=states[bin_index].container.id,
                    position=Point3D(x=position.x, y=position.y, z=position.z),
                    orientation=Orientation(
                        length=dims.length, width=dims.width, height=dims.height
                    ),
                    weight=item.weight,
                )
            )

        return packed, unpacked

    def _best_wall_placement(self, item, states, orientations, constraints):
        best = None
        best_key = None
        for bin_index, state in enumerate(states):
            for position in _wall_anchors(state):
                for dims in orientations:
                    if not self._feasible_wall(state, position, dims, item, constraints):
                        continue
                    key = (round(position.z, 6), round(position.x, 6))
                    if best_key is None or key < best_key:
                        best_key = key
                        best = (bin_index, position, dims)
        return best

    def _feasible_wall(
        self, state: _WallBinState, position: Position, dims: Dimensions, item: Item, constraints
    ) -> bool:
        if position.y > EPS:
            return False
        box = AABB(position=position, dimensions=dims)
        if constraints.containment and not fits_within(box, state.container.dimensions):
            return False
        if (
            constraints.max_weight
            and state.container.max_weight is not None
            and state.loaded_weight + item.weight > state.container.max_weight + EPS
        ):
            return False
        if constraints.non_overlap:
            for placed in state.placed:
                if overlaps(box, placed):
                    return False
        if not _touches_wall(box):
            return False
        if not self._supported_on_wall(box, state):
            return False
        return True

    @staticmethod
    def _supported_on_wall(box: AABB, state: _WallBinState) -> bool:
        """En ``z > 0`` exige apoyo sobre la pared o sobre otro ítem de la pared."""

        if box.position.z <= EPS:
            return True
        x0, _, z0 = box.min_corner
        x1, _, _ = box.max_corner
        footprint_area = (x1 - x0) * box.dimensions.width
        if footprint_area <= EPS:
            return False
        supported = 0.0
        for placed in state.placed:
            if not _touches_wall(placed):
                continue
            px0, _, pz1 = placed.min_corner
            px1, _, _ = placed.max_corner
            if abs(pz1 - z0) > EPS:
                continue
            overlap_x = min(x1, px1) - max(x0, px0)
            if overlap_x > EPS:
                supported += overlap_x * min(box.dimensions.width, placed.dimensions.width)
        return supported >= 0.5 * footprint_area - EPS

    def _place(
        self, state: _WallBinState, position: Position, dims: Dimensions, item: Item
    ) -> None:
        state.placed.append(AABB(position=position, dimensions=dims))
        state.loaded_weight += item.weight
