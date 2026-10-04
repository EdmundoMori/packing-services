"""Etiquetas del piloto. Recorre Greedy, elige cuantiles y continúa.

No entrena. Un retorno desconocido queda null. Un estado incompleto no
entra en las filas de aprendizaje ni en la normalización.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from actor_features import encode_candidate, feature_sha256
from diagnostic import (
    WallClockExceeded,
    _geometry,
    _legal_options,
    _setup,
    candidate_key,
    capture_checkpoint,
    continue_from,
    score_solution,
    select_alternatives,
)
from label_sampling import quantile_indices


class LabelBudget:
    def __init__(self, protocol: dict[str, Any]) -> None:
        budget = protocol["label_budget"]
        self.max_states = int(budget["max_states"])
        self.max_continuations = int(budget["max_continuations"])
        self.continuation_timeout = float(budget["continuation_timeout_seconds"])
        self.audit_timeout = float(budget["capture_and_audit_timeout_seconds"])
        self.wall_seconds = float(budget["wall_seconds"])
        self.states_used = 0
        self.continuations_used = 0


def collect_choice_states(
    problem: Any,
    *,
    deadline: float | None,
    now: Callable[[], float] | None = None,
    alternative_limit: int = 4,
) -> list[dict[str, Any]]:
    """Estados con al menos dos candidatas, en el orden de la trayectoria Greedy."""

    clock = now or time.perf_counter
    if deadline is not None and clock() > deadline:
        raise WallClockExceeded("wall_clock")
    session, mask, policy, budget, remaining = _setup(problem)
    constraints = problem.constraints
    found: list[dict[str, Any]] = []
    while remaining:
        if deadline is not None and clock() > deadline:
            raise WallClockExceeded("wall_clock")
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("la ventana dejó de ser un ítem")
        current = remaining[0]
        options = _legal_options(session, current, constraints, mask)
        chosen = policy.decide(
            options,
            preview=remaining[:observe_p],
            remaining_count=0,
            session=session,
            constraints=constraints,
            mask=mask,
        )
        saved_geometry = None
        if len(options) >= 2 and chosen is not None:
            alternatives = select_alternatives(options, chosen, limit=alternative_limit)
            greedy_key = candidate_key(chosen.candidate)
            rows = []
            for option in alternatives:
                identity = candidate_key(option.candidate)
                features = encode_candidate(session, current, option.candidate)
                rows.append(
                    {
                        "action": list(identity),
                        "is_greedy": identity == greedy_key,
                        "features": features,
                        "feature_sha256": feature_sha256(features),
                        "q_hat": None,
                        "reason": None,
                        "audited": False,
                        "capture_ok": False,
                        "source": "pending",
                    }
                )
            found.append(
                {
                    "choice_index": len(found),
                    "checkpoint": capture_checkpoint(session, remaining),
                    "current_item_id": current.id,
                    "n_legal": len(options),
                    "greedy_key": list(greedy_key),
                    "alternatives": rows,
                }
            )
            saved_geometry = found[-1]["checkpoint"]["geometry"]
        if chosen is None:
            break
        before = _geometry(session)
        session.commit(chosen.candidate, chosen.item)
        if saved_geometry is not None and saved_geometry != before:
            raise RuntimeError("guardar el estado alteró la geometría ya registrada")
        remaining = [item for item in remaining if item.id != chosen.item.id]
    return found


def _run_alternative(
    problem: Any,
    snapshot: dict[str, Any],
    state: dict[str, Any],
    row: dict[str, Any],
    *,
    dataset: str,
    dataset_sha256: str,
    order_id: str,
    deadline: float,
    continuation_timeout: float,
    audit_timeout: float,
    now: Callable[[], float],
) -> dict[str, Any]:
    started = now()
    local_deadline = min(deadline, started + continuation_timeout)
    outcome = continue_from(
        problem,
        state["checkpoint"],
        tuple(row["action"]),
        deadline=local_deadline,
        now=now,
    )
    continuation_seconds = now() - started
    base = {
        **row,
        "q_hat": None,
        "audited": False,
        "capture_ok": False,
        "source": "new",
        "continuation_seconds": continuation_seconds,
        "capture_seconds": None,
        "audit_seconds": None,
        "capture": None,
    }
    if outcome["status"] != "ok" or outcome["solution"] is None:
        base["reason"] = "wall_clock" if now() >= deadline else (outcome.get("reason") or outcome["status"])
        return base
    scored = score_solution(
        problem,
        outcome["solution"],
        order_id=order_id,
        dataset=dataset,
        dataset_sha256=dataset_sha256,
        snapshot=snapshot,
        deadline=min(deadline, now() + audit_timeout),
        now=now,
    )
    base.update(
        {
            "q_hat": scored["q_hat"],
            "reason": scored["reason"],
            "audited": scored.get("audit_seconds") is not None and isinstance(scored.get("capture"), dict),
            "capture_ok": scored["q_hat"] is not None and isinstance(scored.get("capture"), dict),
            "capture_seconds": scored.get("capture_seconds"),
            "audit_seconds": scored.get("audit_seconds"),
            "capture": scored.get("capture"),
        }
    )
    return base


def _pending(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **row,
        "q_hat": None,
        "audited": False,
        "capture_ok": False,
        "reason": reason,
        "source": "not_run",
        "continuation_seconds": None,
        "capture_seconds": None,
        "audit_seconds": None,
        "capture": None,
    }


def complete_state(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(row.get("q_hat") is not None and row.get("audited") and row.get("capture_ok") for row in rows)


def label_selected_states(
    problem: Any,
    snapshot: dict[str, Any],
    states: list[dict[str, Any]],
    *,
    dataset: str,
    dataset_sha256: str,
    order_id: str,
    budget: LabelBudget,
    deadline: float,
    now: Callable[[], float],
) -> list[dict[str, Any]]:
    labeled = []
    try:
        for state in states:
            if budget.states_used >= budget.max_states:
                break
            budget.states_used += 1
            rows = []
            try:
                for row in state["alternatives"]:
                    if budget.continuations_used >= budget.max_continuations or now() > deadline:
                        rows.append(_pending(row, "not_run"))
                        continue
                    budget.continuations_used += 1
                    rows.append(
                        _run_alternative(
                            problem,
                            snapshot,
                            state,
                            row,
                            dataset=dataset,
                            dataset_sha256=dataset_sha256,
                            order_id=order_id,
                            deadline=deadline,
                            continuation_timeout=budget.continuation_timeout,
                            audit_timeout=budget.audit_timeout,
                            now=now,
                        )
                    )
            except WallClockExceeded:
                for row in state["alternatives"][len(rows) :]:
                    rows.append(_pending(row, "wall_clock"))
                labeled.append(_close_state(state, rows))
                raise
            labeled.append(_close_state(state, rows))
    except WallClockExceeded as exc:
        exc.partial_states = labeled
        raise
    return labeled


def _checkpoint_sha256(checkpoint: dict[str, Any]) -> str:
    from run_preflight import _jsonable

    payload = {
        "remaining_ids": list(checkpoint["remaining_ids"]),
        "geometry": _jsonable(checkpoint["geometry"]),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _close_state(state: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = sorted({row.get("reason") for row in rows if row.get("q_hat") is None and row.get("reason")})
    return {
        "choice_index": state["choice_index"],
        "current_item_id": state["current_item_id"],
        "n_legal": state["n_legal"],
        "greedy_key": list(state["greedy_key"]),
        "audit": {
            "checkpoint_sha256": _checkpoint_sha256(state["checkpoint"]),
            "suffix_ids_not_an_actor_input": list(state["checkpoint"]["remaining_ids"]),
        },
        "alternatives": rows,
        "complete": complete_state(rows),
        "incomplete_reasons": reasons,
        "eligible_for_learning": complete_state(rows),
    }


def select_quantile_states(found: list[dict[str, Any]], *, limit: int = 4) -> tuple[list[int], list[dict[str, Any]]]:
    indices = quantile_indices(len(found), limit=limit)
    return indices, [found[index] for index in indices]


def learning_rows(orders: list[dict[str, Any]], *, split: str | None = None) -> list[dict[str, Any]]:
    """Filas de estados completos. El sufijo no forma parte de la entrada."""

    rows = []
    for order in orders:
        if split is not None and order.get("split") != split:
            continue
        for state in order.get("states") or []:
            if not state.get("eligible_for_learning"):
                continue
            for alternative in state["alternatives"]:
                rows.append(
                    {
                        "split": order["split"],
                        "order_id": order["order_id"],
                        "target": order["target"],
                        "choice_index": state["choice_index"],
                        "action": alternative["action"],
                        "features": alternative["features"],
                        "q_hat": alternative["q_hat"],
                    }
                )
    return rows


def run_label_sequence(
    specs: list[dict[str, Any]],
    *,
    process_order: Callable[[dict[str, Any]], dict[str, Any]],
    budget: LabelBudget,
    deadline: float,
    now: Callable[[], float],
    emit: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    done: list[dict[str, Any]] = []
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
