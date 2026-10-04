"""Cuantiles de estados con elección. No consulta retornos."""

from __future__ import annotations

import math


def unique_preserving_order(indices: list[int]) -> list[int]:
    chosen: list[int] = []
    seen: set[int] = set()
    for index in indices:
        if index in seen:
            continue
        seen.add(index)
        chosen.append(index)
    return chosen


def quantile_indices(n_choice_states: int, *, limit: int = 4) -> list[int]:
    """Índices sobre la trayectoria Greedy.

    Con N <= límite se toman todos. Con N mayor, el índice i es
    floor(i * (N - 1) / (límite - 1) + 1/2). Un duplicado se descarta y
    no se rellena con otro estado.
    """

    if n_choice_states <= 0 or limit <= 0:
        return []
    if n_choice_states <= limit:
        return list(range(n_choice_states))
    if limit == 1:
        return [0]
    raw = [
        math.floor(i * (n_choice_states - 1) / (limit - 1) + 0.5)
        for i in range(limit)
    ]
    return unique_preserving_order(raw)
