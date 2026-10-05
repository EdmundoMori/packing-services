"""Análisis exploratorio del piloto counterfactual publicado. No empaqueta."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from pilot_reader import SEEDS, PilotIntegrityError

TIE_EPS = 1e-9
BOOTSTRAP_REPLICAS = 20000
BOOTSTRAP_SEED = 20261004


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("media vacía")
    return float(sum(values) / len(values))


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("mediana vacía")
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _sign_bucket(value: float, *, eps: float = TIE_EPS) -> str:
    if abs(value) <= eps:
        return "zero"
    return "positive" if value > 0.0 else "negative"


def order_level_deltas(pilot: dict[str, Any]) -> list[dict[str, Any]]:
    """Una fila por pedido. Las semillas del pedido quedan juntas."""

    catalog = pilot["catalog"]
    rows = []
    for order in pilot["orders"]:
        order_id = order["order_id"]
        target = order["target"]
        seed_rows = []
        pc_vals = []
        pg_vals = []
        cg_vals = []
        for seed in SEEDS:
            preferences = float(catalog[(order_id, "preferences", seed)]["effective_u_geom"])
            classification = float(catalog[(order_id, "classification", seed)]["effective_u_geom"])
            greedy = float(catalog[(order_id, "greedy", None)]["effective_u_geom"])
            pc = preferences - classification
            pg = preferences - greedy
            cg = classification - greedy
            seed_rows.append(
                {
                    "seed": int(seed),
                    "preferences": preferences,
                    "classification": classification,
                    "greedy": greedy,
                    "preferences_minus_classification": pc,
                    "preferences_minus_greedy": pg,
                    "classification_minus_greedy": cg,
                }
            )
            pc_vals.append(pc)
            pg_vals.append(pg)
            cg_vals.append(cg)
        rows.append(
            {
                "order_id": order_id,
                "target": target,
                "by_seed": seed_rows,
                "d_preferences_minus_classification": _mean(pc_vals),
                "d_preferences_minus_greedy": _mean(pg_vals),
                "d_classification_minus_greedy": _mean(cg_vals),
            }
        )
    return rows


def seed_level_means(order_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for seed in SEEDS:
        pc = [float(item["by_seed"][SEEDS.index(seed)]["preferences_minus_classification"]) for item in order_rows]
        pg = [float(item["by_seed"][SEEDS.index(seed)]["preferences_minus_greedy"]) for item in order_rows]
        cg = [float(item["by_seed"][SEEDS.index(seed)]["classification_minus_greedy"]) for item in order_rows]
        reports.append(
            {
                "seed": int(seed),
                "n_orders": len(order_rows),
                "preferences_minus_classification": _mean(pc),
                "preferences_minus_greedy": _mean(pg),
                "classification_minus_greedy": _mean(cg),
            }
        )
    return reports


def aggregate_equal_seed_weight(seed_reports: list[dict[str, Any]]) -> dict[str, float]:
    if [row["seed"] for row in seed_reports] != list(SEEDS):
        raise PilotIntegrityError("las semillas no están en el orden 11, 23, 37")
    return {
        "preferences_minus_classification": _mean(
            [float(row["preferences_minus_classification"]) for row in seed_reports]
        ),
        "preferences_minus_greedy": _mean([float(row["preferences_minus_greedy"]) for row in seed_reports]),
        "classification_minus_greedy": _mean([float(row["classification_minus_greedy"]) for row in seed_reports]),
    }


def summarize_contrast(order_rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(row[field]) for row in order_rows]
    buckets = {"positive": 0, "zero": 0, "negative": 0}
    for value in values:
        buckets[_sign_bucket(value)] += 1
    by_target = {}
    for target in ("euro-pallet", "rollcontainer"):
        subset = [float(row[field]) for row in order_rows if row["target"] == target]
        by_target[target] = {
            "n_orders": len(subset),
            "mean": _mean(subset),
            "median": _median(subset),
        }
    return {
        "n_orders": len(values),
        "mean": _mean(values),
        "median": _median(values),
        "sign_counts": buckets,
        "by_target": by_target,
        "aggregation": "media de las tres diferencias por semilla dentro de cada pedido; luego media por pedido",
    }


def leave_one_order_out(order_rows: list[dict[str, Any]], field: str = "d_preferences_minus_classification") -> dict[str, Any]:
    """Sensibilidad descriptiva. No excluye pedidos del resultado principal."""

    full = _mean([float(row[field]) for row in order_rows])
    rows = []
    sign_flips = []
    for index, held in enumerate(order_rows):
        remaining = [float(row[field]) for i, row in enumerate(order_rows) if i != index]
        mean = _mean(remaining)
        flipped = (full > TIE_EPS and mean < -TIE_EPS) or (full < -TIE_EPS and mean > TIE_EPS)
        entry = {
            "held_out_order_id": held["order_id"],
            "held_out_target": held["target"],
            "held_out_value": float(held[field]),
            "mean_without_order": mean,
            "sign_flips_relative_to_full": flipped,
        }
        rows.append(entry)
        if flipped:
            sign_flips.append(held["order_id"])
    return {
        "field": field,
        "full_mean": full,
        "rows": rows,
        "orders_that_flip_sign_when_held_out": sign_flips,
        "note": "Diseñado después de observar el piloto. No autoriza excluir pedidos.",
    }


def stratified_order_bootstrap(
    order_rows: list[dict[str, Any]],
    field: str = "d_preferences_minus_classification",
    *,
    replicas: int = BOOTSTRAP_REPLICAS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Remuestra pedidos. Conserva juntas las semillas ya reducidas en d_i."""

    by_target: dict[str, list[float]] = {"euro-pallet": [], "rollcontainer": []}
    for row in order_rows:
        by_target[row["target"]].append(float(row[field]))
    quotas = {target: len(values) for target, values in by_target.items()}
    if quotas["euro-pallet"] != 6 or quotas["rollcontainer"] != 6:
        raise PilotIntegrityError(f"cuotas inesperadas: {quotas}")
    rng = np.random.default_rng(seed)
    means = np.empty(replicas, dtype=np.float64)
    for replica in range(replicas):
        sample = []
        for target, values in by_target.items():
            n = quotas[target]
            choices = rng.integers(0, n, size=n)
            sample.extend(values[index] for index in choices)
        means[replica] = float(np.mean(sample))
    low, high = np.percentile(means, [2.5, 97.5], method="linear")
    return {
        "field": field,
        "unit": "order",
        "seeds_kept_together": True,
        "stratified_by_target": True,
        "quotas": quotas,
        "replicas": replicas,
        "rng": f"numpy.random.default_rng({seed})",
        "percentile_method": "linear",
        "percentile_points": [2.5, 97.5],
        "mean_of_replicates": float(np.mean(means)),
        "interval_95": [float(low), float(high)],
        "confirmatory": False,
        "note": "Intervalo exploratorio. No declara confirmación retrospectiva ni equivalencia.",
    }


