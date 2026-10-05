"""Baselines mínimos G1 (márgenes suministrados; sin calibrar)."""

from __future__ import annotations

from geometry_contract import AxisTriple
from info_separation import PolicyObservation


def margin_zero(_obs: PolicyObservation | None = None) -> AxisTriple:
    return AxisTriple(0.0, 0.0, 0.0)


def margin_uniform(value_mm: float):
    v = float(value_mm)
    if v < 0:
        raise ValueError("margen uniforme negativo")

    def _fn(_obs: PolicyObservation | None = None) -> AxisTriple:
        return AxisTriple(v, v, v)

    return _fn


def margin_axis(margin_lwh_mm: tuple[float, float, float]):
    base = AxisTriple(*margin_lwh_mm)

    def _fn(_obs: PolicyObservation | None = None) -> AxisTriple:
        return base

    return _fn
