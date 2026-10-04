"""Evaluación de desarrollo. No toca test ni OnlineBPH ni reentrena."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import torch

RULES = ("greedy_best_fit", "lowest_top", "least_height_increase")
SEEDS = (101, 102, 103)
CASE_TIMEOUT_SECONDS = 300.0
GLOBAL_TIMEOUT_SECONDS = 3600.0
REFERENCE_TIE = 1e-12
OUTCOME_TIE = 1e-9
GATE_MARGIN = 0.005


def case_key(arm: str, label: str, order_id: str) -> str:
    return f"{arm}|{label}|{order_id}"


def planned_cases(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for order in orders:
        for rule in RULES:
            cases.append({**order, "arm": "fixed", "label": rule, "seed": None, "key": case_key("fixed", rule, order["order_id"])})
        for seed in SEEDS:
            cases.append(
                {
                    **order,
                    "arm": "uniform",
                    "label": str(seed),
                    "seed": seed,
                    "key": case_key("uniform", str(seed), order["order_id"]),
                }
            )
            cases.append(
                {
                    **order,
                    "arm": "ppo",
                    "label": str(seed),
                    "seed": seed,
                    "key": case_key("ppo", str(seed), order["order_id"]),
                }
            )
    keys = [row["key"] for row in cases]
    if len(keys) != 360 or len(set(keys)) != 360:
        raise ValueError("las claves previstas no son las 360 únicas")
    return cases


def uniform_stream_seed(seed: int, order_id: str) -> int:
    digest = hashlib.sha256(f"rl-rules-dev-uniform-v1|{seed}|{order_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def uniform_actions(seed: int, order_id: str, count: int) -> list[int]:
    generator = torch.Generator()
    generator.manual_seed(uniform_stream_seed(seed, order_id))
    return [int(torch.randint(0, 3, (1,), generator=generator).item()) for _index in range(count)]


def deterministic_action(logits: torch.Tensor) -> int:
    """Argmax. En empate exacto gana el menor índice."""

    values = logits.detach().reshape(-1)
    if values.numel() != 3:
        raise ValueError("el actor de evaluación tiene tres logits")
    best = values[0]
    action = 0
    for index in range(1, 3):
        if values[index] > best:
            best = values[index]
            action = index
    return action


def contrast_input(capture: dict[str, Any], snapshot: dict[str, Any], order_id: str) -> dict[str, Any]:
    errors = []
    if capture.get("order_id") != order_id:
        errors.append("el pedido de la captura no coincide")
    expected = snapshot.get("items") or []
    observed = capture.get("input_items") or []
    if len(expected) != len(observed):
        errors.append("el número de ítems de entrada no coincide")
    else:
        for left, right in zip(expected, observed):
            if left.get("item_id") != right.get("item_id"):
                errors.append("un identificador de ítem no coincide")
                break
            for key in ("length_mm", "width_mm", "height_mm"):
                if float(left[key]) != float(right[key]):
                    errors.append(f"{key} de la entrada no coincide")
                    break
    for row in capture.get("placements") or []:
        oriented = row.get("oriented_lwh_mm")
        if not isinstance(oriented, list) or len(oriented) != 3:
            errors.append("una colocación no trae dimensiones orientadas")
            break
    if capture.get("physical_stability_verified") is not None:
        errors.append("la estabilidad física no está en null")
    return {"matches": not errors, "errors": errors}


def classify_case(*, status: str, raw_u_geom: float | None, geometry_valid: bool, contrast_matches: bool) -> dict[str, Any]:
    if status in {"pending", "timeout"}:
        return {
            "method_failure": False,
            "evaluator_error": False,
            "pending": True,
            "effective_u_geom": None,
            "in_denominator": True,
            "scored": False,
        }
    if status == "method_failure":
        return {
            "method_failure": True,
            "evaluator_error": False,
            "pending": False,
            "effective_u_geom": 0.0,
            "in_denominator": True,
            "scored": True,
        }
    if status != "ok":
        return {
            "method_failure": False,
            "evaluator_error": True,
            "pending": False,
            "effective_u_geom": None,
            "in_denominator": True,
            "scored": False,
        }
    if not geometry_valid or not contrast_matches or raw_u_geom is None:
        return {
            "method_failure": False,
            "evaluator_error": True,
            "pending": False,
            "effective_u_geom": None,
            "in_denominator": True,
            "scored": False,
        }
    return {
        "method_failure": False,
        "evaluator_error": False,
        "pending": False,
        "effective_u_geom": float(raw_u_geom),
        "in_denominator": True,
        "scored": True,
    }


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("no hay valores para la media")
    return sum(values) / len(values)


def _outcome(delta: float) -> str:
    if abs(delta) <= OUTCOME_TIE:
        return "empate"
    if delta > 0.0:
        return "victoria"
    return "derrota"


def choose_reference(rule_means: dict[str, float]) -> str:
    best_value = max(rule_means[rule] for rule in RULES)
    for rule in RULES:
        if abs(rule_means[rule] - best_value) <= REFERENCE_TIE:
            return rule
    raise RuntimeError("no aparece la regla de referencia")


def paired_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Igual peso por pedido y después por semilla. Exige las 360 puntuaciones."""

    by_key = {row["key"]: row for row in rows}
    orders = sorted({row["order_id"] for row in rows})
    if len(by_key) != 360:
        raise ValueError("el resumen exige las 360 claves")
    if any(not row.get("scored") or row.get("effective_u_geom") is None for row in rows):
        raise ValueError("hay casos sin puntuación")

    def value(arm: str, label: str, order_id: str) -> float:
        return float(by_key[case_key(arm, label, order_id)]["effective_u_geom"])

    rule_means = {rule: _mean([value("fixed", rule, order_id) for order_id in orders]) for rule in RULES}
    reference = choose_reference(rule_means)
    per_seed = []
    for seed in SEEDS:
        label = str(seed)
        deltas_ref = [value("ppo", label, order_id) - value("fixed", reference, order_id) for order_id in orders]
        deltas_random = [value("ppo", label, order_id) - value("uniform", label, order_id) for order_id in orders]
        by_target = {}
        targets = sorted({row["target"] for row in rows})
        for target in targets:
            target_orders = [order_id for order_id in orders if by_key[case_key("ppo", label, order_id)]["target"] == target]
            by_target[target] = _mean(
                [value("ppo", label, order_id) - value("fixed", reference, order_id) for order_id in target_orders]
            )
        outcomes = {"victoria": 0, "empate": 0, "derrota": 0}
        for delta in deltas_ref:
            outcomes[_outcome(delta)] += 1
        versus_rules = {
            rule: _mean([value("ppo", label, order_id) - value("fixed", rule, order_id) for order_id in orders])
            for rule in RULES
        }
        per_seed.append(
            {
                "seed": seed,
                "mean_rl_minus_reference": _mean(deltas_ref),
                "mean_rl_minus_uniform": _mean(deltas_random),
                "by_target": by_target,
                "outcomes_versus_reference": outcomes,
                "mean_rl_minus_each_fixed_rule": versus_rules,
            }
        )
    targets = sorted({row["target"] for row in rows})
    aggregate_by_target = {
        target: _mean([row["by_target"][target] for row in per_seed])
        for target in targets
    }
    mean_reference = _mean([row["mean_rl_minus_reference"] for row in per_seed])
    mean_uniform = _mean([row["mean_rl_minus_uniform"] for row in per_seed])
    positive_seeds = sum(1 for row in per_seed if row["mean_rl_minus_reference"] > 0.0)
    return {
        "n_orders": len(orders),
        "aggregation": "igual peso por pedido y después por semilla",
        "fixed_rule_means": rule_means,
        "reference_rule": reference,
        "reference_tie_epsilon": REFERENCE_TIE,
        "outcome_tie_epsilon": OUTCOME_TIE,
        "per_seed": per_seed,
        "aggregate_rl_minus_reference": mean_reference,
        "aggregate_rl_minus_uniform": mean_uniform,
        "aggregate_by_target": aggregate_by_target,
        "positive_reference_seeds": positive_seeds,
    }


def apply_gate(summary: dict[str, Any], *, integrity_passed: bool, evaluation_complete: bool) -> dict[str, Any]:
    conditions = {
        "media_rl_menos_mejor_fija": summary["aggregate_rl_minus_reference"] >= GATE_MARGIN,
        "positiva_en_al_menos_dos_semillas": summary["positive_reference_seeds"] >= 2,
        "no_negativo_en_cada_target": all(value >= 0.0 for value in summary["aggregate_by_target"].values()),
        "media_rl_menos_uniforme": summary["aggregate_rl_minus_uniform"] > 0.0,
        "integridad_y_evaluacion_completa": integrity_passed and evaluation_complete,
    }
    return {
        "applied": True,
        "passed": all(conditions.values()),
        "conditions": conditions,
        "margin": GATE_MARGIN,
    }


def protocol_timeout_conflict(protocol: dict[str, Any]) -> str | None:
    for key in ("development_case_timeout_seconds", "development_global_timeout_seconds"):
        if key in protocol:
            return f"el protocolo ya fija {key}"
    return None
