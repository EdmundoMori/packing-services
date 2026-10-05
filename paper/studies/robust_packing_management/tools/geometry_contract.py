"""Contrato geométrico G1: dims, márgenes, envolvente, certificado."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations
from typing import Iterable, Sequence

EPS_MM = 1e-6


def _finite_positive(x: float, name: str) -> float:
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise ValueError(f"{name} debe ser numérico")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{name} no finito: {v}")
    if v <= 0:
        raise ValueError(f"{name} debe ser > 0, got {v}")
    return v


def _finite_nonneg(x: float, name: str) -> float:
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        raise ValueError(f"{name} debe ser numérico")
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{name} no finito: {v}")
    if v < 0:
        raise ValueError(f"{name} debe ser >= 0, got {v}")
    return v


@dataclass(frozen=True)
class AxisTriple:
    """Triple (length, width, height) en mm."""

    length: float
    width: float
    height: float

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.length, self.width, self.height)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height

    def permute(self, order: tuple[int, int, int]) -> "AxisTriple":
        vals = self.as_tuple()
        return AxisTriple(vals[order[0]], vals[order[1]], vals[order[2]])


def validate_positive_dims(dims: Sequence[float], name: str = "dims") -> AxisTriple:
    if len(dims) != 3:
        raise ValueError(f"{name} requiere 3 componentes")
    return AxisTriple(
        _finite_positive(dims[0], f"{name}[0]"),
        _finite_positive(dims[1], f"{name}[1]"),
        _finite_positive(dims[2], f"{name}[2]"),
    )


def validate_margin(margin: Sequence[float], name: str = "margin") -> AxisTriple:
    if len(margin) != 3:
        raise ValueError(f"{name} requiere 3 componentes")
    return AxisTriple(
        _finite_nonneg(margin[0], f"{name}[0]"),
        _finite_nonneg(margin[1], f"{name}[1]"),
        _finite_nonneg(margin[2], f"{name}[2]"),
    )


# Índices de permutación sobre (L, W, H) de catálogo.
ORIENTATION_ORDERS: tuple[tuple[int, int, int], ...] = tuple(
    perm for perm in permutations((0, 1, 2))
)


def unique_orientation_orders(nominal: AxisTriple) -> list[tuple[int, int, int]]:
    """Permutaciones distintas de dims (hasta 6)."""
    seen: set[tuple[float, float, float]] = set()
    out: list[tuple[int, int, int]] = []
    for order in ORIENTATION_ORDERS:
        oriented = nominal.permute(order).as_tuple()
        if oriented not in seen:
            seen.add(oriented)
            out.append(order)
    return out


@dataclass(frozen=True)
class OrientedSizes:
    """Definición única: distingue nominal, margen, envelope y realizado."""

    orientation_order: tuple[int, int, int]
    nominal_oriented: AxisTriple
    margin_oriented: AxisTriple
    envelope: AxisTriple
    realized_oriented: AxisTriple | None = None

    @staticmethod
    def from_catalogue(
        nominal: AxisTriple,
        margin: AxisTriple,
        orientation_order: tuple[int, int, int],
        realized: AxisTriple | None = None,
    ) -> "OrientedSizes":
        nom_o = nominal.permute(orientation_order)
        mar_o = margin.permute(orientation_order)
        env = AxisTriple(
            nom_o.length + mar_o.length,
            nom_o.width + mar_o.width,
            nom_o.height + mar_o.height,
        )
        real_o = None if realized is None else realized.permute(orientation_order)
        return OrientedSizes(orientation_order, nom_o, mar_o, env, real_o)


def envelope_exceeded(realized_oriented: AxisTriple, envelope: AxisTriple) -> bool:
    return (
        realized_oriented.length > envelope.length + EPS_MM
        or realized_oriented.width > envelope.width + EPS_MM
        or realized_oriented.height > envelope.height + EPS_MM
    )


def realized_subseteq_envelope(realized_oriented: AxisTriple, envelope: AxisTriple) -> bool:
    return not envelope_exceeded(realized_oriented, envelope)


@dataclass(frozen=True)
class AABBBox:
    flb: tuple[float, float, float]
    dims: AxisTriple

    @property
    def max_corner(self) -> tuple[float, float, float]:
        return (
            self.flb[0] + self.dims.length,
            self.flb[1] + self.dims.width,
            self.flb[2] + self.dims.height,
        )


def interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def boxes_overlap(a: AABBBox, b: AABBBox, *, eps: float = EPS_MM) -> bool:
    ax0, ay0, az0 = a.flb
    ax1, ay1, az1 = a.max_corner
    bx0, by0, bz0 = b.flb
    bx1, by1, bz1 = b.max_corner
    ox = interval_overlap(ax0, ax1, bx0, bx1)
    oy = interval_overlap(ay0, ay1, by0, by1)
    oz = interval_overlap(az0, az1, bz0, bz1)
    # Contacto de caras (overlap == 0) permitido.
    return ox > eps and oy > eps and oz > eps


def outside_container(box: AABBBox, container: AxisTriple, *, eps: float = EPS_MM) -> bool:
    mx, my, mz = box.max_corner
    x, y, z = box.flb
    if x < -eps or y < -eps or z < -eps:
        return True
    if mx > container.length + eps or my > container.width + eps or mz > container.height + eps:
        return True
    return False


def geometric_violation(
    realized_box: AABBBox,
    container: AxisTriple,
    occupied: Sequence[AABBBox],
    *,
    eps: float = EPS_MM,
) -> dict[str, bool]:
    outside = outside_container(realized_box, container, eps=eps)
    overlap = any(boxes_overlap(realized_box, other, eps=eps) for other in occupied)
    return {
        "outside": outside,
        "overlap": overlap,
        "geometric_failure": outside or overlap,
    }


def certificate_realized_safe_if_subseteq_envelope(
    *,
    flb: tuple[float, float, float],
    envelope: AxisTriple,
    realized_oriented: AxisTriple,
    container: AxisTriple,
    occupied_revealed: Sequence[AABBBox],
) -> dict[str, object]:
    """Propiedad elemental: realized ⊆ envelope y envelope factible ⇒ realized factible.

    La ocupación relevante son cajas *reveladas* (realizadas), no envolventes antiguas.
    No aplica si hubo envelope_exceeded.
    """
    env_box = AABBBox(flb, envelope)
    env_ok = not geometric_violation(env_box, container, occupied_revealed)["geometric_failure"]
    subset = realized_subseteq_envelope(realized_oriented, envelope)
    real_box = AABBBox(flb, realized_oriented)
    real_check = geometric_violation(real_box, container, occupied_revealed)
    implies = (not subset) or (not env_ok) or (not real_check["geometric_failure"])
    return {
        "envelope_feasible_vs_revealed": env_ok,
        "realized_subseteq_envelope": subset,
        "realized_geometric_failure": real_check["geometric_failure"],
        "certificate_holds": bool(implies),
        "applies": bool(subset and env_ok),
    }
