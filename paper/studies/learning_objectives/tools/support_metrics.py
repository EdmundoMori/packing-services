"""Métricas sobre S. No sustituyen episodios completos."""

from __future__ import annotations

from typing import Sequence

from candidate_support import select_logit_index
from losses import TIE_EPS


def support_regret(
    q_hats: Sequence[float],
    selected_index: int,
    *,
    eps: float = TIE_EPS,
) -> float:
    """R_S = max_a Q_hat(a) - Q_hat(pi).

    Requiere retornos finitos conocidos y que la acción elegida esté en S
    (el índice se interpreta dentro de S).
    """

    if selected_index < 0 or selected_index >= len(q_hats):
        raise ValueError("la acción seleccionada no pertenece a S")
    if any(value is None for value in q_hats):
        raise ValueError("hay retornos desconocidos")
    values = [float(value) for value in q_hats]
    if any(value != value or value in (float("inf"), float("-inf")) for value in values):
        raise ValueError("hay retornos no finitos")
    return max(values) - values[selected_index]


def regret_from_logits(q_hats: Sequence[float], logits: Sequence[float]) -> float:
    chosen = select_logit_index(logits)
    return support_regret(q_hats, chosen)


def is_maximum_return(q_hats: Sequence[float], selected_index: int, *, eps: float = TIE_EPS) -> bool:
    return abs(float(q_hats[selected_index]) - max(float(value) for value in q_hats)) <= eps
