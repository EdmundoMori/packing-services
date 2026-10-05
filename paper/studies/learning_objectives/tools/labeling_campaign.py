"""Campaña de etiquetado: restauración, continuación, captura y auditoría.

No entrena. Desconoce test. Conserva evidencia parcial ante fallos.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from campaign import recompute_u  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from diagnostic import WallClockExceeded, continue_from, score_solution  # noqa: E402
from labeling_contracts import (  # noqa: E402
    AUDIT_TIMEOUT_SECONDS,
    CONTINUATION_TIMEOUT_SECONDS,
    PUBLISHED_PREFLIGHT_WALL_SECONDS,
)
from labeling_reuse import PreflightReuseIndex  # noqa: E402
from labeling_states import collect_choice_states, select_quantile_states  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402


class LabelBudget:
    def __init__(self, protocol: dict[str, Any]) -> None:
        labeling = protocol["labeling"]
        self.train_max_states = int(labeling["train_max_states"])
        self.train_max_continuations = int(labeling["train_max_continuations"])
        self.development_max_states = int(labeling["development_max_states"])
        self.development_max_continuations = int(labeling["development_max_continuations"])
        self.states_per_order_max = int(labeling["states_per_order_max"])
        self.continuation_timeout = CONTINUATION_TIMEOUT_SECONDS
        self.audit_timeout = AUDIT_TIMEOUT_SECONDS
        self.wall_seconds = float(protocol["budget"]["labeling_wall_seconds"])
        self.states_used = {"train": 0, "development": 0}
        self.continuations_new = {"train": 0, "development": 0}
        self.continuations_reused = 0
        self.continuations_unknown = 0
        self.pending_continuations = 0

    def can_add_state(self, split: str) -> bool:
        limit = self.train_max_states if split == "train" else self.development_max_states
        return self.states_used[split] < limit

    def can_add_new_continuation(self, split: str) -> bool:
        limit = self.train_max_continuations if split == "train" else self.development_max_continuations
        return self.continuations_new[split] < limit


def _pending(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **row,
        "q_hat": None,
        "recomputed_u_geom": None,
        "audited": False,
        "capture_ok": False,
        "geometry_valid": None,
        "source": "not_run",
        "reason": reason,
        "continuation_seconds": None,
        "capture_seconds": None,
        "audit_seconds": None,
        "capture": None,
    }


def complete_state(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(
        row.get("q_hat") is not None and row.get("audited") and row.get("capture_ok") for row in rows
    )


def _run_new_alternative(
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
    if now() > deadline:
        return _pending(row, "wall_clock")
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
        "recomputed_u_geom": None,
        "audited": False,
        "capture_ok": False,
        "geometry_valid": None,
        "source": "new",
        "continuation_seconds": continuation_seconds,
        "capture_seconds": None,
        "audit_seconds": None,
        "capture": None,
        "reason": None,
    }
    if outcome["status"] != "ok" or outcome["solution"] is None:
        reason = outcome.get("reason") or outcome["status"]
        if now() >= deadline or reason in {"wall_clock", "timeout"}:
            base["reason"] = "wall_clock"
        else:
            base["reason"] = reason
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
    capture = scored.get("capture")
    recomputed = recompute_u(capture) if isinstance(capture, dict) else None
    q_hat = scored.get("q_hat")
    if q_hat is not None and recomputed is not None and abs(float(q_hat) - float(recomputed)) > 1e-12:
        raise RuntimeError("Q_hat no coincide con el volumen recompuesto")
    action_matches = None
    geometry_valid = None
    if isinstance(capture, dict) and capture.get("placements"):
        matched = [item for item in capture["placements"] if item.get("item_id") == state["current_item_id"]]
        if matched:
            first = matched[0]
            flb = list(first["flb_mm"])
            oriented = list(first["oriented_lwh_mm"])
            action = row["action"]
            action_matches = (
                abs(flb[0] - action[1]) < 1e-9
                and abs(flb[1] - action[2]) < 1e-9
                and abs(flb[2] - action[3]) < 1e-9
                and abs(oriented[0] - action[4]) < 1e-9
                and abs(oriented[1] - action[5]) < 1e-9
                and abs(oriented[2] - action[6]) < 1e-9
            )
        geometry_valid = q_hat is not None and not list(scored.get("audit_failure_types") or [])
    if scored.get("reason"):
        base["reason"] = scored["reason"]
    base.update(
        {
            "q_hat": q_hat,
            "recomputed_u_geom": recomputed,
            "audited": scored.get("audit_seconds") is not None and isinstance(capture, dict),
            "capture_ok": q_hat is not None and isinstance(capture, dict),
            "geometry_valid": geometry_valid,
            "action_matches_current_item_placement": action_matches,
            "audit_failure_types": list(scored.get("audit_failure_types") or []),
            "capture_seconds": scored.get("capture_seconds"),
            "audit_seconds": scored.get("audit_seconds"),
            "capture": capture,
            "suffix_ids_not_an_actor_input": list(state["checkpoint"]["remaining_ids"]),
        }
    )
    return base


def label_order(
    orders_blob: dict[str, Any],
    spec: dict[str, Any],
    *,
    dataset: str,
    dataset_sha256: str,
    output_order_dir: Path,
    budget: LabelBudget,
    reuse: PreflightReuseIndex,
    deadline: float,
    now: Callable[[], float],
) -> dict[str, Any]:
    started = now()
    split = spec["split"]
    order_id = spec["order_id"]
    problem = build_compact_problem(orders_blob, order_id)
    snapshot = problem_snapshot(problem)
    found = collect_choice_states(problem, deadline=deadline, now=now)
    indices, selected = select_quantile_states(found, limit=budget.states_per_order_max)
    state_rows: list[dict[str, Any]] = []
    failure_tags: list[str] = []
    if len(found) == 0:
        failure_tags.append("no_eligible_choice_states")
    try:
        for state in selected:
            if not budget.can_add_state(split) or now() > deadline:
                for alt in state["alternatives"]:
                    budget.pending_continuations += 1
                failure_tags.append("state_cap" if not budget.can_add_state(split) else "wall_clock")
                break
            budget.states_used[split] += 1
            rows: list[dict[str, Any]] = []
            for alt in state["alternatives"]:
                if now() > deadline:
                    rows.append(_pending(alt, "wall_clock"))
                    budget.pending_continuations += 1
                    budget.continuations_unknown += 1
                    failure_tags.append("wall_clock")
                    continue
                reused = reuse.try_reuse(order_id, state, alt)
                if reused is not None:
                    budget.continuations_reused += 1
                    rows.append(reused)
                    continue
                if not budget.can_add_new_continuation(split):
                    rows.append(_pending(alt, "continuation_cap"))
                    budget.pending_continuations += 1
                    budget.continuations_unknown += 1
                    failure_tags.append("continuation_cap")
                    continue
                budget.continuations_new[split] += 1
                labeled = _run_new_alternative(
                    problem,
                    snapshot,
                    state,
                    alt,
                    dataset=dataset,
                    dataset_sha256=dataset_sha256,
                    order_id=order_id,
                    deadline=deadline,
                    continuation_timeout=budget.continuation_timeout,
                    audit_timeout=budget.audit_timeout,
                    now=now,
                )
                if labeled.get("q_hat") is None:
                    budget.continuations_unknown += 1
                    if labeled.get("reason"):
                        failure_tags.append(str(labeled["reason"]))
                rows.append(labeled)
            is_complete = complete_state(rows)
            closed = {
                "choice_index": state["choice_index"],
                "current_item_id": state["current_item_id"],
                "n_legal": state["n_legal"],
                "legal_ids": state["legal_ids"],
                "support_ids": state["support_ids"],
                "support_contract": state["support_contract"],
                "greedy_key": state["greedy_key"],
                "greedy_in_support": state["greedy_in_support"],
                "n_support": len(state["support_ids"]),
                "fewer_than_four_geometries": len(state["support_ids"]) < 4,
                "checkpoint_remaining_ids": list(state["checkpoint"]["remaining_ids"]),
                "alternatives": [
                    {key: value for key, value in row.items() if key != "capture"}
                    | {"capture_saved": row.get("capture") is not None}
                    for row in rows
                ],
                "complete": is_complete,
                "eligible_for_learning": is_complete,
                "incomplete_reasons": sorted(
                    {row.get("reason") for row in rows if row.get("q_hat") is None and row.get("reason")}
                ),
            }
            state_rows.append(closed)
            state_dir = output_order_dir / "states" / f"choice_{state['choice_index']}"
            state_dir.mkdir(parents=True, exist_ok=True)
            for index, row in enumerate(rows):
                if row.get("capture") is not None:
                    (state_dir / f"alt_{index}_capture.json").write_text(
                        json.dumps(row["capture"], ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
            (state_dir / "state.json").write_text(
                json.dumps(closed, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    except WallClockExceeded:
        failure_tags.append("wall_clock")
        raise
    except Exception as exc:  # noqa: BLE001
        failure_tags.append(f"evaluator_internal:{type(exc).__name__}")
        partial = {
            "order_id": order_id,
            "split": split,
            "target": spec["target"],
            "status": "incomplete_evaluator_internal",
            "error": f"{type(exc).__name__}: {exc}",
            "selected_indices": indices,
            "n_choice_states_found": len(found),
            "states": state_rows,
            "unknown_returns": sum(
                1 for state in state_rows for row in state["alternatives"] if row.get("q_hat") is None
            ),
            "wall_seconds": now() - started,
            "failure_tags": sorted(set(failure_tags)),
            "physical_stability_verified": None,
        }
        output_order_dir.mkdir(parents=True, exist_ok=True)
        (output_order_dir / "result.json").write_text(
            json.dumps(partial, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise RuntimeError(f"error interno del evaluador en {order_id}: {exc}") from exc

    fewer_states = len(selected) < budget.states_per_order_max and len(found) < budget.states_per_order_max
    if fewer_states:
        failure_tags.append("fewer_eligible_states_than_max")
    unknown = sum(1 for state in state_rows for row in state["alternatives"] if row.get("q_hat") is None)
    result = {
        "order_id": order_id,
        "split": split,
        "target": spec["target"],
        "selection_hash": spec["selection_hash"],
        "signature": spec["signature"],
        "status": "ok",
        "n_choice_states_found": len(found),
        "selected_indices": indices,
        "states": state_rows,
        "n_states": len(state_rows),
        "unknown_returns": unknown,
        "wall_seconds": now() - started,
        "failure_tags": sorted(set(failure_tags)),
        "fewer_eligible_states_than_max": fewer_states,
        "physical_stability_verified": None,
        "naturally_stopped_without_choice_states": len(found) == 0,
    }
    output_order_dir.mkdir(parents=True, exist_ok=True)
    (output_order_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result


def run_labeling_campaign(
    *,
    protocol: dict[str, Any],
    ordered: list[dict[str, Any]],
    orders_blob: dict[str, Any],
    dataset: str,
    dataset_sha256: str,
    output: Path,
    reuse: PreflightReuseIndex,
    now: Callable[[], float] | None = None,
    deadline: float | None = None,
) -> dict[str, Any]:
    clock = now or time.perf_counter
    budget = LabelBudget(protocol)
    started = clock()
    labeling_deadline = deadline if deadline is not None else started + budget.wall_seconds
    done: list[dict[str, Any]] = []
    pending = [row["order_id"] for row in ordered]
    status = "completed"
    try:
        for spec in ordered:
            if spec["split"] == "test":
                raise RuntimeError("bloqueo: test en la campaña de etiquetado")
            if clock() > labeling_deadline:
                status = "incomplete_wall_clock"
                break
            order_dir = output / "orders" / spec["order_id"]
            result = label_order(
                orders_blob,
                spec,
                dataset=dataset,
                dataset_sha256=dataset_sha256,
                output_order_dir=order_dir,
                budget=budget,
                reuse=reuse,
                deadline=labeling_deadline,
                now=clock,
            )
            public = {key: value for key, value in result.items() if key != "states"}
            public["n_states"] = result["n_states"]
            done.append(public)
            pending = [row["order_id"] for row in ordered[len(done) :]]
            progress = {
                "status": "running",
                "orders_done": done,
                "pending_order_ids": pending,
                "budget": {
                    "states_used": budget.states_used,
                    "continuations_new": budget.continuations_new,
                    "continuations_reused": budget.continuations_reused,
                    "continuations_unknown": budget.continuations_unknown,
                    "pending_continuations": budget.pending_continuations,
                },
            }
            (output / "progress.json").write_text(
                json.dumps(progress, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    except WallClockExceeded:
        status = "incomplete_wall_clock"
    except RuntimeError as exc:
        if "error interno del evaluador" in str(exc):
            status = "incomplete_evaluator_internal"
        else:
            status = "incomplete_runtime"
            (output / "runtime_error.json").write_text(
                json.dumps({"error": str(exc)}, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            raise
    pending = [row["order_id"] for row in ordered if row["order_id"] not in {item["order_id"] for item in done}]
    if pending and status == "completed":
        status = "incomplete_pending_orders"
    labeling_wall = clock() - started
    summary = {
        "status": status,
        "orders": done,
        "pending_order_ids": pending,
        "n_orders_done": len(done),
        "n_orders_expected": len(ordered),
        "states_used": budget.states_used,
        "continuations_new": budget.continuations_new,
        "continuations_reused": budget.continuations_reused,
        "continuations_unknown": budget.continuations_unknown,
        "pending_continuations": budget.pending_continuations,
        "labeling_wall_seconds": labeling_wall,
        "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "global_accounted_wall_seconds": labeling_wall + PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "reuse": reuse.summary(),
        "training_executed": False,
        "development_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
    }
    (output / "labeling_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary
