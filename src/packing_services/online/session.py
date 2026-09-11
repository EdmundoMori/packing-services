"""Sesión incremental sobre el motor de puntos extremos ya implementado.

No modifica ``ExtremePointPacker.pack`` (offline). Reutiliza factibilidad,
puntuación y commit de EP para generar candidatas de un solo ítem.
"""

from __future__ import annotations

from ..algorithms._extreme_points import ExtremePointPacker, _BinState
from ..domain.geometry import AABB, Dimensions, supported_area_ratio, unique_orientations
from ..domain.models import (
    ConstraintFlags,
    Container,
    Item,
    Orientation,
    PackedItem,
    Point3D,
)
from .types import PlacementCandidate


def _clone_states(states: list[_BinState]) -> list[_BinState]:
    return [
        _BinState(
            container=state.container,
            placed=list(state.placed),
            extreme_points=list(state.extreme_points),
            loaded_weight=state.loaded_weight,
        )
        for state in states
    ]


class ExtremePointOnlineSession:
    """Estado mutable de contenedores + lista de EP, un ítem cada vez."""

    def __init__(self, containers: list[Container], *, selection: str = "best_fit") -> None:
        self.packer = ExtremePointPacker(selection=selection)
        self.states: list[_BinState] = [_BinState(container=c) for c in containers]
        self.packed: list[PackedItem] = []

    def snapshot(self) -> tuple[list[_BinState], list[PackedItem]]:
        return _clone_states(self.states), list(self.packed)

    def restore(self, snap: tuple[list[_BinState], list[PackedItem]]) -> None:
        self.states = _clone_states(snap[0])
        self.packed = list(snap[1])

    def orientations_for(self, item: Item, constraints: ConstraintFlags) -> list[Dimensions]:
        allow = bool(constraints.allow_rotation) and item.allow_rotation
        return unique_orientations(item.dimensions, allow)

    def candidates(
        self,
        item: Item,
        constraints: ConstraintFlags,
        orientations: list[Dimensions] | None = None,
    ) -> list[PlacementCandidate]:
        oris = orientations or self.orientations_for(item, constraints)
        found: list[PlacementCandidate] = []
        for bin_index, state in enumerate(self.states):
            for position in list(state.extreme_points):
                for dims in oris:
                    if not self.packer._feasible(state, position, dims, item, constraints):
                        continue
                    box = AABB(position=position, dimensions=dims)
                    found.append(
                        PlacementCandidate(
                            item_id=item.id,
                            bin_index=bin_index,
                            container_id=state.container.id,
                            position=position,
                            dimensions=dims,
                            rank_key=self.packer._score(box, state, constraints),
                            support_ratio=_support_ratio_on(box, state.placed),
                        )
                    )
        found.sort(key=lambda c: (c.rank_key, c.bin_index, c.position.as_tuple()))
        return found

    def as_packed_item(self, candidate: PlacementCandidate, item: Item) -> PackedItem:
        return PackedItem(
            item_id=item.id,
            container_id=candidate.container_id,
            position=Point3D(
                x=candidate.position.x,
                y=candidate.position.y,
                z=candidate.position.z,
            ),
            orientation=Orientation(
                length=candidate.dimensions.length,
                width=candidate.dimensions.width,
                height=candidate.dimensions.height,
            ),
            weight=item.weight,
        )

    def commit(self, candidate: PlacementCandidate, item: Item) -> PackedItem:
        packed = self.as_packed_item(candidate, item)
        self.packer._place(
            self.states[candidate.bin_index],
            candidate.position,
            candidate.dimensions,
            item,
        )
        self.packed.append(packed)
        return packed


def _support_ratio_on(box: AABB, placed: list[AABB]) -> float:
    return supported_area_ratio(box, placed)
