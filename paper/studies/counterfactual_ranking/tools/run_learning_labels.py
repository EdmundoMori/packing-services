"""Genera una vez las etiquetas del piloto. No entrena."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
for _entry in (str(PAPER_TOOLS), str(HERE)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from actor_features import FEATURE_NAMES
from campaign import directory_must_be_new, file_sha256, recompute_u
from compact_study import build_compact_problem
from diagnostic import WallClockExceeded
from label_campaign import (
    LabelBudget,
    collect_choice_states,
    label_selected_states,
    learning_rows,
    run_label_sequence,
    select_quantile_states,
)
from model_spec import TRAINING_CONFIG
from objectives import fit_normalization
from pilot_common import REPO_ROOT, sha256_file
from pilot_problems import problem_snapshot
from run_preflight import arm_wall_clock, disarm_wall_clock
from select_sample import signature_payload

CODE_FILES = (
    "paper/studies/counterfactual_ranking/tools/actor_features.py",
    "paper/studies/counterfactual_ranking/tools/objectives.py",
    "paper/studies/counterfactual_ranking/tools/model_spec.py",
    "paper/studies/counterfactual_ranking/tools/label_sampling.py",
    "paper/studies/counterfactual_ranking/tools/label_campaign.py",
    "paper/studies/counterfactual_ranking/tools/run_learning_labels.py",
    "paper/studies/counterfactual_ranking/tools/diagnostic.py",
    "paper/tools/compact_study.py",
    "paper/tools/pilot_metrics.py",
    "paper/tools/pilot_problems.py",
    "paper/tools/audit_internal_solution.py",
)
DIAGNOSTIC_ORDERS = (
    "00109938",
    "00109266",
    "00102701",
    "00108060",
    "00104500",
    "00103525",
    "00100812",
    "00109602",
    "00109122",
    "00104671",
    "00105640",
    "00109225",
    "00100129",
    "00103399",
    "00105687",
    "00107454",
    "00109271",
    "00105150",
    "00109874",
    "00101397",
)


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


def _specs(protocol: dict) -> list[dict]:
    catalog = {}
    for split in ("train", "development"):
        for target, rows in protocol["splits"].items():
            for row in rows[split]:
                catalog[row["order_id"]] = {**row, "split": split}
    return [catalog[order_id] for order_id in protocol["execution_order"]]


def _verify_identities(protocol: dict, orders: dict, specs: list[dict]) -> None:
    seen_signatures = {}
    diagnostic = set(DIAGNOSTIC_ORDERS)
    prefix = protocol["dataset"]["selection_prefix"]
    for spec in specs:
        order_id = spec["order_id"]
        if order_id in diagnostic:
            raise SystemExit(f"bloqueo: {order_id} pertenece al diagnóstico")
        digest = hashlib.sha256(f"{prefix}{order_id}".encode("utf-8")).hexdigest()
        if digest != spec["selection_hash"]:
            raise SystemExit(f"bloqueo: el hash de selección de {order_id} no coincide")
        problem = build_compact_problem(orders, order_id)
        signature = signature_payload(problem_snapshot(problem), spec["target"])
        if signature != spec["signature"]:
            raise SystemExit(f"bloqueo: la firma de {order_id} no coincide")
        if signature in seen_signatures:
            raise SystemExit(f"bloqueo: {order_id} clona a {seen_signatures[signature]}")
        seen_signatures[signature] = order_id
        if str((orders[order_id].get("properties") or {}).get("target") or "") != spec["target"]:
            raise SystemExit(f"bloqueo: el target de {order_id} no coincide")


def _process_factory(orders, dataset, dataset_sha256, budget, deadline, output: Path):
    def process(spec: dict) -> dict:
        now = time.perf_counter
        problem = build_compact_problem(orders, spec["order_id"])
        snapshot = problem_snapshot(problem)
        acquired = now()
        found = None
        try:
            found = collect_choice_states(problem, deadline=deadline, now=now, alternative_limit=4)
            acquisition = now() - acquired
            indices, selected = select_quantile_states(found, limit=4)
            room = budget.max_states - budget.states_used
            admitted = selected[: max(room, 0)]
            not_captured = len(selected) - len(admitted)
            states = label_selected_states(
                problem,
                snapshot,
                admitted,
                dataset=dataset,
                dataset_sha256=dataset_sha256,
                order_id=spec["order_id"],
                budget=budget,
                deadline=deadline,
                now=now,
            )
            order = {
                "order_id": spec["order_id"],
                "target": spec["target"],
                "split": spec["split"],
                "selection_hash": spec["selection_hash"],
                "signature": spec["signature"],
                "n_items": spec.get("n_items"),
                "inspected": True,
                "acquisition_complete": True,
                "n_choice_states": len(found),
                "selected_indices": indices[: len(states)],
                "states_not_captured_budget": not_captured,
                "state_acquisition_seconds": acquisition,
                "states": states,
            }
            _write(output / "orders" / f"{spec['order_id']}.json", order)
            print(
                f"{spec['split']} {spec['order_id']} choice={len(found)} labeled={len(states)} "
                f"continuations={budget.continuations_used}",
                flush=True,
            )
            return order
        except WallClockExceeded as exc:
            partial_states = list(getattr(exc, "partial_states", []) or [])
            order = {
                "order_id": spec["order_id"],
                "target": spec["target"],
                "split": spec["split"],
                "selection_hash": spec["selection_hash"],
                "signature": spec["signature"],
                "n_items": spec.get("n_items"),
                "inspected": True,
                "acquisition_complete": found is not None,
                "n_choice_states": None if found is None else len(found),
                "selected_indices": [],
                "states_not_captured_budget": 0,
                "state_acquisition_seconds": now() - acquired,
                "states": partial_states,
                "reason": "wall_clock" if found is not None else "wall_clock_during_acquisition",
            }
            _write(output / "orders" / f"{spec['order_id']}.json", order)
            exc.partial = order
            raise

    return process


def _coverage(orders: list[dict]) -> dict:
    summary: dict[str, Any] = {}
    for order in orders:
        key = f"{order.get('split')}|{order.get('target')}"
        bucket = summary.setdefault(
            key,
            {
                "split": order.get("split"),
                "target": order.get("target"),
                "orders": 0,
                "orders_inspected": 0,
                "choice_states": 0,
                "labeled_states": 0,
                "complete_states": 0,
                "incomplete_states": 0,
                "continuations": 0,
                "unknown_returns": 0,
                "positive_gaps": 0,
                "zero_gaps": 0,
                "negative_gaps": 0,
            },
        )
        bucket["orders"] += 1
        if order.get("inspected"):
            bucket["orders_inspected"] += 1
        bucket["choice_states"] += int(order.get("n_choice_states") or 0)
        for state in order.get("states") or []:
            bucket["labeled_states"] += 1
            bucket["complete_states"] += int(bool(state.get("complete")))
            bucket["incomplete_states"] += int(not state.get("complete"))
            q_values = []
            greedy_q = None
            for row in state.get("alternatives") or []:
                bucket["continuations"] += 1
                if row.get("q_hat") is None:
                    bucket["unknown_returns"] += 1
                else:
                    q_values.append(float(row["q_hat"]))
                    if row.get("is_greedy"):
                        greedy_q = float(row["q_hat"])
            if state.get("complete") and greedy_q is not None:
                for value in q_values:
                    gap = value - greedy_q
                    if gap > 1e-9:
                        bucket["positive_gaps"] += 1
                    elif gap < -1e-9:
                        bucket["negative_gaps"] += 1
                    else:
                        bucket["zero_gaps"] += 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    directory_must_be_new(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    protocol_path = Path(args.protocol)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "congelado_para_generar_etiquetas" or protocol.get("training") is not False:
        raise SystemExit("bloqueo: el protocolo de etiquetas no está congelado o autoriza entrenamiento")
    if list(protocol["features"]["kept_columns"]) != list(FEATURE_NAMES):
        raise SystemExit("bloqueo: las columnas del protocolo no son las implementadas")
    dataset_path = Path(args.dataset)
    dataset_sha = sha256_file(dataset_path)
    if dataset_sha != protocol["dataset"]["sha256"]:
        raise SystemExit("bloqueo: el dataset no coincide")
    specs = _specs(protocol)
    if len(specs) != 36:
        raise SystemExit("bloqueo: no hay 36 pedidos")
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}
    if code != protocol["code_sha256"]:
        raise SystemExit("bloqueo: el código ejecutado no coincide con el protocolo congelado")
    budget = LabelBudget(protocol)
    deadline = started + budget.wall_seconds
    manifest = {
        "role": "manifiesto_previo",
        "continuations_started": False,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "protocol_sha256": file_sha256(protocol_path),
        "dataset_sha256": dataset_sha,
        "code_sha256": code,
        "execution_order": protocol["execution_order"],
        "label_budget": protocol["label_budget"],
        "training_config_not_executed": TRAINING_CONFIG,
        "training": False,
    }
    _write(output / "manifest.json", manifest)
    arm_wall_clock(max(deadline - time.perf_counter(), 0.001))
    document = None
    try:
        orders = json.loads(dataset_path.read_text(encoding="utf-8"))
        _verify_identities(protocol, orders, specs)
        manifest["continuations_started"] = True
        manifest["identity_check"] = "firmas_hashes_y_ausencia_de_clones_ok"
        _write(output / "manifest.json", manifest)

        def emit(payload: dict) -> None:
            _write(
                output / "results_partial.json",
                {
                    **payload,
                    "orders": [_public_order(order) for order in payload.get("orders") or []],
                    "elapsed_seconds": time.perf_counter() - started,
                },
            )

        document = run_label_sequence(
            specs,
            process_order=_process_factory(orders, str(dataset_path), dataset_sha, budget, deadline, output),
            budget=budget,
            deadline=deadline,
            now=time.perf_counter,
            emit=emit,
        )
    except WallClockExceeded:
        disarm_wall_clock()
        if document is None:
            partial_path = output / "results_partial.json"
            if partial_path.is_file():
                document = json.loads(partial_path.read_text(encoding="utf-8"))
                document["status"] = "wall_clock"
            else:
                document = {"status": "wall_clock", "orders": [], "pending_order_ids": protocol["execution_order"]}
    finally:
        disarm_wall_clock()
    elapsed = time.perf_counter() - started
    public_orders = [_public_order(order) for order in document.get("orders") or []]
    known = {order["order_id"] for order in public_orders}
    catalog = {spec["order_id"]: spec for spec in specs}
    for order_id in document.get("pending_order_ids") or []:
        if order_id in known:
            continue
        spec = catalog[order_id]
        public_orders.append(
            {
                "order_id": order_id,
                "target": spec["target"],
                "split": spec["split"],
                "inspected": False,
                "states": [],
                "n_choice_states": 0,
                "states_not_captured_budget": 0,
            }
        )
    train_rows = [row["features"] for row in learning_rows(public_orders, split="train")]
    normalization = fit_normalization(train_rows) if train_rows else None
    if normalization is not None:
        _write(output / "normalization.json", normalization)
    coverage = _coverage(public_orders)
    _write(
        output / "results.json",
        {
            **document,
            "orders": public_orders,
            "coverage": coverage,
            "elapsed_seconds": elapsed,
            "states_used": budget.states_used,
            "continuations_used": budget.continuations_used,
            "training": False,
            "normalization_fit_on": "complete_train_candidate_rows" if normalization else None,
        },
    )
    print(document.get("status"), elapsed, budget.states_used, budget.continuations_used)


if __name__ == "__main__":
    main()
