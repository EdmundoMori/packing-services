"""Agregación de la ablación. No elige semilla ni declara una confirmación."""

from __future__ import annotations

from typing import Any

from ablation_contract import ARMS, EXPECTED_SEEDS, AblationError

ROLES = ("raw", "normalized", "heuristic")


def _mean(values: list[float]) -> float:
    if not values:
        raise AblationError("la media no tiene observaciones")
    return sum(values) / len(values)


def advance_decision(
    normalized_minus_raw_by_seed: list[float],
    normalized_minus_greedy: float,
) -> dict[str, Any]:
    """Evalúa las tres condiciones tal como quedaron congeladas."""

    positive_seeds = sum(1 for value in normalized_minus_raw_by_seed if value > 0)
    conditions = {
        "mean_normalized_minus_raw_positive": _mean(normalized_minus_raw_by_seed) > 0,
        "at_least_four_seeds_positive": positive_seeds >= 4,
        "mean_normalized_minus_greedy_positive": normalized_minus_greedy > 0,
    }
    return {
        "kind": "regla de avance de ingeniería",
        "statistical_test": False,
        "practical_relevance_guaranteed": False,
        "conditions": conditions,
        "positive_seeds": positive_seeds,
        "continue_with_this_configuration": all(conditions.values()),
        "confirmatory": False,
    }


def _index_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, int | None], dict[str, Any]]:
    found: dict[tuple[str, str, int | None], dict[str, Any]] = {}
    for row in rows:
        role = row["role"]
        if role not in ROLES:
            raise AblationError("rol desconocido")
        seed = None if role == "heuristic" else int(row["seed"])
        if role == "heuristic" and row.get("seed") not in (None,):
            raise AblationError("la heurística no se repite por semilla")
        key = (row["order_id"], role, seed)
        if key in found:
            raise AblationError(f"observación duplicada: {key}")
        utility = float(row["effective_u_geom"])
        if row.get("failure") and utility != 0:
            raise AblationError("un fallo debe entrar con U_geom 0")
        found[key] = row
    return found


def aggregate_development(
    rows: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    *,
    seeds: list[int] | None = None,
) -> dict[str, Any]:
    """Cinco medias de 50 pedidos. Los fallos permanecen en el denominador."""

    seed_list = list(EXPECTED_SEEDS if seeds is None else seeds)
    indexed = _index_rows(rows)
    per_seed_raw: list[float] = []
    per_seed_vs_greedy: dict[str, list[float]] = {arm: [] for arm in ARMS}
    target_seed_means: dict[str, list[float]] = {}
    actor_failures = {"raw": 0, "normalized": 0}
    for seed in seed_list:
        raw_deltas: list[float] = []
        greedy_deltas = {arm: [] for arm in ARMS}
        target_deltas: dict[str, list[float]] = {}
        for order in orders:
            order_id = order["order_id"]
            target = order["target"]
            heuristic = indexed.get((order_id, "heuristic", None))
            raw = indexed.get((order_id, "raw", seed))
            normalized = indexed.get((order_id, "normalized", seed))
            if heuristic is None or raw is None or normalized is None:
                raise AblationError(f"falta un resultado de {order_id} en la semilla {seed}")
            raw_u = float(raw["effective_u_geom"])
            norm_u = float(normalized["effective_u_geom"])
            heur_u = float(heuristic["effective_u_geom"])
            delta = norm_u - raw_u
            raw_deltas.append(delta)
            greedy_deltas["raw"].append(raw_u - heur_u)
            greedy_deltas["normalized"].append(norm_u - heur_u)
            target_deltas.setdefault(target, []).append(delta)
            if raw.get("failure"):
                actor_failures["raw"] += 1
            if normalized.get("failure"):
                actor_failures["normalized"] += 1
        per_seed_raw.append(_mean(raw_deltas))
        for arm in ARMS:
            per_seed_vs_greedy[arm].append(_mean(greedy_deltas[arm]))
        for target, values in target_deltas.items():
            target_seed_means.setdefault(target, []).append(_mean(values))
    heuristic_failures = sum(
        1 for order in orders if indexed[(order["order_id"], "heuristic", None)].get("failure")
    )
    normalized_vs_greedy = _mean(per_seed_vs_greedy["normalized"])
    decision = advance_decision(per_seed_raw, normalized_vs_greedy)
    return {
        "confirmatory": False,
        "n_orders": len(orders),
        "n_seeds": len(seed_list),
        "seeds": seed_list,
        "normalized_minus_raw_by_seed": per_seed_raw,
        "mean_of_seed_means": _mean(per_seed_raw),
        "versus_greedy_by_seed": per_seed_vs_greedy,
        "mean_versus_greedy": {arm: _mean(per_seed_vs_greedy[arm]) for arm in ARMS},
        "by_target": {
            target: {"mean_of_seed_means": _mean(values)}
            for target, values in sorted(target_seed_means.items())
        },
        "failures_in_denominator": {
            "raw_order_seed": actor_failures["raw"],
            "normalized_order_seed": actor_failures["normalized"],
            "heuristic_orders": heuristic_failures,
        },
        "advance": decision,
    }
