"""Preflight reducido: dos pedidos train, hasta cuatro estados y dieciséis continuaciones."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
PAPER = STUDY.parents[1]
REPO = PAPER.parent
PAPER_TOOLS = PAPER / "tools"
COUNTERFACTUAL_TOOLS = PAPER / "studies" / "counterfactual_ranking" / "tools"

for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from campaign import recompute_u  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from diagnostic import (  # noqa: E402
    WallClockExceeded,
    _geometry,
    _legal_options,
    _setup,
    capture_checkpoint,
    continue_from,
    score_solution,
)
from pipeline import labeling_select_support  # noqa: E402
from pilot_common import sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from quantile_sampling import quantile_indices  # noqa: E402
from support_api import CONTRACT_NAME, SUPPORT_LIMIT, build_S_from_options  # noqa: E402

CONTINUATION_TIMEOUT = 60.0
AUDIT_TIMEOUT = 60.0
GLOBAL_TIMEOUT = 900.0


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_choice_states(problem: Any, *, deadline: float, now: Callable[[], float]) -> list[dict[str, Any]]:
    session, mask, policy, budget, remaining = _setup(problem)
    constraints = problem.constraints
    found: list[dict[str, Any]] = []
    while remaining:
        if now() > deadline:
            raise WallClockExceeded("wall_clock")
        select_s, observe_p = budget.window(len(remaining))
        if select_s != 1 or observe_p != 1:
            raise RuntimeError("ventana distinta de p=s=1")
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
        if len(options) >= 2 and chosen is not None:
            legal_ids = []
            for index, option in enumerate(options):
                cand = option.candidate
                legal_ids.append(
                    [
                        int(cand.bin_index),
                        float(cand.position.x),
                        float(cand.position.y),
                        float(cand.position.z),
                        float(cand.dimensions.length),
                        float(cand.dimensions.width),
                        float(cand.dimensions.height),
                        index,
                    ]
                )
            support = labeling_select_support(options, chosen, limit=SUPPORT_LIMIT)
            # Repetición sin Q_hat
            support_again = build_S_from_options(options, chosen, limit=SUPPORT_LIMIT)
            support_ids = [
                [
                    int(opt.candidate.bin_index),
                    float(opt.candidate.position.x),
                    float(opt.candidate.position.y),
                    float(opt.candidate.position.z),
                    float(opt.candidate.dimensions.length),
                    float(opt.candidate.dimensions.width),
                    float(opt.candidate.dimensions.height),
                ]
                for opt in support
            ]
            support_ids_again = [
                [
                    int(opt.candidate.bin_index),
                    float(opt.candidate.position.x),
                    float(opt.candidate.position.y),
                    float(opt.candidate.position.z),
                    float(opt.candidate.dimensions.length),
                    float(opt.candidate.dimensions.width),
                    float(opt.candidate.dimensions.height),
                ]
                for opt in support_again
            ]
            if support_ids != support_ids_again:
                raise RuntimeError("S no es repetible sin Q_hat")
            greedy_id = support_ids[0]
            if greedy_id not in support_ids:
                raise RuntimeError("Greedy ausente de S")
            # Verificar que greedy está primero y en S
            gkey = [
                int(chosen.candidate.bin_index),
                float(chosen.candidate.position.x),
                float(chosen.candidate.position.y),
                float(chosen.candidate.position.z),
                float(chosen.candidate.dimensions.length),
                float(chosen.candidate.dimensions.width),
                float(chosen.candidate.dimensions.height),
            ]
            if support_ids[0] != gkey:
                raise RuntimeError("Greedy no es el primer elemento de S")
            checkpoint = capture_checkpoint(session, remaining)
            found.append(
                {
                    "choice_index": len(found),
                    "current_item_id": current.id,
                    "n_legal": len(options),
                    "legal_ids": legal_ids,
                    "support_ids": support_ids,
                    "support_contract": CONTRACT_NAME,
                    "greedy_key": gkey,
                    "checkpoint": checkpoint,
                    "geometry_before": checkpoint["geometry"],
                    "alternatives": [
                        {
                            "action": row,
                            "is_greedy": row == gkey,
                        }
                        for row in support_ids
                    ],
                }
            )
        if chosen is None:
            break
        before = _geometry(session)
        session.commit(chosen.candidate, chosen.item)
        if found and found[-1]["geometry_before"] != before:
            # geometry_before was captured before commit; OK
            pass
        remaining = [item for item in remaining if item.id != chosen.item.id]
    return found


def run_order_preflight(
    orders: dict[str, Any],
    *,
    order_id: str,
    target: str,
    dataset: str,
    dataset_sha256: str,
    output: Path,
    deadline: float,
    now: Callable[[], float],
    max_states: int,
    max_continuations: int,
    counters: dict[str, int],
) -> dict[str, Any]:
    started = now()
    problem = build_compact_problem(orders, order_id)
    snapshot = problem_snapshot(problem)
    found = collect_choice_states(problem, deadline=deadline, now=now)
    indices = quantile_indices(len(found), limit=4)[:max_states]
    selected = [found[index] for index in indices]
    state_rows = []
    for state in selected:
        if counters["states"] >= 4 or counters["continuations"] >= max_continuations:
            break
        counters["states"] += 1
        alt_rows = []
        for alt in state["alternatives"]:
            if counters["continuations"] >= max_continuations or now() > deadline:
                alt_rows.append({**alt, "q_hat": None, "reason": "not_run", "audited": False})
                continue
            counters["continuations"] += 1
            local_deadline = min(deadline, now() + CONTINUATION_TIMEOUT)
            outcome = continue_from(
                problem,
                state["checkpoint"],
                tuple(alt["action"]),
                deadline=local_deadline,
                now=now,
            )
            if outcome["status"] != "ok" or outcome["solution"] is None:
                alt_rows.append(
                    {
                        **alt,
                        "q_hat": None,
                        "reason": outcome.get("reason") or outcome["status"],
                        "audited": False,
                        "capture": None,
                    }
                )
                continue
            scored = score_solution(
                problem,
                outcome["solution"],
                order_id=order_id,
                dataset=dataset,
                dataset_sha256=dataset_sha256,
                snapshot=snapshot,
                deadline=min(deadline, now() + AUDIT_TIMEOUT),
                now=now,
            )
            capture = scored.get("capture")
            recomputed = recompute_u(capture) if isinstance(capture, dict) else None
            q_hat = scored.get("q_hat")
            if q_hat is not None and recomputed is not None and abs(float(q_hat) - float(recomputed)) > 1e-12:
                raise RuntimeError("Q_hat no coincide con el volumen recompuesto")
            # La acción del estado es el placement del ítem actual, no necesariamente placements[0].
            action_matches_capture = None
            geometry_valid = None
            if isinstance(capture, dict) and capture.get("placements"):
                current_id = state["current_item_id"]
                matched = [row for row in capture["placements"] if row.get("item_id") == current_id]
                if matched:
                    first = matched[0]
                    oriented = list(first["oriented_lwh_mm"])
                    flb = list(first["flb_mm"])
                    action_matches_capture = (
                        abs(flb[0] - alt["action"][1]) < 1e-9
                        and abs(flb[1] - alt["action"][2]) < 1e-9
                        and abs(flb[2] - alt["action"][3]) < 1e-9
                        and abs(oriented[0] - alt["action"][4]) < 1e-9
                        and abs(oriented[1] - alt["action"][5]) < 1e-9
                        and abs(oriented[2] - alt["action"][6]) < 1e-9
                    )
                # evaluate_outcome deja q_hat solo si no hay failure_types geométricos.
                geometry_valid = q_hat is not None and not list(scored.get("audit_failure_types") or [])
            alt_rows.append(
                {
                    **alt,
                    "q_hat": q_hat,
                    "recomputed_u_geom": recomputed,
                    "reason": scored.get("reason"),
                    "audited": bool(scored.get("audit_seconds") is not None and capture),
                    "capture_ok": q_hat is not None and isinstance(capture, dict),
                    "geometry_valid": geometry_valid,
                    "action_matches_first_placement": action_matches_capture,
                    "action_matches_current_item_placement": action_matches_capture,
                    "suffix_ids_not_an_actor_input": list(state["checkpoint"]["remaining_ids"]),
                    "capture": capture,
                    "continuation_status": outcome["status"],
                    "audit_failure_types": list(scored.get("audit_failure_types") or []),
                }
            )
        complete = bool(alt_rows) and all(row.get("q_hat") is not None and row.get("audited") for row in alt_rows)
        state_rows.append(
            {
                "choice_index": state["choice_index"],
                "quantile_position": state["choice_index"],
                "current_item_id": state["current_item_id"],
                "n_legal": state["n_legal"],
                "legal_ids": state["legal_ids"],
                "support_ids": state["support_ids"],
                "support_contract": state["support_contract"],
                "greedy_key": state["greedy_key"],
                "greedy_in_support": state["greedy_key"] in state["support_ids"],
                "alternatives": [
                    {key: value for key, value in row.items() if key != "capture"} | {"capture_saved": row.get("capture") is not None}
                    for row in alt_rows
                ],
                "complete": complete,
                "checkpoint_remaining_ids": list(state["checkpoint"]["remaining_ids"]),
            }
        )
        # persist captures separately
        state_dir = output / "states" / f"choice_{state['choice_index']}"
        state_dir.mkdir(parents=True, exist_ok=True)
        for index, row in enumerate(alt_rows):
            if row.get("capture") is not None:
                (state_dir / f"alt_{index}_capture.json").write_text(
                    json.dumps(row["capture"], ensure_ascii=False) + "\n", encoding="utf-8"
                )
        (state_dir / "state.json").write_text(
            json.dumps(state_rows[-1], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    unknown = sum(1 for state in state_rows for row in state["alternatives"] if row.get("q_hat") is None)
    return {
        "order_id": order_id,
        "target": target,
        "n_choice_states_found": len(found),
        "selected_indices": indices,
        "states": state_rows,
        "unknown_returns": unknown,
        "wall_seconds": now() - started,
        "snapshot_target": snapshot.get("target"),
        "physical_stability_verified": None,
    }


def run_preflight(protocol: dict[str, Any], sample_manifest: dict[str, Any], output: Path) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"el directorio de preflight no está vacío: {output}")
    output.mkdir(parents=True, exist_ok=True)
    dataset = Path(protocol["dataset"])
    dataset_sha = sha256_file(dataset)
    if dataset_sha != protocol["dataset_sha256"]:
        raise RuntimeError("dataset SHA distinto del protocolo")
    orders = json.loads(dataset.read_text(encoding="utf-8"))
    deadline = time.perf_counter() + float(protocol["budget"]["preflight_wall_seconds"])
    counters = {"states": 0, "continuations": 0}
    results = []
    started = time.perf_counter()
    try:
        for row in sample_manifest["preflight_orders"]:
            if time.perf_counter() > deadline:
                raise WallClockExceeded("wall_clock")
            order_dir = output / "orders" / row["order_id"]
            order_dir.mkdir(parents=True, exist_ok=True)
            result = run_order_preflight(
                orders,
                order_id=row["order_id"],
                target=row["target"],
                dataset=str(dataset),
                dataset_sha256=dataset_sha,
                output=order_dir,
                deadline=deadline,
                now=time.perf_counter,
                max_states=2,
                max_continuations=16,
                counters=counters,
            )
            (order_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            results.append({key: value for key, value in result.items() if key != "states"} | {"n_states": len(result["states"])})
    except WallClockExceeded:
        status = "incomplete_wall_clock"
    else:
        status = "completed"
    code_hashes = {
        relative: file_sha256(STUDY / relative)
        for relative in protocol["code_files"]
    }
    memory = {
        "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "note": "ru_maxrss es pico del proceso; no es RSS conjunto ni duración de pared",
    }
    unknown = sum(item.get("unknown_returns", 0) for item in results)
    verification = {
        "status": status,
        "orders": results,
        "states_used": counters["states"],
        "continuations_used": counters["continuations"],
        "unknown_returns": unknown,
        "wall_seconds": time.perf_counter() - started,
        "memory": memory,
        "code_hashes": code_hashes,
        "protocol_sha256": protocol.get("sha256"),
        "support_contract": CONTRACT_NAME,
        "greedy_in_all_recorded_supports": all(
            state.get("greedy_in_support")
            for order in (json.loads((output / "orders" / item["order_id"] / "result.json").read_text()) for item in results)
            for state in order.get("states", [])
        )
        if results
        else False,
        "physical_stability_verified": None,
        "training_executed": False,
        "development_executed": False,
        "test_executed": False,
    }
    (output / "preflight_verification.json").write_text(
        json.dumps(verification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return verification
