"""Normalización solo con filas de train. Desviación poblacional."""

from __future__ import annotations

import math
from typing import Sequence


def fit_normalization(rows: Sequence[Sequence[float]]) -> dict[str, list[float] | int | str]:
    if not rows:
        raise ValueError("train no tiene filas")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("anchura inconsistente")
    count = len(rows)
    means: list[float] = []
    scales: list[float] = []
    for column in range(width):
        values = [float(row[column]) for row in rows]
        mean = sum(values) / count
        variance = sum((value - mean) ** 2 for value in values) / count
        deviation = math.sqrt(variance)
        means.append(mean)
        scales.append(1.0 if deviation == 0.0 else deviation)
    return {
        "mean": means,
        "scale": scales,
        "denominator": "population_std_or_1_if_constant",
        "row_weight": "igual_por_fila",
        "n_rows": count,
    }


def apply_normalization(row: Sequence[float], stats: dict[str, list[float]]) -> list[float]:
    return [(float(value) - mean) / scale for value, mean, scale in zip(row, stats["mean"], stats["scale"])]
