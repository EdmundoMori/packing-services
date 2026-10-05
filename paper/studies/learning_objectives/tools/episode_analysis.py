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
    """Casos por pedido: 1 Greedy + 3 brazos × 3 semillas. 24 pedidos → 240."""

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
    if len(keys) != len(set(keys)):
        raise ValueError("claves no únicas")
    return cases


def filter_cases(
    cases: list[dict[str, Any]],
    *,
    order_ids: set[str] | None = None,
    arms: set[str] | None = None,
    seeds: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Filtra casos para smoke u otras subcuadrículas autorizadas."""

    out = []
    for case in cases:
        if order_ids is not None and case["order_id"] not in order_ids:
            continue
        if arms is not None and case["arm"] not in arms:
            continue
        if case["arm"] != "greedy" and seeds is not None and int(case["seed"]) not in seeds:
            continue
        out.append(case)
    return out


def looks_like_harness_failure(error: str | None, stderr: str | None = None) -> bool:
    """Causa técnica de infraestructura (no del algoritmo de packing)."""

    blob = f"{error or ''}\n{stderr or ''}".lower()
    markers = (
        "modulenotfounderror",
        "no module named 'torch'",
        "no module named \"torch\"",
        "importerror",
        "worker_environment_preflight_failed",
        "harness",
        "venv",
        "sys.prefix",
    )
    return any(marker in blob for marker in markers)


def classify_episode(
    *,
    status: str,
    raw_u_geom: float | None,
    geometry_valid: bool,
    contrast_matches: bool,
    error: str | None = None,
    stderr: str | None = None,
    failure_class: str | None = None,
) -> dict[str, Any]:
    if status != "ok":
        harness = failure_class == "harness" or looks_like_harness_failure(error, stderr)
        if harness:
            return {
                "method_failure": False,
                "harness_failure": True,
                "evaluator_error": False,
                "geometry_invalid": False,
                "input_mismatch": False,
                "effective_u_geom": None,
                "raw_u_geom": None,
                "in_denominator": False,
                "physical_stability_verified": None,
                "failure_class": "harness",
            }
        return {
            "method_failure": True,
            "harness_failure": False,
            "evaluator_error": False,
            "geometry_invalid": False,
            "input_mismatch": False,
            "effective_u_geom": 0.0,
            "raw_u_geom": None,
            "in_denominator": True,
            "physical_stability_verified": None,
            "failure_class": "method",
        }
    geometry_invalid = not geometry_valid
    input_mismatch = not contrast_matches
    if geometry_invalid or input_mismatch or raw_u_geom is None:
        return {
            "method_failure": False,
            "harness_failure": False,
            "evaluator_error": True,
            "geometry_invalid": geometry_invalid,
            "input_mismatch": input_mismatch,
            "effective_u_geom": None,
            "raw_u_geom": raw_u_geom,
            "in_denominator": False,
            "physical_stability_verified": None,
            "failure_class": "evaluator",
        }
    return {
        "method_failure": False,
        "harness_failure": False,
        "evaluator_error": False,
        "geometry_invalid": False,
        "input_mismatch": False,
        "effective_u_geom": float(raw_u_geom),
        "raw_u_geom": float(raw_u_geom),
        "in_denominator": True,
        "physical_stability_verified": None,
        "failure_class": None,
    }


def evaluation_integrity(
    *,
    n_keys_received: int,
    expected_keys: int,
    n_episodes_executed: int,
    n_audited_captures: int,
    method_failures: int,
    harness_failures: int,
    evaluator_errors: int,
    harness_preflight_ok: bool = True,
) -> dict[str, Any]:
    """Integridad operativa vs científica. No usa U_geom."""

    keys_complete = n_keys_received == expected_keys and expected_keys > 0
    episodes_executed = n_episodes_executed
    captures_audited = n_audited_captures
    infrastructure_blocked = (not harness_preflight_ok) or harness_failures > 0
    scientifically_valid = (
        keys_complete
        and captures_audited == expected_keys
        and evaluator_errors == 0
        and harness_failures == 0
        and harness_preflight_ok
    )
    gate_applicable = scientifically_valid
    return {
        "keys_received": n_keys_received,
        "expected_keys": expected_keys,
        "keys_complete": keys_complete,
        "episodes_executed": episodes_executed,
        "captures_audited": captures_audited,
        "method_failures": method_failures,
        "harness_failures": harness_failures,
        "evaluator_errors": evaluator_errors,
        "harness_preflight_ok": harness_preflight_ok,
        "infrastructure_blocked": infrastructure_blocked,
        "scientifically_valid": scientifically_valid,
        "gate_applicable": gate_applicable,
        "complete_audited_evaluation": scientifically_valid,
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
    integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cinco condiciones del protocolo. No exige superar Greedy.

    Si la integridad indica evaluación inválida (arnés/infraestructura), la puerta
    científica no aplica: no cierra la configuración por falta de mejora.
    """

    integrity = integrity or {}
    gate_applicable = bool(integrity.get("gate_applicable", True))
    complete_audited = bool(integrity.get("complete_audited_evaluation", evaluator_errors == 0 and missing_keys == 0))
    if integrity:
        # integridad manda sobre el atajo de errores/claves
        complete_audited = bool(integrity.get("complete_audited_evaluation"))
        gate_applicable = bool(integrity.get("gate_applicable"))
    else:
        complete_audited = evaluator_errors == 0 and missing_keys == 0
        gate_applicable = complete_audited

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
        "complete_audited_evaluation": complete_audited,
        "remaining_budget_for_test": remaining_seconds_for_test >= float(test_wall_seconds),
    }
    scientific_pass = all(conditions.values())
    pref_g = float((order_aggregate.get("preferences_minus_greedy") or {}).get("mean") or 0.0)
    class_g = float((order_aggregate.get("classification_minus_greedy") or {}).get("mean") or 0.0)
    if not gate_applicable:
        decision = "evaluacion_incompleta"
        if integrity.get("infrastructure_blocked") or integrity.get("harness_failures", 0) > 0:
            decision = "evaluacion_incompleta_por_fallo_del_arnes"
        passed = False
    elif scientific_pass:
        decision = "puerta_desarrollo_cumplida_pendiente_revision"
        passed = True
    else:
        decision = "no_avanzar_con_esta_configuracion"
        passed = False
    return {
        "passed": passed,
        "gate_applicable": gate_applicable,
        "decision": decision,
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
        "integrity": integrity,
        "seed_selected": False,
        "secondary_arm_does_not_rescue_gate": True,
        "engineering_gate_not_significance_test": True,
        "numeric_contrasts_are_packing_results": gate_applicable,
    }
