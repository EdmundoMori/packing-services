"""Separación explícita: observación de política vs verdad del simulador."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from geometry_contract import AxisTriple, validate_margin, validate_positive_dims


@dataclass(frozen=True)
class RevealedBox:
    item_id: str
    flb_mm: tuple[float, float, float]
    realized_oriented_mm: AxisTriple
    nominal_mm: AxisTriple
    orientation_order: tuple[int, int, int]
    envelope_mm: AxisTriple
    envelope_exceeded: bool


@dataclass(frozen=True)
class PolicyObservation:
    """Única vista permitida para el chooser / política."""

    container_mm: AxisTriple
    current_item_id: str
    current_nominal_mm: AxisTriple
    margin_mm: AxisTriple
    revealed: tuple[RevealedBox, ...]
    remaining_count_including_current: int

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "container_mm": self.container_mm.as_tuple(),
            "current_item_id": self.current_item_id,
            "current_nominal_mm": self.current_nominal_mm.as_tuple(),
            "margin_mm": self.margin_mm.as_tuple(),
            "revealed": [
                {
                    "item_id": r.item_id,
                    "flb_mm": r.flb_mm,
                    "realized_oriented_mm": r.realized_oriented_mm.as_tuple(),
                    "nominal_mm": r.nominal_mm.as_tuple(),
                    "orientation_order": r.orientation_order,
                    "envelope_mm": r.envelope_mm.as_tuple(),
                    "envelope_exceeded": r.envelope_exceeded,
                }
                for r in self.revealed
            ],
            "remaining_count_including_current": self.remaining_count_including_current,
        }


class SimulatorTruth:
    """Verdad oculta: el chooser no recibe esta instancia."""

    def __init__(self, realized_by_id: dict[str, AxisTriple]) -> None:
        self._realized_by_id = dict(realized_by_id)
        self._released: set[str] = set()

    def peek_realized(self, item_id: str) -> AxisTriple:
        """Solo el entorno tras fijar la pose."""
        if item_id not in self._realized_by_id:
            raise KeyError(f"realizado desconocido: {item_id}")
        return self._realized_by_id[item_id]

    def mark_released(self, item_id: str) -> None:
        self._released.add(item_id)

    @property
    def released_ids(self) -> frozenset[str]:
        return frozenset(self._released)


@dataclass
class SyntheticItem:
    item_id: str
    nominal_mm: AxisTriple
    realized_mm: AxisTriple


def make_item(item_id: str, nominal: Sequence[float], realized: Sequence[float]) -> SyntheticItem:
    return SyntheticItem(
        item_id=item_id,
        nominal_mm=validate_positive_dims(nominal, f"{item_id}.nominal"),
        realized_mm=validate_positive_dims(realized, f"{item_id}.realized"),
    )


@dataclass
class EpisodeSpec:
    container_mm: AxisTriple
    items: list[SyntheticItem]
    allow_rotation: bool = True

    @staticmethod
    def build(
        container: Sequence[float],
        items: list[tuple[str, Sequence[float], Sequence[float]]],
        *,
        allow_rotation: bool = True,
    ) -> "EpisodeSpec":
        return EpisodeSpec(
            container_mm=validate_positive_dims(container, "container"),
            items=[make_item(i, n, r) for i, n, r in items],
            allow_rotation=allow_rotation,
        )

    def truth(self) -> SimulatorTruth:
        return SimulatorTruth({it.item_id: it.realized_mm for it in self.items})
