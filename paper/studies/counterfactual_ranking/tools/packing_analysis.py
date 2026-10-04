"""Medias pareadas y puerta de development. No empaqueta ni elige semilla."""

from __future__ import annotations

from typing import Any

TIE_EPS = 1e-9
SEEDS = (11, 23, 37)
ARMS = ("classification", "preferences")
CLASS_AHEAD = "avanzar al diseño de evaluación posterior"
CLASS_STOP = "no avanzar con esta configuración"
CLASS_INCONCLUSIVE = "inconcluso"


def case_key(order_id: str, arm: str, seed: int | None) -> str:
    if arm == "greedy":
        return f"greedy|{order_id}"
    return f"{arm}|{seed}|{order_id}"


def planned_cases(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """12 Greedy y 36 de cada brazo. Una clave por pedido, brazo y semilla."""

    cases = []
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
        raise ValueError("las claves previstas no son únicas")
    return cases


def classify_episode(
    *,
    status: str,
    raw_u_geom: float | None,
    geometry_valid: bool,
    contrast_matches: bool,
) -> dict[str, Any]:
    """Un fallo del método entra como 0. Un fallo geométrico o de contraste no."""

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
    if not values:
        raise ValueError("no hay valores")
    return sum(values) / len(values)


def _outcome(delta: float) -> str:
    if abs(delta) <= TIE_EPS:
        return "tie"
    if delta > 0.0:
        return "win"
    return "loss"


def _pair_summary(deltas: list[float]) -> dict[str, Any]:
    outcomes = [_outcome(value) for value in deltas]
    return {
        "n_orders": len(deltas),
        "mean": _mean(deltas),
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
    """Medias de un semilla con igual peso por pedido. Greedy no depende de la semilla."""

    catalog = _by_order(rows)
    pair_rows = []
    for order in orders:
        sides = catalog[order["order_id"]]
        greedy = sides[("greedy", None)]
        classification = sides[("classification", seed)]
        preferences = sides[("preferences", seed)]
        if not all(item["in_denominator"] for item in (greedy, classification, preferences)):
            raise ValueError(f"el pedido {order['order_id']} no está completo para la semilla {seed}")
        pair_rows.append(
            {
                "order_id": order["order_id"],
                "target": order["target"],
                "preferences_minus_classification": float(preferences["effective_u_geom"]) - float(classification["effective_u_geom"]),
                "preferences_minus_greedy": float(preferences["effective_u_geom"]) - float(greedy["effective_u_geom"]),
                "classification_minus_greedy": float(classification["effective_u_geom"]) - float(greedy["effective_u_geom"]),
                "greedy_failure": bool(greedy["method_failure"]),
                "classification_failure": bool(classification["method_failure"]),
                "preferences_failure": bool(preferences["method_failure"]),
            }
        )
    report: dict[str, Any] = {"seed": seed, "n_orders": len(pair_rows)}
    for name in (
        "preferences_minus_classification",
        "preferences_minus_greedy",
        "classification_minus_greedy",
    ):
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
    }
    report["orders"] = pair_rows
    return report


def aggregate_seeds(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Media de las medias por semilla. No suma los 36 episodios de un brazo."""

    if [report["seed"] for report in reports] != list(SEEDS):
        raise ValueError("las semillas no están en el orden 11, 23, 37")
    combined: dict[str, Any] = {"n_seeds": len(reports), "equal_weight_per_seed": True}
    for name in (
        "preferences_minus_classification",
        "preferences_minus_greedy",
        "classification_minus_greedy",
    ):
        combined[name] = {
            "mean": _mean([float(report[name]["mean"]) for report in reports]),
            "by_target": {
                target: {
                    "mean": _mean([float(report[name]["by_target"][target]["mean"]) for report in reports]),
                }
                for target in ("euro-pallet", "rollcontainer")
            },
        }
    return combined


def apply_gate(reports: list[dict[str, Any]], *, evaluator_errors: int, missing_keys: int) -> dict[str, Any]:
    """Cinco condiciones del protocolo congelado. No reescribe ese protocolo."""

    if evaluator_errors or missing_keys:
        return {
            "passed": False,
            "classification": CLASS_INCONCLUSIVE,
            "conditions": {},
            "evaluator_errors": evaluator_errors,
            "missing_keys": missing_keys,
            "physical_stability_verified": None,
            "seed_selected": False,
            "authorizes_automatic_training": False,
            "authorizes_arm_substitution": False,
        }
    combined = aggregate_seeds(reports)
    positive_seeds = sum(
        1 for report in reports if float(report["preferences_minus_classification"]["mean"]) > TIE_EPS
    )
    conditions = {
        "preferences_minus_classification_mean_at_least_0_005": combined["preferences_minus_classification"]["mean"] >= 0.005,
        "preferences_minus_classification_positive_in_at_least_two_seeds": positive_seeds >= 2,
        "preferences_minus_greedy_mean_at_least_0_01": combined["preferences_minus_greedy"]["mean"] >= 0.01,
        "preferences_minus_greedy_nonnegative_on_every_target": all(
            combined["preferences_minus_greedy"]["by_target"][target]["mean"] >= 0.0
            for target in ("euro-pallet", "rollcontainer")
        ),
        "evaluator_integrity_and_coverage": evaluator_errors == 0 and missing_keys == 0,
    }
    passed = all(conditions.values())
    return {
        "passed": passed,
        "classification": CLASS_AHEAD if passed else CLASS_STOP,
        "conditions": conditions,
        "positive_seeds": positive_seeds,
        "thresholds": {
            "preferences_minus_classification": 0.005,
            "positive_seeds": 2,
            "preferences_minus_greedy": 0.01,
            "target_floor": 0.0,
            "positive_tolerance": TIE_EPS,
        },
        "evaluator_errors": evaluator_errors,
        "missing_keys": missing_keys,
        "physical_stability_verified": None,
        "seed_selected": False,
        "authorizes_automatic_training": False,
        "authorizes_arm_substitution": False,
    }
