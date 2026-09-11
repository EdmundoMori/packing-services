"""Tipos del bucle online (candidata de colocación)."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.geometry import AABB, Dimensions, Position
from ..domain.models import Item


@dataclass(frozen=True)
class PlacementCandidate:
    """Una colocación legal *ahora* para un ítem (aún no comprometida)."""

    item_id: str
    bin_index: int
    container_id: str
    position: Position
    dimensions: Dimensions
    rank_key: tuple
    support_ratio: float

    @property
    def box(self) -> AABB:
        return AABB(position=self.position, dimensions=self.dimensions)


@dataclass(frozen=True)
class StepOption:
    """Par (ítem del buffer, candidata legal) que la política puede elegir."""

    item: Item
    candidate: PlacementCandidate
    buffer_index: int
