"""Motor de palletización por capas horizontales.

Construye capas sucesivas en ``z``: dentro de cada capa coloca ítems en el
plano ``(x, y)`` con criterio bottom-left-back. Cuando un ítem no cabe en la
capa actual (por altura o por falta de hueco 2D), se cierra la capa y se abre
la siguiente.

Opera sobre pallets/contenedores arbitrarios del input normalizado.
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
class _LayerBinState:
    container: Container
    placed: list[AABB] = field(default_factory=list)
    loaded_weight: float = 0.0
    layer_z: float = 0.0
    layer_height: float = 0.0


def _layer_anchors(state: _LayerBinState, layer_z: float) -> list[Position]:
    anchors: list[tuple[float, float]] = [(0.0, 0.0)]
    for box in state.placed:
        if abs(box.position.z - layer_z) > EPS:
            continue
        x0, y0, _ = box.min_corner
        x1, y1, _ = box.max_corner
        anchors.extend([(x0, y1), (x1, y0)])

    unique: list[tuple[float, float]] = []
    seen: set[tuple[float, float]] = set()
    for x, y in anchors:
        key = (round(x, 6), round(y, 6))
        if key not in seen:
            seen.add(key)
            unique.append((x, y))
    return [
        Position(x, y, layer_z)
        for x, y in sorted(unique, key=lambda t: (t[1], t[0]))
    ]


class LayerPalletPacker:
    """Empaquetador constructivo por capas horizontales."""

    def __init__(self, sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC) -> None:
        self.sort_strategy = sort_strategy

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation

        states = [_LayerBinState(container=c) for c in problem.containers]
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
                        reason="No se encontró capa o posición factible",
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

    def _best_placement(self, item, states, orientations, constraints):
        best = None
        best_key = None
        for bin_index, state in enumerate(states):
            layer_z = state.layer_z
            layer_height = state.layer_height
            for _ in range(64):
                for position in _layer_anchors(state, layer_z):
                    for dims in orientations:
                        if not self._feasible(
                            state, position, dims, item, constraints, layer_z
                        ):
                            continue
                        key = (
                            bin_index,
                            round(position.z, 6),
                            round(position.y, 6),
                            round(position.x, 6),
                        )
                        if best_key is None or key < best_key:
                            best_key = key
                            best = (bin_index, position, dims)
                if best is not None and best[0] == bin_index:
                    break
                if layer_height <= EPS:
                    break
                layer_z = layer_z + layer_height
                layer_height = 0.0
                if layer_z >= state.container.height - EPS:
                    break
        return best

    def _feasible(
        self,
        state: _LayerBinState,
        position: Position,
        dims: Dimensions,
        item: Item,
        constraints,
        layer_z: float,
    ) -> bool:
        if abs(position.z - layer_z) > EPS:
            return False
        if position.z + dims.height > state.container.height + EPS:
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
        return True

    def _place(
        self, state: _LayerBinState, position: Position, dims: Dimensions, item: Item
    ) -> None:
        if abs(position.z - state.layer_z) > EPS:
            state.layer_z = position.z
            state.layer_height = 0.0
        box = AABB(position=position, dimensions=dims)
        state.placed.append(box)
        state.loaded_weight += item.weight
        top = position.z + dims.height
        if top - state.layer_z > state.layer_height:
            state.layer_height = top - state.layer_z
