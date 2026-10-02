"""Intervalo bootstrap del paso 07. Solo analiza deltas ya pareados."""

from __future__ import annotations

from typing import Any

import numpy as np

from freeze_independent_sample import QUOTA_N


N_REPLICATES = 20000
SEED = 20261002
EURO = "euro-pallet"
ROLL = "rollcontainer"


def replicate_means(
    euro_deltas: np.ndarray,
    roll_deltas: np.ndarray,
    rng: np.random.Generator,
    n_replicates: int,
) -> np.ndarray:
    """Cada réplica conserva las cuotas y mueve el pedido, no cada método."""

    n_euro = int(euro_deltas.shape[0])
    n_roll = int(roll_deltas.shape[0])
    means = np.empty(n_replicates, dtype=float)
    total = n_euro + n_roll
    for _index in range(n_replicates):
        euro_draw = euro_deltas[rng.integers(0, n_euro, size=n_euro)]
        roll_draw = roll_deltas[rng.integers(0, n_roll, size=n_roll)]
        means[_index] = (float(euro_draw.sum()) + float(roll_draw.sum())) / total
    return means


def bootstrap_primary(
    euro_deltas: list[float] | np.ndarray,
    roll_deltas: list[float] | np.ndarray,
    *,
    n_replicates: int = N_REPLICATES,
    seed: int = SEED,
) -> dict[str, Any]:
    euro = np.asarray(euro_deltas, dtype=float)
    roll = np.asarray(roll_deltas, dtype=float)
    if euro.shape != (QUOTA_N[EURO],) or roll.shape != (QUOTA_N[ROLL],):
        raise ValueError("la primaria exige 91 deltas de euro-pallet y 109 de rollcontainer")
    if not np.isfinite(euro).all() or not np.isfinite(roll).all():
        raise ValueError("hay deltas no finitos")
    point = (float(euro.sum()) + float(roll.sum())) / (QUOTA_N[EURO] + QUOTA_N[ROLL])
    rng = np.random.default_rng(seed)
    means = replicate_means(euro, roll, rng, n_replicates)
    low, high = np.percentile(means, [2.5, 97.5], method="linear")
    return {
        "n": QUOTA_N[EURO] + QUOTA_N[ROLL],
        "n_euro_pallet": QUOTA_N[EURO],
        "n_rollcontainer": QUOTA_N[ROLL],
        "mean_delta": point,
        "replicates": n_replicates,
        "seed": seed,
        "percentile_method": "linear",
        "ci_low": float(low),
        "ci_high": float(high),
        "interpretation": interpret_interval(float(low), float(high)),
        "by_target_role": "secundario y descriptivo",
        "interval_is_approximate": True,
        "equality_demonstrated": False,
    }


def interpret_interval(low: float, high: float) -> str:
    if high < 0.0:
        return "desventaja_media"
    if low > 0.0:
        return "ventaja_media"
    return "no_concluyente"


def secondary_target_mean(deltas: list[float] | np.ndarray) -> dict[str, Any]:
    values = np.asarray(deltas, dtype=float)
    return {
        "role": "secundario",
        "n": int(values.shape[0]),
        "mean_delta": float(values.mean()) if values.size else None,
        "used_as_primary": False,
    }
