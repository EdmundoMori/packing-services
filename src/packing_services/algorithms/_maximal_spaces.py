"""Motor constructivo por espacios vacíos máximos (Maximal Empty Spaces).

Mantiene una lista de cajas axis-aligned de espacio libre por contenedor. Tras
cada colocación, divide el espacio usado con cortes guillotina y elimina espacios
dominados (contenidos en otro). Todo deriva de ``PackingProblem`` (contenedores,
ítems, restricciones, parámetros); no hay dimensiones fijas en código.
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
from ._constructive import order_items


@dataclass
class _EmptySpace:
    position: Position
    dimensions: Dimensions

    def to_aabb(self) -> AABB:
        return AABB(self.position, self.dimensions)

    def volume(self) -> float:
        return self.dimensions.volume


@dataclass
class _BinState:
    container: Container
    spaces: list[_EmptySpace] = field(default_factory=list)
    placed: list[AABB] = field(default_factory=list)
    loaded_weight: float = 0.0

    def __post_init__(self) -> None:
        if not self.spaces:
            c = self.container
            self.spaces = [
                _EmptySpace(
                    Position(0.0, 0.0, 0.0),
                    Dimensions(c.length, c.width, c.height),
                )
            ]


def _space_contains(outer: _EmptySpace, inner: _EmptySpace) -> bool:
    ox, oy, oz = outer.position.as_tuple()
    ix, iy, iz = inner.position.as_tuple()
    od = outer.dimensions
    id_ = inner.dimensions
    return (
        ix >= ox - EPS
        and iy >= oy - EPS
        and iz >= oz - EPS
        and ix + id_.length <= ox + od.length + EPS
        and iy + id_.width <= oy + od.width + EPS
        and iz + id_.height <= oz + od.height + EPS
    )


def _prune_spaces(spaces: list[_EmptySpace]) -> list[_EmptySpace]:
    kept: list[_EmptySpace] = []
    for i, s in enumerate(spaces):
        if s.dimensions.volume <= EPS:
            continue
        dominated = any(
            i != j and _space_contains(spaces[j], s) for j in range(len(spaces))
        )
        if not dominated:
            kept.append(s)
    return kept


def _guillotine_split(space: _EmptySpace, box: AABB) -> list[_EmptySpace]:
    sx, sy, sz = space.position.as_tuple()
    sl, sw, sh = space.dimensions.length, space.dimensions.width, space.dimensions.height
    px, py, pz = box.min_corner
    pl, pw, ph = box.dimensions.length, box.dimensions.width, box.dimensions.height

    result: list[_EmptySpace] = []

    right_len = (sx + sl) - (px + pl)
    if right_len > EPS:
        result.append(
            _EmptySpace(
                Position(px + pl, sy, sz),
                Dimensions(right_len, sw, sh),
            )
        )

    front_w = (sy + sw) - (py + pw)
    if front_w > EPS:
        result.append(
            _EmptySpace(
                Position(sx, py + pw, sz),
                Dimensions(pl, front_w, sh),
            )
        )

    top_h = (sz + sh) - (pz + ph)
    if top_h > EPS:
        result.append(
            _EmptySpace(
                Position(sx, sy, pz + ph),
                Dimensions(pl, pw, top_h),
            )
        )

    return result


def _fits_in_space(space: _EmptySpace, position: Position, dims: Dimensions) -> bool:
    sx, sy, sz = space.position.as_tuple()
    sl, sw, sh = space.dimensions.length, space.dimensions.width, space.dimensions.height
    px, py, pz = position.as_tuple()
    return (
        px >= sx - EPS
        and py >= sy - EPS
        and pz >= sz - EPS
        and px + dims.length <= sx + sl + EPS
        and py + dims.width <= sy + sw + EPS
        and pz + dims.height <= sz + sh + EPS
    )


class MaximalSpacePacker:
    """Empaquetador por espacios vacíos máximos con cortes guillotina."""

    def __init__(
        self,
        sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC,
        selection: str = "best_fit",
    ) -> None:
        self.sort_strategy = sort_strategy
        self.selection = selection

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation

        states = [_BinState(container=c) for c in problem.containers]
        ordered = order_items(problem.items, self.sort_strategy)

        packed: list[PackedItem] = []
        unpacked: list[UnpackedItem] = []

        for item in ordered:
            orientations = unique_orientations(
                item.dimensions, allow_rotation and item.allow_rotation
            )
            placement = self._best_placement(item, states, orientations, constraints)
            if placement is None:
                unpacked.append(
                    UnpackedItem(
                        item_id=item.id,
                        reason="No se encontró espacio máximo factible",
                    )
                )
                continue

            bin_index, space_index, position, dims = placement
            self._place(states[bin_index], space_index, position, dims, item)
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

    def _best_placement(self, item, states, orientations, constraints):
        best = None
        best_key = None

        for bin_index, state in enumerate(states):
            for space_index, space in enumerate(state.spaces):
                if space.dimensions.volume <= EPS:
                    continue
                origin = space.position
                for dims in orientations:
                    if not _fits_in_space(space, origin, dims):
                        continue
                    if not self._feasible(state, origin, dims, item, constraints):
                        continue
                    box = AABB(origin, dims)
                    key = self._score(box, space, state)
                    if best_key is None or key < best_key:
                        best_key = key
                        best = (bin_index, space_index, origin, dims)
        return best

    def _feasible(self, state, position, dims, item, constraints) -> bool:
        box = AABB(position, dims)
        if constraints.containment and not fits_within(
            box, state.container.dimensions
        ):
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
        return True

    def _score(self, box: AABB, space: _EmptySpace, state: _BinState):
        pos = box.position
        blb = (round(pos.z, 6), round(pos.y, 6), round(pos.x, 6))
        if self.selection == "best_fit":
            leftover = space.dimensions.volume - box.dimensions.volume
            return (round(leftover, 6),) + blb
        return blb

    def _place(
        self,
        state: _BinState,
        space_index: int,
        position: Position,
        dims: Dimensions,
        item: Item,
    ) -> None:
        box = AABB(position, dims)
        state.placed.append(box)
        state.loaded_weight += item.weight

        used_space = state.spaces.pop(space_index)
        state.spaces.extend(_guillotine_split(used_space, box))
        state.spaces = _prune_spaces(state.spaces)
