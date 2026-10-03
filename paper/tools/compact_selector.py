"""Selector compacto del paso 17. No entrena ni observa la cola futura.

El contacto es el score ya guardado en rank_key[0], con signo invertido.
No es una prueba de estabilidad.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

FORMULA_VERSION = "compact_contact_height_v1"
FORMULA = (
    "contacto_normalizado - a * incremento_altura_normalizado "
    "- b * techo_normalizado + c * apoyo"
)
SELECTOR_ALGORITHM = "compact_selector"
GRID_A = (0.0, 0.5, 1.0, 2.0)
GRID_B = (0.0, 0.5, 1.0, 2.0)
GRID_C = (0.0, 0.25)
GATE_MEAN_DELTA = 0.005


def grid_configurations() -> list[tuple[float, float, float]]:
    return [(a, b, c) for a in GRID_A for b in GRID_B for c in GRID_C]


def config_id(a: float, b: float, c: float) -> str:
    return f"a{a:g}_b{b:g}_c{c:g}"


def surface_denominator(length: float, width: float, height: float) -> float:
    return 2.0 * (length * width + length * height + width * height)


def present_height_mm(session: Any, bin_index: int) -> float:
    placed = session.states[bin_index].placed
    if not placed:
        return 0.0
    return max(float(box.max_corner[2]) for box in placed)


def score_components(
    *,
    rank_key: Sequence[float],
    oriented_lwh: Sequence[float],
    z_mm: float,
    support_ratio: float,
    bin_height_mm: float,
    current_height_mm: float,
    a: float,
    b: float,
    c: float,
) -> dict[str, float] | None:
    """Devuelve None si un denominador no es positivo o algún valor no es finito."""

    if len(rank_key) < 1 or len(oriented_lwh) != 3:
        return None
    length, width, height = (float(oriented_lwh[0]), float(oriented_lwh[1]), float(oriented_lwh[2]))
    contact_key = float(rank_key[0])
    values = (
        length,
        width,
        height,
        float(z_mm),
        float(support_ratio),
        float(bin_height_mm),
        float(current_height_mm),
        float(a),
        float(b),
        float(c),
        contact_key,
    )
    if not all(math.isfinite(value) for value in values):
        return None
    if length <= 0 or width <= 0 or height <= 0 or bin_height_mm <= 0:
        return None
    denominator = surface_denominator(length, width, height)
    if not math.isfinite(denominator) or denominator <= 0:
        return None
    contact = (-contact_key) / denominator
    ceiling = (float(z_mm) + height) / float(bin_height_mm)
    increment = (max(float(current_height_mm), float(z_mm) + height) - float(current_height_mm)) / float(bin_height_mm)
    score = contact - float(a) * increment - float(b) * ceiling + float(c) * float(support_ratio)
    if not all(math.isfinite(value) for value in (contact, ceiling, increment, score)):
        return None
    return {
        "contacto_normalizado": contact,
        "techo_normalizado": ceiling,
        "incremento_altura_normalizado": increment,
        "apoyo": float(support_ratio),
        "score": score,
    }


class CompactScorePolicy:
    """Mayor score; empate exacto por rank_key menor y después por el índice original."""

    def __init__(self, a: float, b: float, c: float) -> None:
        self.a = float(a)
        self.b = float(b)
        self.c = float(c)

    def decide(
        self,
        options: Sequence[Any],
        *,
        preview: Sequence[Any],
        remaining_count: int,
        session: Any,
        constraints: Any,
        mask: Any,
    ) -> Any | None:
        del preview, remaining_count, constraints, mask
        best = None
        best_score = None
        best_rank = None
        best_index = None
        for index, option in enumerate(options):
            candidate = option.candidate
            state = session.states[candidate.bin_index]
            components = score_components(
                rank_key=candidate.rank_key,
                oriented_lwh=(
                    candidate.dimensions.length,
                    candidate.dimensions.width,
                    candidate.dimensions.height,
                ),
                z_mm=candidate.position.z,
                support_ratio=candidate.support_ratio,
                bin_height_mm=state.container.dimensions.height,
                current_height_mm=present_height_mm(session, candidate.bin_index),
                a=self.a,
                b=self.b,
                c=self.c,
            )
            if components is None:
                continue
            score = components["score"]
            rank = tuple(candidate.rank_key)
            better = best is None or score > best_score
            tied = best is not None and score == best_score and (
                rank < best_rank or (rank == best_rank and index < best_index)
            )
            if better or tied:
                best = option
                best_score = score
                best_rank = rank
                best_index = index
        return best


def mean_effective(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("la media no tiene pedidos")
    total = 0.0
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("U_geom no finita")
        total += number
    return total / len(values)


def rank_configurations(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -float(row["mean_effective_u_geom"]),
            float(row["a"]),
            float(row["b"]),
            float(row["c"]),
        ),
    )


def choose_top(rows: Sequence[dict[str, Any]], k: int = 3) -> list[dict[str, Any]]:
    return rank_configurations(rows)[:k]


def engineering_gate(mean_delta: float, euro_delta: float, roll_delta: float) -> dict[str, Any]:
    conditions = {
        "A_mean_delta_at_least_0_005": mean_delta >= GATE_MEAN_DELTA,
        "B_euro_delta_non_negative": euro_delta >= 0.0,
        "C_roll_delta_non_negative": roll_delta >= 0.0,
    }
    return {
        "conditions": conditions,
        "passed": all(conditions.values()),
        "statistical_test": False,
    }
