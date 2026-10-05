"""Análisis de episodios development (3 brazos) y puerta congelada learning_objectives."""

from __future__ import annotations

import statistics
from typing import Any

TIE_EPS = 1e-9
SEEDS = (11, 23, 37)
ARMS = ("classification", "preferences", "return_difference")


def case_key(order_id: str, arm: str, seed: int | None) -> str:
    if arm == "greedy":
        return f"greedy|{order_id}"
    return f"{arm}|{seed}|{order_id}"


def planned_cases(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """24 Greedy + 216 actores = 240 claves."""

    cases: list[dict[str, Any]] = []
    for order in orders:
        cases.append({**order, "arm": "greedy", "seed": None, "key": case_key(order["order_id"], "greedy", None)})
        for arm in ARMS:
            for seed in SEEDS:
                cases.append(
                    {
                        **order,
                        "arm": arm,
                        "seed": seed,
                        "key": case_key(order["order_id"], arm, seed),
                    }
                )
    keys = [item["key"] for item in cases]
    if len(cases) != 240:
        raise ValueError(f"se esperaban 240 casos, got {len(cases)}")
    if len(keys) != len(set(keys)):
        raise ValueError("claves no únicas")
    return cases


def classify_episode(
    *,
    status: str,
    raw_u_geom: float | None,
    geometry_valid: bool,
    contrast_matches: bool,
) -> dict[str, Any]:
    if status != "ok":
        return {
            "method_failure": True,
            "evaluator_error": False,
            "geometry_invalid": False,
            "input_mismatch": False,
            "effective_u_geom": 0.0,
            "raw_u_geom": None,
            "in_denominator": True,
            "physical_stability_verified": None,
        }
    geometry_invalid = not geometry_valid
    input_mismatch = not contrast_matches
    if geometry_invalid or input_mismatch or raw_u_geom is None:
        return {
            "method_failure": False,
            "evaluator_error": True,
            "geometry_invalid": geometry_invalid,
            "input_mismatch": input_mismatch,
            "effective_u_geom": None,
            "raw_u_geom": raw_u_geom,
            "in_denominator": False,
            "physical_stability_verified": None,
        }
    return {
        "method_failure": False,
        "evaluator_error": False,
        "geometry_invalid": False,
        "input_mismatch": False,
        "effective_u_geom": float(raw_u_geom),
        "raw_u_geom": float(raw_u_geom),
        "in_denominator": True,
        "physical_stability_verified": None,
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _outcome(delta: float) -> str:
    if abs(delta) <= TIE_EPS:
        return "tie"
    return "win" if delta > 0.0 else "loss"


def _pair_summary(deltas: list[float]) -> dict[str, Any]:
    outcomes = [_outcome(value) for value in deltas]
    return {
        "n": len(deltas),
        "mean": _mean(deltas),
        "median": _median(deltas),
        "wins": outcomes.count("win"),
        "ties": outcomes.count("tie"),
        "losses": outcomes.count("loss"),
        "tie_tolerance": TIE_EPS,
    }


def _by_order(rows: list[dict[str, Any]]) -> dict[str, dict[tuple[str, int | None], dict[str, Any]]]:
    found: dict[str, dict[tuple[str, int | None], dict[str, Any]]] = {}
    for row in rows:
        found.setdefault(row["order_id"], {})[(row["arm"], row["seed"])] = row
    return found


def seed_report(rows: list[dict[str, Any]], orders: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    catalog = _by_order(rows)
    pair_rows = []
    for order in orders:
        sides = catalog[order["order_id"]]
        greedy = sides[("greedy", None)]
        classification = sides[("classification", seed)]
        preferences = sides[("preferences", seed)]
        return_difference = sides[("return_difference", seed)]
        needed = (greedy, classification, preferences, return_difference)
        if not all(item["in_denominator"] for item in needed):
            raise ValueError(f"pedido incompleto {order['order_id']} seed={seed}")
        pair_rows.append(
            {
                "order_id": order["order_id"],
                "target": order["target"],
                "preferences_minus_classification": float(preferences["effective_u_geom"])
                - float(classification["effective_u_geom"]),
                "preferences_minus_greedy": float(preferences["effective_u_geom"]) - float(greedy["effective_u_geom"]),
                "classification_minus_greedy": float(classification["effective_u_geom"])
                - float(greedy["effective_u_geom"]),
                "return_difference_minus_classification": float(return_difference["effective_u_geom"])
                - float(classification["effective_u_geom"]),
                "return_difference_minus_preferences": float(return_difference["effective_u_geom"])
                - float(preferences["effective_u_geom"]),
                "return_difference_minus_greedy": float(return_difference["effective_u_geom"])
                - float(greedy["effective_u_geom"]),
                "greedy_failure": bool(greedy["method_failure"]),
                "classification_failure": bool(classification["method_failure"]),
                "preferences_failure": bool(preferences["method_failure"]),
                "return_difference_failure": bool(return_difference["method_failure"]),
            }
        )
    contrast_names = (
        "preferences_minus_classification",
        "preferences_minus_greedy",
        "classification_minus_greedy",
        "return_difference_minus_classification",
        "return_difference_minus_preferences",
        "return_difference_minus_greedy",
    )
    report: dict[str, Any] = {"seed": seed, "n_orders": len(pair_rows)}
    for name in contrast_names:
        report[name] = _pair_summary([float(row[name]) for row in pair_rows])
        by_target = {}
        for target in ("euro-pallet", "rollcontainer"):
            selected = [float(row[name]) for row in pair_rows if row["target"] == target]
            by_target[target] = _pair_summary(selected)
        report[name]["by_target"] = by_target
    report["failures"] = {
        "greedy": sum(int(row["greedy_failure"]) for row in pair_rows),
        "classification": sum(int(row["classification_failure"]) for row in pair_rows),
        "preferences": sum(int(row["preferences_failure"]) for row in pair_rows),
        "return_difference": sum(int(row["return_difference_failure"]) for row in pair_rows),
    }
    report["orders"] = pair_rows
    return report


def order_then_seed_aggregate(reports: list[dict[str, Any]], orders: list[dict[str, Any]]) -> dict[str, Any]:
    """Primero media de semillas dentro del pedido; luego media igual por pedido."""

    if [r["seed"] for r in reports] != list(SEEDS):
        raise ValueError("semillas fuera de orden 11,23,37")
    by_seed = {r["seed"]: {row["order_id"]: row for row in r["orders"]} for r in reports}
    contrast_names = (
        "preferences_minus_classification",
        "preferences_minus_greedy",
        "classification_minus_greedy",
        "return_difference_minus_classification",
        "return_difference_minus_preferences",
        "return_difference_minus_greedy",
    )
    out: dict[str, Any] = {"aggregation": "mean_seeds_within_order_then_equal_orders"}
    for name in contrast_names:
        order_means = []
        by_target_vals: dict[str, list[float]] = {"euro-pallet": [], "rollcontainer": []}
        for order in orders:
            vals = [float(by_seed[seed][order["order_id"]][name]) for seed in SEEDS]
            m = _mean(vals)
            order_means.append(m)
            by_target_vals[order["target"]].append(m)
        out[name] = {
            "mean": _mean(order_means),
            "median": _median(order_means),
            "by_target": {t: {"mean": _mean(vs), "median": _median(vs), "n": len(vs)} for t, vs in by_target_vals.items()},
        }
    return out


def apply_development_gate(
    reports: list[dict[str, Any]],
    order_aggregate: dict[str, Any],
    *,
    evaluator_errors: int,
    missing_keys: int,
    remaining_seconds_for_test: float,
    test_wall_seconds: float = 9000.0,
) -> dict[str, Any]:
    """Cinco condiciones del protocolo learning_objectives. No exige superar Greedy."""

    complete = evaluator_errors == 0 and missing_keys == 0
    pref_class = order_aggregate["preferences_minus_classification"]
    positive_seeds = sum(
        1 for report in reports if float(report["preferences_minus_classification"]["mean"]) > TIE_EPS
    )
    conditions = {
        "mean_pref_minus_class_ge_0_005": float(pref_class["mean"]) >= 0.005,
        "positive_mean_in_at_least_two_seeds": positive_seeds >= 2,
        "aggregate_nonnegative_per_target": all(
            float(pref_class["by_target"][target]["mean"]) >= 0.0 for target in ("euro-pallet", "rollcontainer")
        ),
        "complete_audited_evaluation": complete,
        "remaining_budget_for_test": remaining_seconds_for_test >= float(test_wall_seconds),
    }
    passed = all(conditions.values())
    pref_g = float((order_aggregate.get("preferences_minus_greedy") or {}).get("mean") or 0.0)
    class_g = float((order_aggregate.get("classification_minus_greedy") or {}).get("mean") or 0.0)
    return {
        "passed": passed,
        "decision": (
            "puerta_desarrollo_cumplida_pendiente_revision" if passed else "no_avanzar_con_esta_configuracion"
        ),
        "conditions": conditions,
        "positive_seeds": positive_seeds,
        "does_not_require_beating_greedy": True,
        "highlighted_vs_greedy": {
            "preferences_minus_greedy_mean": pref_g,
            "classification_minus_greedy_mean": class_g,
            "preferences_disadvantage_vs_greedy": pref_g < -TIE_EPS,
            "classification_disadvantage_vs_greedy": class_g < -TIE_EPS,
        },
        "remaining_seconds_for_test": remaining_seconds_for_test,
        "test_wall_seconds": test_wall_seconds,
        "evaluator_errors": evaluator_errors,
        "missing_keys": missing_keys,
        "seed_selected": False,
        "secondary_arm_does_not_rescue_gate": True,
        "engineering_gate_not_significance_test": True,
    }
