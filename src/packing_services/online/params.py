"""Parámetros compartidos de los algoritmos online."""

from __future__ import annotations

from typing import Any

from ..domain.models import PackingProblem
from .policies import ConsolidatingPolicy, PlacementPolicy


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


def wants_consolidate(params: dict | None, n_containers: int) -> bool:
    """Disciplina first-fit: default True si hay más de un contenedor.

    El Paso A demostró que el defecto multi-pallet estaba en el espacio de
    acciones, no en la política. El execute activa la envolvente salvo que
    el cliente envíe ``consolidate=false``.
    """

    raw = None if params is None else params.get("consolidate")
    if raw in (None, ""):
        return n_containers > 1
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return n_containers > 1


def maybe_wrap_consolidating(
    policy: PlacementPolicy,
    problem: PackingProblem,
    params: dict[str, Any] | None,
) -> PlacementPolicy:
    """Envuelve la política si el execute debe consolidar. No toca el bucle."""

    if wants_consolidate(params, len(problem.containers)):
        return ConsolidatingPolicy(policy)
    return policy
