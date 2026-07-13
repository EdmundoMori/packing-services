"""Motor de palletización por columnas / stacks verticales.

Mantiene columnas de apilamiento en el pallet. Cada ítem se coloca en la
columna factible más bottom-left-back o abre una nueva columna en el suelo.
Opcionalmente exige estabilidad por superficie de soporte y ``load_bearing``.
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
    supported_area_ratio,
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
class StackPalletConfig:
    sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC
    enforce_stability: bool = False
    enforce_load_bearing: bool = False
    min_support_ratio: float = 0.6


@dataclass
class _StackBinState:
    container: Container
    placed: list[AABB] = field(default_factory=list)
    packed_items: list[PackedItem] = field(default_factory=list)
    loaded_weight: float = 0.0
    load_on_top: dict[str, float] = field(default_factory=dict)


def _stack_anchors(state: _StackBinState) -> list[Position]:
    anchors: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)]
    for box in state.placed:
        x0, y0, z0 = box.min_corner
        x1, y1, z1 = box.max_corner
        anchors.extend([(x0, y1, z0), (x1, y0, z0), (x0, y0, z1)])

    unique: list[tuple[float, float, float]] = []
    seen: set[tuple[float, float, float]] = set()
    for x, y, z in anchors:
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in seen:
            seen.add(key)
            unique.append((x, y, z))
    return [
        Position(x, y, z) for x, y, z in sorted(unique, key=lambda t: (t[2], t[1], t[0]))
    ]


class StackPalletPacker:
    """Empaquetador por columnas verticales."""

    def __init__(self, config: StackPalletConfig) -> None:
        self.config = config

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation
        item_by_id = {it.id: it for it in problem.items}

        states = [_StackBinState(container=c) for c in problem.containers]
        ordered = sorted(
            problem.items, key=lambda it: _sort_key(it, self.config.sort_strategy)
        )

        packed: list[PackedItem] = []
        unpacked: list[UnpackedItem] = []

        for item in ordered:
            orientations = unique_orientations(
                item.dimensions, allow_rotation and item.allow_rotation
            )
            placement = self._best_placement(
                item, states, orientations, constraints, item_by_id
            )
            if placement is None:
                unpacked.append(
                    UnpackedItem(
                        item_id=item.id,
                        reason="No se encontró columna o stack factible",
                    )
                )
                continue

            bin_index, position, dims = placement
            packed_item = PackedItem(
                item_id=item.id,
                container_id=states[bin_index].container.id,
                position=Point3D(x=position.x, y=position.y, z=position.z),
                orientation=Orientation(
                    length=dims.length, width=dims.width, height=dims.height
                ),
                weight=item.weight,
            )
            self._place(states[bin_index], position, dims, packed_item)
            packed.append(packed_item)

        return packed, unpacked

    def _best_placement(self, item, states, orientations, constraints, item_by_id):
        best = None
        best_key = None
        for bin_index, state in enumerate(states):
            for position in _stack_anchors(state):
                for dims in orientations:
                    if not self._feasible(
                        state, position, dims, item, constraints, item_by_id
                    ):
                        continue
                    key = (round(position.z, 6), round(position.y, 6), round(position.x, 6))
                    if best_key is None or key < best_key:
                        best_key = key
                        best = (bin_index, position, dims)
        return best

    def _feasible(
        self,
        state: _StackBinState,
        position: Position,
        dims: Dimensions,
        item: Item,
        constraints,
        item_by_id: dict[str, Item],
    ) -> bool:
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

        need_stability = self.config.enforce_stability or constraints.basic_stability
        if need_stability and position.z > EPS:
            ratio = supported_area_ratio(box, state.placed)
            if ratio + EPS < self.config.min_support_ratio:
                return False

        need_bearing = self.config.enforce_load_bearing or constraints.load_bearing
        if need_bearing:
            if not self._load_bearing_ok(state, box, item.weight, item_by_id):
                return False

        return True

    @staticmethod
    def _load_bearing_ok(
        state: _StackBinState,
        box: AABB,
        item_weight: float,
        item_by_id: dict[str, Item],
    ) -> bool:
        if box.position.z <= EPS:
            return True

        ix0, iy0, iz0 = box.min_corner
        ix1, iy1, _ = box.max_corner

        for packed, placed in zip(state.packed_items, state.placed, strict=True):
            if abs(placed.max_corner[2] - iz0) > EPS:
                continue
            sx0, sy0, _ = placed.min_corner
            sx1, sy1, _ = placed.max_corner
            overlap_x = min(ix1, sx1) - max(ix0, sx0)
            overlap_y = min(iy1, sy1) - max(iy0, sy0)
            if overlap_x <= EPS or overlap_y <= EPS:
                continue
            support_item = item_by_id.get(packed.item_id)
            if support_item is None:
                continue
            limit = support_item.max_load_on_top
            if limit is None:
                continue
            projected = state.load_on_top.get(packed.item_id, 0.0) + item_weight
            if projected > limit + EPS:
                return False
        return True

    def _place(
        self,
        state: _StackBinState,
        position: Position,
        dims: Dimensions,
        packed_item: PackedItem,
    ) -> None:
        box = AABB(position=position, dimensions=dims)
        state.placed.append(box)
        state.packed_items.append(packed_item)
        state.loaded_weight += packed_item.weight

        if box.position.z <= EPS:
            return

        ix0, iy0, iz0 = box.min_corner
        ix1, iy1, _ = box.max_corner
        for packed, placed in zip(state.packed_items[:-1], state.placed[:-1], strict=True):
            if abs(placed.max_corner[2] - iz0) > EPS:
                continue
            sx0, sy0, _ = placed.min_corner
            sx1, sy1, _ = placed.max_corner
            overlap_x = min(ix1, sx1) - max(ix0, sx0)
            overlap_y = min(iy1, sy1) - max(iy0, sy0)
            if overlap_x > EPS and overlap_y > EPS:
                state.load_on_top[packed.item_id] = (
                    state.load_on_top.get(packed.item_id, 0.0) + packed_item.weight
                )