def analyze_pilot(pilot: dict[str, Any]) -> dict[str, Any]:
    order_rows = order_level_deltas(pilot)
    seed_reports = seed_level_means(order_rows)
    aggregate = aggregate_equal_seed_weight(seed_reports)
    # También la media directa de d_i (pedido) coincide con la media de semillas para este contraste
    order_mean_pc = _mean([float(row["d_preferences_minus_classification"]) for row in order_rows])
    if not math.isclose(order_mean_pc, aggregate["preferences_minus_classification"], rel_tol=0.0, abs_tol=1e-15):
        raise PilotIntegrityError("la media por pedido no coincide con la media por semilla")
    return {
        "design_timing": "after_observing_pilot",
        "confirmatory": False,
        "seed_selected": False,
        "equivalence_test": False,
        "n_orders": len(order_rows),
        "n_seeds": len(SEEDS),
        "n_cases": 84,
        "per_order": order_rows,
        "per_seed": seed_reports,
        "aggregate_equal_weight_per_seed": aggregate,
        "contrasts": {
            "preferences_minus_classification": summarize_contrast(
                order_rows, "d_preferences_minus_classification"
            ),
            "preferences_minus_greedy": summarize_contrast(order_rows, "d_preferences_minus_greedy"),
            "classification_minus_greedy": summarize_contrast(order_rows, "d_classification_minus_greedy"),
        },
        "leave_one_order_out": leave_one_order_out(order_rows),
        "bootstrap_exploratory": stratified_order_bootstrap(order_rows),
        "published_reference_means": {
            "preferences_minus_classification": 0.03094863126240079,
            "preferences_minus_greedy": -0.019783628885582008,
            "classification_minus_greedy": -0.050732260147982794,
        },
        "matches_published_aggregate": {
            "preferences_minus_classification": math.isclose(
                aggregate["preferences_minus_classification"], 0.03094863126240079, abs_tol=0.0, rel_tol=0.0
            ),
            "preferences_minus_greedy": math.isclose(
                aggregate["preferences_minus_greedy"], -0.019783628885582008, abs_tol=0.0, rel_tol=0.0
            ),
            "classification_minus_greedy": math.isclose(
                aggregate["classification_minus_greedy"], -0.050732260147982794, abs_tol=0.0, rel_tol=0.0
            ),
        },
    }
