"""Ejecuta una vez la campaña congelada. Rechaza una salida ya existente."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
for entry in (str(PAPER_TOOLS), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from campaign import (  # noqa: E402
    CODE_COMPATIBILITY,
    Budget,
    CompatibilityError,
    admit_state,
    directory_must_be_new,
    evaluate_planned_actions,
    file_sha256,
    finalize_state,
    preflight_accounted_seconds,
    run_sequence,
    semantic_equivalence,
    summarize,
    verify_preflight_file,
)
from compact_study import build_compact_problem  # noqa: E402
from diagnostic import (  # noqa: E402
    WallClockExceeded,
    collect_states,
    continue_from,
    score_solution,
)
from pilot_common import REPO_ROOT, sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from run_preflight import _checkpoint_public, arm_wall_clock, disarm_wall_clock  # noqa: E402


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _public_order(order: dict) -> dict:
    states = []
    for state in order.get("states") or []:
        alternatives = []
        for row in state.get("alternatives") or []:
            alternatives.append({key: value for key, value in row.items() if key != "capture"})
        states.append({**state, "alternatives": alternatives})
    return {**order, "states": states}


def _live_match(state: dict, preflight_order: dict) -> bool:
    public = _checkpoint_public(state)
    checkpoint = preflight_order["checkpoint"]
    return (
        public["sha256"] == checkpoint["sha256"]
        and public["greedy_key"] == checkpoint["greedy_key"]
        and public["alternatives"][:2] == checkpoint["alternatives"]
        and public["remaining_ids"] == checkpoint["remaining_ids"]
    )


def _run_action(problem, snapshot, state, identity, *, dataset, dataset_sha256, order_id, deadline, continuation_timeout, audit_timeout, now):
    started = now()
    local_deadline = min(deadline, started + continuation_timeout)
    try:
        outcome = continue_from(problem, state["checkpoint"], identity, deadline=local_deadline, now=now)
    except WallClockExceeded:
        raise
    continuation_seconds = now() - started
    is_greedy = tuple(identity) == tuple(state["greedy_key"])
    base = {
        "action": list(identity),
        "is_greedy": is_greedy,
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


def _process_factory(orders, dataset, dataset_sha256, preflight_orders, reuse, budget, deadline, output: Path):
    def process(spec: dict) -> dict:
        now = time.perf_counter
        problem = build_compact_problem(orders, spec["order_id"])
        snapshot = problem_snapshot(problem)
        acquired = now()
        holder = {"states": []}
        try:
            found = collect_states(
                problem,
                max_states=5,
                alternative_limit=4,
                deadline=deadline,
                now=now,
            )
            acquisition_seconds = now() - acquired
            preflight_order = preflight_orders.get(spec["order_id"])
            not_captured = 0
            for index, state in enumerate(found):
                already = False
                if preflight_order is not None and index == 0:
                    if not _live_match(state, preflight_order):
                        raise CompatibilityError(f"el estado inicial de {spec['order_id']} no coincide con el preflight")
                    already = True
                if not admit_state(budget, already_counted=already):
                    not_captured += 1
                    continue
                actions = [list(action) for action in state["alternatives"]]

                def run_one(identity, state=state):
                    return _run_action(
                        problem,
                        snapshot,
                        state,
                        identity,
                        dataset=dataset,
                        dataset_sha256=dataset_sha256,
                        order_id=spec["order_id"],
                        deadline=deadline,
                        continuation_timeout=budget.continuation_timeout,
                        audit_timeout=budget.audit_timeout,
                        now=now,
                    )

                try:
                    rows = evaluate_planned_actions(
                        actions,
                        reuse=reuse,
                        order_id=spec["order_id"],
                        budget=budget,
                        now=now,
                        deadline=deadline,
                        run_one=run_one,
                        greedy_key=state["greedy_key"],
                    )
                except WallClockExceeded as exc:
                    rows = list(getattr(exc, "partial_rows", []) or [])
                    finalized = finalize_state(actions, rows)
                    finalized["state_index"] = index
                    finalized["checkpoint_sha256"] = _checkpoint_public(state)["sha256"]
                    holder["states"].append(finalized)
                    raise
                finalized = finalize_state(actions, rows)
                finalized["state_index"] = index
                finalized["checkpoint_sha256"] = _checkpoint_public(state)["sha256"]
                holder["states"].append(finalized)
            row = {
                "order_id": spec["order_id"],
                "target": spec["target"],
                "inspected": True,
                "states": holder["states"],
                "choice_states_found": len(found),
                "states_not_captured_budget": not_captured,
                "state_acquisition_seconds": acquisition_seconds,
                "trajectory_exhausted": len(found) < 5,
            }
            _write(output / "orders" / f"{spec['order_id']}.json", row)
            print(
                f"{spec['order_id']} states={len(row['states'])} "
                f"continuations={budget.continuations_used}",
                flush=True,
            )
            return row
        except WallClockExceeded as exc:
            exc.partial = {
                "order_id": spec["order_id"],
                "target": spec["target"],
                "inspected": True,
                "states": holder["states"],
                "choice_states_found": None,
                "states_not_captured_budget": 0,
                "reason": "wall_clock",
            }
            _write(output / "orders" / f"{spec['order_id']}.json", exc.partial)
            raise
        except CompatibilityError:
            raise

    return process


def _timing(orders: list[dict], *, preflight_seconds: float, startup_seconds: float, elapsed: float) -> dict:
    continuation = capture = audit = acquisition = 0.0
    for order in orders:
        acquisition += float(order.get("state_acquisition_seconds") or 0.0)
        for state in order.get("states") or []:
            for row in state.get("alternatives") or []:
                if row.get("source") == "preflight":
                    continue
                continuation += float(row.get("continuation_seconds") or 0.0)
                capture += float(row.get("capture_seconds") or 0.0)
                audit += float(row.get("audit_seconds") or 0.0)
    return {
        "preflight_seconds": preflight_seconds,
        "startup_seconds": startup_seconds,
        "state_acquisition_seconds": acquisition,
        "continuation_seconds": continuation,
        "capture_seconds": capture,
        "audit_seconds": audit,
        "campaign_elapsed_seconds": elapsed,
        "accumulated_wall_seconds": preflight_seconds + elapsed,
        "note": "Paredes sucesivas de un proceso. La suma de fases no es coste de CPU.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    directory_must_be_new(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    draft_path = REPO_ROOT / "paper/studies/counterfactual_ranking/protocol_draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    equivalence = semantic_equivalence(draft, protocol)
    if not equivalence["equivalent"]:
        raise SystemExit(f"bloqueo: el congelado no equivale al borrador: {equivalence['mismatches']}")
    manifest_path = REPO_ROOT / protocol["sample_manifest"]
    sample = json.loads(manifest_path.read_text(encoding="utf-8"))
    if file_sha256(manifest_path) != protocol["sample_manifest_sha256"]:
        raise SystemExit("bloqueo: la muestra no coincide con el hash congelado")
    dataset_path = Path(args.dataset)
    dataset_sha = sha256_file(dataset_path)
    if dataset_sha != protocol["dataset_sha256"]:
        raise SystemExit("bloqueo: el dataset no coincide con el hash congelado")
    preflight_path = Path(args.preflight)
    preflight_sha = file_sha256(preflight_path)
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    accounted = preflight_accounted_seconds(preflight)
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_COMPATIBILITY}
    checked = verify_preflight_file(preflight, dataset_sha256=dataset_sha, code_on_disk=code)
    if not checked["ok"]:
        _write(output / "preflight_compatibility.json", {"ok": False, "errors": checked["errors"]})
        raise SystemExit("bloqueo: el preflight no es compatible")
    protocol_sha = file_sha256(protocol_path)
    budget = Budget(
        protocol,
        preflight_states=int(protocol["preflight_observed"]["states"]),
        preflight_continuations=int(protocol["preflight_observed"]["continuations"]),
    )
    allowance = budget.wall_seconds - accounted["seconds"]
    deadline = started + allowance
    manifest = {
        "role": "manifiesto_previo",
        "continuations_started": False,
        "protocol_frozen_sha256": protocol_sha,
        "protocol_draft_sha256": file_sha256(draft_path),
        "semantic_equivalence": equivalence,
        "dataset_sha256": dataset_sha,
        "sample_manifest_sha256": protocol["sample_manifest_sha256"],
        "preflight_sha256": preflight_sha,
        "preflight_accounted_seconds": accounted,
        "code_sha256": code,
        "budget": protocol["budget"],
        "gate": protocol["gate"],
        "execution_order": sample["execution_order"],
    }
    _write(output / "manifest.json", manifest)
    arm_wall_clock(max(deadline - time.perf_counter(), 0.001))
    startup_seconds = 0.0
    document = None
    try:
        orders = json.loads(dataset_path.read_text(encoding="utf-8"))
        startup_seconds = time.perf_counter() - started
        by_id = {row["order_id"]: row for rows in sample["selected"].values() for row in rows}
        specs = [by_id[order_id] for order_id in sample["execution_order"]]
        preflight_orders = {order["order_id"]: order for order in preflight["orders"]}
        for order_id in protocol["preflight_observed"]["order_ids"]:
            probe = collect_states(
                build_compact_problem(orders, order_id),
                max_states=1,
                alternative_limit=4,
                deadline=deadline,
            )
            if not probe or not _live_match(probe[0], preflight_orders[order_id]):
                _write(
                    output / "preflight_compatibility.json",
                    {"ok": False, "errors": [f"estado en vivo distinto: {order_id}"], "continuations_started": False},
                )
                raise SystemExit(f"bloqueo: el estado de {order_id} no coincide con el preflight")
        _write(
            output / "preflight_compatibility.json",
            {
                "ok": True,
                "errors": [],
                "continuations_started": False,
                "reused_orders": protocol["preflight_observed"]["order_ids"],
                "preflight_sha256": preflight_sha,
                "semantic_equivalence": equivalence,
            },
        )
        manifest["continuations_started"] = True
        _write(output / "manifest.json", manifest)

        def emit(document: dict) -> None:
            _write(
                output / "results_partial.json",
                {
                    **document,
                    "orders": [_public_order(order) for order in document.get("orders") or []],
                    "preflight_sha256": preflight_sha,
                    "accumulated_wall_seconds": accounted["seconds"] + (time.perf_counter() - started),
                },
            )

        document = run_sequence(
            specs,
            process_order=_process_factory(
                orders,
                str(dataset_path),
                dataset_sha,
                preflight_orders,
                checked["reuse"],
                budget,
                deadline,
                output,
            ),
            budget=budget,
            deadline=deadline,
            now=time.perf_counter,
            emit=emit,
        )
    except CompatibilityError as exc:
        disarm_wall_clock()
        _write(output / "preflight_compatibility.json", {"ok": False, "errors": [str(exc)], "continuations_started": True})
        raise SystemExit(f"bloqueo: {exc}") from exc
    except WallClockExceeded:
        disarm_wall_clock()
        if document is None:
            partial_path = output / "results_partial.json"
            if partial_path.is_file():
                document = json.loads(partial_path.read_text(encoding="utf-8"))
                document["status"] = "wall_clock"
            else:
                document = {"status": "wall_clock", "orders": [], "pending_order_ids": sample.get("execution_order", [])}
    finally:
        disarm_wall_clock()
    elapsed = time.perf_counter() - started
    wall = accounted["seconds"] + elapsed
    public_orders = [_public_order(order) for order in document.get("orders") or []]
    known = {order["order_id"] for order in public_orders}
    catalog = {row["order_id"]: row for rows in sample["selected"].values() for row in rows}
    for order_id in document.get("pending_order_ids") or []:
        if order_id in known:
            continue
        public_orders.append(
            {
                "order_id": order_id,
                "target": (catalog.get(order_id) or {}).get("target"),
                "inspected": False,
                "states": [],
                "states_not_captured_budget": 0,
            }
        )
    summary = summarize(public_orders, wall_seconds=wall, gate=protocol["gate"])
    timing = _timing(public_orders, preflight_seconds=accounted["seconds"], startup_seconds=startup_seconds, elapsed=elapsed)
    _write(output / "results.json", {**document, "orders": public_orders, "timing": timing, "summary": summary})
    _write(
        output / "verification.json",
        {
            "role": "verificacion_del_diagnostico",
            "preflight_sha256": preflight_sha,
            "protocol_frozen_sha256": protocol_sha,
            "classification": summary["classification"],
            "authorizes_training": False,
            "summary": summary,
            "timing": timing,
        },
    )
    inspected = [order["order_id"] for order in public_orders if order.get("inspected")]
    _write(
        output / "exposure_registry.json",
        {
            "role": "pedidos_inspeccionados_en_el_diagnostico",
            "order_ids": inspected,
            "preflight_already_observed": protocol["preflight_observed"]["order_ids"],
            "pending_order_ids": document.get("pending_order_ids") or [],
        },
    )
    print(document.get("status"), summary["classification"], wall)


if __name__ == "__main__":
    main()
