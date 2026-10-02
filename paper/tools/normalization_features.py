"""Transformación de características para la ablación del paso 10.

La media y la desviación se ajustan solo con filas candidatas de train.
No entrena ni ejecuta packing.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import numpy as np

FEATURE_NAMES: tuple[str, ...] = (
    "item_l_n",
    "item_w_n",
    "item_h_n",
    "item_vol_n",
    "item_weight_n",
    "item_can_rotate",
    "pos_x_n",
    "pos_y_n",
    "pos_z_n",
    "ori_l_n",
    "ori_w_n",
    "ori_h_n",
    "support_ratio",
    "bin_index_n",
    "rank_0",
    "rank_1",
    "rank_2",
    "rank_3",
    "n_packed_n",
    "loaded_weight_n",
    "used_height_n",
    "remaining_n",
    "buffer_index_n",
    "preview_0_l_n",
    "preview_0_w_n",
    "preview_0_h_n",
    "preview_0_vol_n",
    "preview_1_l_n",
    "preview_1_w_n",
    "preview_1_h_n",
    "preview_1_vol_n",
    "preview_2_l_n",
    "preview_2_w_n",
    "preview_2_h_n",
    "preview_2_vol_n",
)
STD_EPS = 1e-12
WEIGHTING = "cada fila candidata pesa igual; no se promedia primero dentro de la transición"


def candidate_matrix(transitions: list[dict[str, Any]]) -> np.ndarray:
    """Apila las candidatas en el orden guardado. Conserva las de una sola opción."""

    blocks = [np.asarray(transition["features"], dtype=np.float64) for transition in transitions]
    if not blocks:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float64)
    matrix = np.concatenate(blocks, axis=0)
    if matrix.ndim != 2 or matrix.shape[1] != len(FEATURE_NAMES):
        raise ValueError("las candidatas no tienen 35 columnas en el orden congelado")
    return matrix


def fit_standardizer(train_matrix: np.ndarray) -> dict[str, Any]:
    if train_matrix.ndim != 2 or train_matrix.shape[1] != len(FEATURE_NAMES):
        raise ValueError("train no tiene 35 columnas")
    if not np.isfinite(train_matrix).all():
        raise ValueError("train tiene valores no finitos")
    mean = train_matrix.mean(axis=0)
    std = train_matrix.std(axis=0, ddof=0)
    denominator = np.where(std <= STD_EPS, 1.0, std)
    return {
        "feature_names": list(FEATURE_NAMES),
        "weighting": WEIGHTING,
        "ddof": 0,
        "std_eps": STD_EPS,
        "mean": mean.tolist(),
        "population_std": std.tolist(),
        "denominator": denominator.tolist(),
        "n_rows": int(train_matrix.shape[0]),
    }


def transform_rows(matrix: np.ndarray, stats: dict[str, Any], *, arm: str) -> np.ndarray:
    """A es la identidad. B usa las estadísticas ya ajustadas, también al puntuar."""

    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(FEATURE_NAMES):
        raise ValueError("la matriz no conserva las 35 columnas")
    if list(stats["feature_names"]) != list(FEATURE_NAMES):
        raise ValueError("el orden de columnas no coincide")
    if arm == "raw":
        return values.copy()
    if arm != "normalized":
        raise ValueError("brazo desconocido")
    mean = np.asarray(stats["mean"], dtype=np.float64)
    denominator = np.asarray(stats["denominator"], dtype=np.float64)
    return (values - mean) / denominator


def constant_names(matrix: np.ndarray) -> list[str]:
    if matrix.size == 0:
        return []
    std = matrix.std(axis=0, ddof=0)
    return [FEATURE_NAMES[index] for index, value in enumerate(std) if float(value) <= STD_EPS]


def stats_sha256(stats: dict[str, Any]) -> str:
    payload = json.dumps(stats, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def finite_columns(matrix: np.ndarray) -> bool:
    return bool(matrix.size) and bool(np.isfinite(matrix).all()) and not any(
        not math.isfinite(value) for value in np.asarray(matrix, dtype=np.float64).ravel()
    )
