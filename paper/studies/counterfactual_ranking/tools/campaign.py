"""Campaña del diagnóstico. No entrena y no rehace continuaciones compatibles."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any, Callable

from diagnostic import WallClockExceeded

POSITIVE_EPS = 1e-9
REQUIRED_EQUAL_KEYS = (
    "question",
    "not_a_reproduction_of",
    "theoretical_guarantees_claimed",
    "contract",
    "observability",
    "dataset",
    "dataset_sha256",
    "sample_manifest",
    "sample_manifest_sha256",
    "selection",
    "diagnostic",
    "checkpoint",
    "analysis_limits",
)
CODE_COMPATIBILITY = (
    "paper/studies/counterfactual_ranking/tools/diagnostic.py",
    "paper/studies/counterfactual_ranking/tools/select_sample.py",
    "paper/tools/compact_study.py",
    "paper/tools/pilot_metrics.py",
    "paper/tools/pilot_problems.py",
    "paper/tools/audit_internal_solution.py",
)


class CompatibilityError(Exception):
    pass


class Budget:
    def __init__(self, protocol: dict, *, preflight_states: int, preflight_continuations: int) -> None:
        gate = protocol["budget"]
        self.max_states = int(gate["max_states"])
        self.max_continuations = int(gate["max_continuations"])
        self.continuation_timeout = float(gate["continuation_timeout_seconds"])
        self.audit_timeout = float(gate["capture_and_audit_timeout_seconds"])
        self.wall_seconds = float(gate["full_wall_clock_seconds"])
        self.states_used = preflight_states
        self.continuations_used = preflight_continuations


def semantic_equivalence(draft: dict, frozen: dict) -> dict[str, Any]:
    mismatches = []
    for key in REQUIRED_EQUAL_KEYS:
        if draft.get(key) != frozen.get(key):
            mismatches.append(key)
    differences = []
    if draft.get("document") != frozen.get("document"):
        differences.append("el documento congelado no es el borrador")
    if draft.get("budget") != frozen.get("budget"):
        differences.append("el presupuesto truncado se acepta solo en el congelado")
    if "gate" in frozen and "proposed_gate_pending_review" in draft:
        differences.append("la puerta propuesta antes del preflight se adopta en el congelado")
    if draft.get("status") != frozen.get("status"):
        differences.append("el borrador sigue en borrador y el operativo queda congelado")
    return {
        "equivalent": not mismatches,
        "mismatches": mismatches,
        "operational_differences": differences,
        "literal_protocol_hash_equal": False,
    }


def preflight_accounted_seconds(document: dict) -> dict[str, Any]:
    startup = document.get("startup_seconds")
    work = document.get("work_wall_seconds")
    if isinstance(startup, (int, float)) and isinstance(work, (int, float)):
        return {
            "seconds": float(startup) + float(work),
            "source": "startup_seconds+work_wall_seconds",
            "uncertain": False,
        }
    return {"seconds": 11.0, "source": "reserva_conservadora", "uncertain": True}


def recompute_u(capture: dict) -> float | None:
    containers = capture.get("containers")
    placements = capture.get("placements")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(placements, list):
        return None
    container = containers[0]
    volume = float(container["length_mm"]) * float(container["width_mm"]) * float(container["height_mm"])
    if volume <= 0:
        return None
    packed = 0.0
    for row in placements:
        length, width, height = row["oriented_lwh_mm"]
        packed += float(length) * float(width) * float(height)
    return packed / volume


def _action(action: list | tuple) -> tuple:
    return tuple(action)


def verify_preflight_file(document: dict, *, dataset_sha256: str, code_on_disk: dict[str, str]) -> dict[str, Any]:
    """Comprueba las capturas guardadas. No empaqueta."""

    errors = []
    if document.get("dataset_sha256") != dataset_sha256:
        errors.append("el dataset del preflight no coincide")
    recorded = document.get("code_sha256") or {}
    for relative in CODE_COMPATIBILITY:
        if recorded.get(relative) != code_on_disk.get(relative):
            errors.append(f"código distinto del preflight: {relative}")
    reuse = {}
    for order in document.get("orders") or []:
        checkpoint = order.get("checkpoint") or {}
        states = order.get("states") or []
        if len(states) != 1:
            errors.append(f"{order.get('order_id')}: el preflight no tiene un único estado")
            continue
        evaluation = states[0]
        alternatives = evaluation.get("alternatives") or []
        if len(alternatives) != 2 or not any(row.get("is_greedy") for row in alternatives):
            errors.append(f"{order.get('order_id')}: faltan las dos alternativas con Greedy")
        snapshot = order.get("snapshot") or {}
        for row in alternatives:
            capture = row.get("capture")
            if row.get("q_hat") is None or not row.get("audited") or not isinstance(capture, dict):
                errors.append(f"{order.get('order_id')}: retorno no reutilizable")
                continue
            if capture.get("physical_stability_verified") is not None:
                errors.append(f"{order.get('order_id')}: estabilidad física marcada")
            if capture.get("input_items") != snapshot.get("items"):
                errors.append(f"{order.get('order_id')}: la entrada de la captura no coincide")
            recomputed = recompute_u(capture)
            if recomputed is None or abs(recomputed - float(row["q_hat"])) > 0:
                errors.append(f"{order.get('order_id')}: Q_hat no coincide con el volumen de la captura")
            action = _action(row["action"])
            if list(action) != list(checkpoint.get("greedy_key") or []) and row.get("is_greedy"):
                errors.append(f"{order.get('order_id')}: la acción Greedy no coincide")
            reuse[(order["order_id"], action)] = {
                "q_hat": float(row["q_hat"]),
                "is_greedy": bool(row["is_greedy"]),
                "audited": True,
                "capture_ok": True,
                "reason": None,
                "source": "preflight",
                "continuation_seconds": row.get("continuation_seconds"),
                "capture_seconds": row.get("capture_seconds"),
                "audit_seconds": row.get("audit_seconds"),
            }
        stored_actions = [_action(item) for item in checkpoint.get("alternatives") or []]
        if [_action(row["action"]) for row in alternatives] != stored_actions:
            errors.append(f"{order.get('order_id')}: las acciones no coinciden con el checkpoint")
    return {"ok": not errors, "errors": errors, "reuse": reuse}


def admit_state(budget: Budget, *, already_counted: bool) -> bool:
    if already_counted:
        return True
    if budget.states_used >= budget.max_states:
        return False
    budget.states_used += 1
    return True


def evaluate_planned_actions(
    actions: list,
    *,
    reuse: dict,
    order_id: str,
    budget: Budget,
    now: Callable[[], float],
    deadline: float,
    run_one: Callable[[tuple], dict],
    greedy_key: tuple | list | None = None,
) -> list[dict]:
    rows = []
    greedy_identity = None if greedy_key is None else _action(greedy_key)

    def _pending(identity: tuple, reason: str) -> dict:
        return {
            "action": list(identity),
            "is_greedy": identity == greedy_identity,
            "q_hat": None,
            "audited": False,
            "capture_ok": False,
            "reason": reason,
            "source": "not_run",
            "continuation_seconds": None,
            "capture_seconds": None,
            "audit_seconds": None,
        }

    try:
        for action in actions:
            identity = _action(action)
            cached = reuse.get((order_id, identity))
            if cached is not None:
                rows.append({"action": list(identity), **cached})
                continue
            if budget.continuations_used >= budget.max_continuations or now() > deadline:
                rows.append(_pending(identity, "not_run"))
                continue
            budget.continuations_used += 1
            rows.append(run_one(identity))
    except WallClockExceeded as exc:
        done = {_action(row["action"]) for row in rows}
        for action in actions:
            identity = _action(action)
            if identity not in done:
                rows.append(_pending(identity, "wall_clock"))
        exc.partial_rows = rows
        raise
    return rows


def finalize_state(actions: list, rows: list[dict]) -> dict[str, Any]:
    greedy_rows = [row for row in rows if row.get("is_greedy")]
    complete = (
        len(rows) == len(actions)
        and len(greedy_rows) == 1
        and greedy_rows[0].get("q_hat") is not None
        and all(row.get("q_hat") is not None and row.get("audited") and row.get("capture_ok") for row in rows)
    )
    labels = []
    if complete:
        greedy_q = float(greedy_rows[0]["q_hat"])
        for row in rows:
            labels.append(
                {
                    "action": row["action"],
                    "is_greedy": row["is_greedy"],
                    "q_hat": float(row["q_hat"]),
                    "a_hat": float(row["q_hat"]) - greedy_q,
                }
            )
    return {"captured": True, "complete": complete, "alternatives": rows, "labels": labels}


def _median_positive(values: list[float], eps: float) -> float:
    positive = [value for value in values if value > eps]
    if not positive:
        return 0.0
    return float(statistics.median(positive))


def summarize(orders: list[dict], *, wall_seconds: float, gate: dict) -> dict[str, Any]:
    eps = float(gate["positive_eps"])
    evaluable = []
    complete_states = 0
    programmed = 0
    unknown = 0
    uncaptured_budget = 0
    not_inspected = []
    inspected_without_choice = []
    inspected_without_complete = []
    distribution = []
    best_examined = []
    per_order = []
    for order in orders:
        if not order.get("inspected"):
            not_inspected.append(order["order_id"])
            per_order.append({**_order_public(order), "evaluable": False})
            continue
        uncaptured_budget += int(order.get("states_not_captured_budget") or 0)
        states = [state for state in order.get("states") or [] if state.get("captured")]
        if not states:
            inspected_without_choice.append(order["order_id"])
        complete = [state for state in states if state.get("complete")]
        complete_states += len(complete)
        positives = []
        superior = 0
        n_alternatives = 0
        for state in states:
            for row in state.get("alternatives") or []:
                programmed += 1
                n_alternatives += 1
                if row.get("q_hat") is None:
                    unknown += 1
            if not state.get("complete"):
                continue
            labels = state.get("labels") or []
            advantages = [float(item["a_hat"]) for item in labels]
            distribution.extend(advantages)
            if advantages:
                best_examined.append(max(advantages))
            if any(value > eps for value in advantages):
                superior += 1
            positives.extend(value for value in advantages if value > eps)
        if complete:
            metrics = {
                "f_i": superior / len(complete),
                "m_i": _median_positive(positives, eps),
                "n_complete_states": len(complete),
                "n_alternatives": n_alternatives,
                "evaluable": True,
            }
            evaluable.append(metrics)
        else:
            metrics = {
                "f_i": None,
                "m_i": None,
                "n_complete_states": 0,
                "n_alternatives": n_alternatives,
                "evaluable": False,
            }
            if order["order_id"] not in inspected_without_choice:
                inspected_without_complete.append(order["order_id"])
        per_order.append({**_order_public(order), **metrics})
    mean_f = statistics.fmean(item["f_i"] for item in evaluable) if evaluable else None
    mean_m = statistics.fmean(item["m_i"] for item in evaluable) if evaluable else None
    unknown_rate = (unknown / programmed) if programmed else 0.0
    conditions = {
        "orders_with_complete_state": len(evaluable) >= int(gate["min_orders_with_complete_state"]),
        "complete_states": complete_states >= int(gate["min_complete_states"]),
        "mean_f": mean_f is not None and mean_f >= float(gate["min_mean_f"]),
        "mean_m": mean_m is not None and mean_m >= float(gate["min_mean_m"]),
        "unknown_rate": unknown_rate < float(gate["max_unknown_rate"]),
        "wall": wall_seconds <= float(gate["max_wall_seconds"]),
    }
    coverage_ok = conditions["orders_with_complete_state"] and conditions["complete_states"]
    integrity_ok = conditions["unknown_rate"] and conditions["wall"]
    margin_ok = conditions["mean_f"] and conditions["mean_m"]
    if not coverage_ok or not integrity_ok:
        classification = "inconcluso"
    elif not margin_ok:
        classification = "no_avanzar"
    else:
        classification = "margen_suficiente_para_disenar_el_experimento_de_aprendizaje"
    negatives = sum(1 for value in distribution if value < -eps)
    zeros = sum(1 for value in distribution if abs(value) <= eps)
    positives_n = sum(1 for value in distribution if value > eps)
    return {
        "per_order": per_order,
        "evaluable_n": len(evaluable),
        "complete_states": complete_states,
        "mean_f": mean_f,
        "mean_m": mean_m,
        "programmed_continuations": programmed,
        "unknown_returns": unknown,
        "unknown_rate": unknown_rate,
        "states_not_captured_budget": uncaptured_budget,
        "orders_not_inspected": not_inspected,
        "orders_inspected_without_choice": inspected_without_choice,
        "orders_inspected_without_complete": inspected_without_complete,
        "a_hat_distribution": {"negative": negatives, "zero": zeros, "positive": positives_n, "values": distribution},
        "best_examined_margin": best_examined,
        "conditions": conditions,
        "classification": classification,
        "authorizes_training": False,
        "wall_seconds": wall_seconds,
    }


def _order_public(order: dict) -> dict[str, Any]:
    return {
        "order_id": order["order_id"],
        "target": order.get("target"),
        "inspected": bool(order.get("inspected")),
        "states_not_captured_budget": int(order.get("states_not_captured_budget") or 0),
        "choice_states_found": order.get("choice_states_found"),
    }


def run_sequence(
    specs: list[dict],
    *,
    process_order: Callable[[dict], dict],
    budget: Budget,
    deadline: float,
    now: Callable[[], float],
    emit: Callable[[dict], None],
) -> dict[str, Any]:
    done = []
    pending = [spec["order_id"] for spec in specs]
    status = "completed"
    current_index = 0
    try:
        for index, spec in enumerate(specs):
            current_index = index
            if now() > deadline or budget.states_used >= budget.max_states:
                status = "wall_clock" if now() > deadline else "state_cap"
                pending = [item["order_id"] for item in specs[index:]]
                break
            row = process_order(spec)
            done.append(row)
            pending = [item["order_id"] for item in specs[index + 1 :]]
            emit({"status": "running", "orders": done, "pending_order_ids": pending})
    except WallClockExceeded as exc:
        partial = getattr(exc, "partial", None)
        included = isinstance(partial, dict)
        if included:
            done.append(partial)
        pending = [item["order_id"] for item in specs[current_index + (1 if included else 0) :]]
        status = "wall_clock"
    document = {"status": status, "orders": done, "pending_order_ids": pending}
    try:
        emit(document)
    except WallClockExceeded:
        pass
    return document


def directory_must_be_new(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"el directorio de salida ya existe: {path}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
