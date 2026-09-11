"""Parámetros compartidos de los algoritmos online."""

from __future__ import annotations


def resolve_selection(params: dict | None) -> str:
    selection = str((params or {}).get("selection", "best_fit")).lower()
    if selection not in ("best_fit", "blb"):
        return "best_fit"
    return selection


def support_threshold(params: dict | None, basic_stability: bool) -> float:
    if not basic_stability:
        return 0.0
    raw = (params or {}).get("min_support_ratio", 0.6)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return 0.6
