"""Preflight de rendimiento sobre el subconjunto ya declarado.

El reloj global cubre la carga, la obtención de estados, la restauración,
la continuación, la captura, la auditoría y la escritura. Una señal de
reloj puede interrumpir ese trabajo. El directorio de salida no se sobrescribe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
for entry in (str(PAPER_TOOLS), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from compact_study import build_compact_problem  # noqa: E402
from diagnostic import (  # noqa: E402
    CONTINUATION_TIMEOUT_SECONDS,
    PREFLIGHT_WALL_CLOCK_SECONDS,
    WallClockExceeded,
    collect_states,
    evaluate_state,
)
from pilot_common import REPO_ROOT, sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from select_sample import selection_hash  # noqa: E402

PREFLIGHT_ORDER_IDS = ("00109938", "00105640")
CODE_FILES = (
    "paper/studies/counterfactual_ranking/tools/run_preflight.py",
    "paper/studies/counterfactual_ranking/tools/diagnostic.py",
    "paper/studies/counterfactual_ranking/tools/select_sample.py",
    "paper/studies/counterfactual_ranking/protocol_draft.json",
    "paper/studies/counterfactual_ranking/sample_manifest.json",
    "paper/tools/compact_study.py",
    "paper/tools/pilot_metrics.py",
    "paper/tools/pilot_problems.py",
    "paper/tools/audit_internal_solution.py",
)


class InvocationError(Exception):
    pass


def _on_wall(signum, frame) -> None:
    del signum, frame
    raise WallClockExceeded("wall_clock")


def arm_wall_clock(seconds: float) -> None:
    if seconds <= 0:
        raise WallClockExceeded("wall_clock")
    signal.signal(signal.SIGALRM, _on_wall)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))


def disarm_wall_clock() -> None:
    signal.setitimer(signal.ITIMER_REAL, 0.0)
    signal.signal(signal.SIGALRM, signal.SIG_DFL)


def declared_subset(manifest: dict) -> dict:
    selected = manifest["selected"]
    orders = []
    for target in ("euro-pallet", "rollcontainer"):
        rows = selected.get(target) or []
        if not rows:
            raise ValueError(f"la muestra no tiene un primer pedido de {target}")
        orders.append(rows[0])
    return {
        "orders": orders,
        "max_states_per_order": 1,
        "max_alternatives": 2,
        "continuation_timeout_seconds": CONTINUATION_TIMEOUT_SECONDS,
        "wall_clock_seconds": PREFLIGHT_WALL_CLOCK_SECONDS,
        "counts_toward_sample": True,
        "counts_toward_budget": True,
        "may_reselect_sample": False,
    }


def require_declared_orders(protocol: dict, manifest: dict) -> dict:
    subset = declared_subset(manifest)
    ids = tuple(row["order_id"] for row in subset["orders"])
    registered = (protocol["preflight"]["euro-pallet"], protocol["preflight"]["rollcontainer"])
    if ids != PREFLIGHT_ORDER_IDS or ids != registered:
        raise InvocationError("los pedidos del preflight no son 00109938 y 00105640")
    if subset["max_states_per_order"] != 1 or subset["max_alternatives"] != 2:
        raise InvocationError("el alcance del preflight no es un estado y dos alternativas")
    return subset


def require_hashes(protocol: dict, manifest_path: Path, manifest: dict, dataset_path: Path) -> tuple[str, str]:
    dataset_sha = sha256_file(dataset_path)
    manifest_sha = sha256_file(manifest_path)
    if dataset_sha != protocol["dataset_sha256"] or dataset_sha != manifest.get("dataset_sha256"):
        raise InvocationError("el dataset no coincide con los hashes registrados")
    if manifest_sha != protocol["sample_manifest_sha256"]:
        raise InvocationError("la muestra no coincide con el hash registrado")
    if dataset_path.resolve() != Path(protocol["dataset"]).resolve():
        raise InvocationError("la ruta del dataset no es la registrada")
    return dataset_sha, manifest_sha


def code_hashes() -> dict[str, str]:
    found = {}
    for relative in CODE_FILES:
        path = REPO_ROOT / relative
        found[relative] = sha256_file(path) if path.is_file() else None
    return found


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _checkpoint_public(state: dict) -> dict:
    checkpoint = state["checkpoint"]
    payload = {
        "remaining_ids": list(checkpoint["remaining_ids"]),
        "geometry": _jsonable(checkpoint["geometry"]),
        "greedy_key": list(state["greedy_key"]),
        "alternatives": [list(action) for action in state["alternatives"]],
        "n_legal": state["n_legal"],
        "current_item_id": state["current_item_id"],
        "orientations": state["orientations"],
        "positions": state["positions"],
    }
    raw = json.dumps(
        {"remaining_ids": payload["remaining_ids"], "geometry": payload["geometry"]},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    payload["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return payload


def _order_wall(spec: dict, *, state_acquisition_seconds: float | None, partial: dict | None) -> dict:
    return {
        "order_id": spec["order_id"],
        "target": spec.get("target"),
        "selection_hash": selection_hash(spec["order_id"]),
        "reason": "wall_clock",
        "state_acquisition_seconds": state_acquisition_seconds,
        "states": [] if partial is None else [partial],
        "q_values_known": False,
    }


def _run_order(spec: dict, orders: dict, dataset: str, dataset_sha256: str, subset: dict, deadline: float | None) -> dict:
    clock = time.perf_counter
    build_started = clock()
    problem = build_compact_problem(orders, spec["order_id"])
    snapshot = problem_snapshot(problem)
    problem_build_seconds = clock() - build_started
    acquisition_started = clock()
    try:
        states = collect_states(
            problem,
            max_states=subset["max_states_per_order"],
            alternative_limit=subset["max_alternatives"],
            deadline=deadline,
        )
    except WallClockExceeded as exc:
        exc.partial = _order_wall(spec, state_acquisition_seconds=clock() - acquisition_started, partial=None)
        raise
    state_acquisition_seconds = clock() - acquisition_started
    base = {
        "order_id": spec["order_id"],
        "target": spec["target"],
        "selection_hash": selection_hash(spec["order_id"]),
        "problem_build_seconds": problem_build_seconds,
        "state_acquisition_seconds": state_acquisition_seconds,
        "reason": None,
    }
    if not states:
        base["reason"] = "sin_estado_con_eleccion"
        base["states"] = []
        base["snapshot"] = snapshot
        return base
    state = states[0]
    checkpoint = _checkpoint_public(state)
    try:
        evaluation = evaluate_state(
            problem,
            state,
            order_id=spec["order_id"],
            dataset=dataset,
            dataset_sha256=dataset_sha256,
            snapshot=snapshot,
            timeout_seconds=subset["continuation_timeout_seconds"],
            global_deadline=deadline,
            keep_captures=True,
        )
    except WallClockExceeded as exc:
        exc.partial = {
            **base,
            "reason": "wall_clock",
            "checkpoint": checkpoint,
            "snapshot": snapshot,
            "states": [] if exc.partial is None else [exc.partial],
        }
        raise
    base.update({"reason": None, "checkpoint": checkpoint, "snapshot": snapshot, "states": [evaluation]})
    return base


def run(
    manifest: dict,
    orders: dict,
    dataset: str,
    dataset_sha256: str,
    output: Path,
    *,
    deadline: float | None = None,
    protocol_sha256: str | None = None,
    manifest_sha256: str | None = None,
    startup_seconds: float | None = None,
    code: dict[str, str] | None = None,
) -> dict:
    if output.exists():
        raise FileExistsError(f"el directorio de salida ya existe: {output}")
    subset = declared_subset(manifest)
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    rows = []
    status = "completed"
    try:
        for spec in subset["orders"]:
            if deadline is not None and time.perf_counter() > deadline:
                rows.append(_order_wall(spec, state_acquisition_seconds=None, partial=None))
                status = "wall_clock"
                break
            try:
                rows.append(_run_order(spec, orders, dataset, dataset_sha256, subset, deadline))
            except WallClockExceeded as exc:
                rows.append(exc.partial or _order_wall(spec, state_acquisition_seconds=None, partial=None))
                status = "wall_clock"
                break
    except WallClockExceeded:
        status = "wall_clock"
    write_started = time.perf_counter()
    document = {
        "role": "preflight_de_rendimiento",
        "status": status,
        "counts_toward_sample": True,
        "counts_toward_budget": True,
        "may_reselect_sample": False,
        "observed_order_ids": [row["order_id"] for row in rows],
        "declared_order_ids": list(PREFLIGHT_ORDER_IDS),
        "max_states_per_order": subset["max_states_per_order"],
        "max_alternatives": subset["max_alternatives"],
        "continuation_timeout_seconds": subset["continuation_timeout_seconds"],
        "wall_clock_seconds_limit": subset["wall_clock_seconds"],
        "wall_clock_covers": [
            "carga",
            "obtencion_de_estados",
            "restauracion",
            "continuacion",
            "captura",
            "auditoria",
            "escritura",
        ],
        "startup_seconds": startup_seconds,
        "work_wall_seconds": time.perf_counter() - started,
        "dataset": dataset,
        "dataset_sha256": dataset_sha256,
        "manifest_sha256": manifest_sha256,
        "protocol_sha256": protocol_sha256,
        "code_sha256": code or {},
        "orders": rows,
    }
    (output / "preflight.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    document["write_seconds"] = time.perf_counter() - write_started
    document["work_wall_seconds"] = time.perf_counter() - started
    (output / "preflight.json").write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    process_started = time.perf_counter()
    output = Path(args.output)
    if output.exists():
        raise SystemExit(f"bloqueo: el directorio de salida ya existe: {output}")
    arm_wall_clock(PREFLIGHT_WALL_CLOCK_SECONDS)
    deadline = process_started + PREFLIGHT_WALL_CLOCK_SECONDS
    document = None
    try:
        protocol_path = Path(args.protocol)
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        manifest_path = Path(protocol["sample_manifest"])
        if not manifest_path.is_absolute():
            manifest_path = REPO_ROOT / manifest_path
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "lista_preparada":
            raise InvocationError("la muestra no está preparada")
        require_declared_orders(protocol, manifest)
        dataset_path = Path(args.dataset)
        dataset_sha, manifest_sha = require_hashes(protocol, manifest_path, manifest, dataset_path)
        orders = json.loads(dataset_path.read_text(encoding="utf-8"))
        startup_seconds = time.perf_counter() - process_started
        document = run(
            manifest,
            orders,
            dataset=str(dataset_path),
            dataset_sha256=dataset_sha,
            output=output,
            deadline=deadline,
            protocol_sha256=sha256_file(protocol_path),
            manifest_sha256=manifest_sha,
            startup_seconds=startup_seconds,
            code=code_hashes(),
        )
    except InvocationError as exc:
        raise SystemExit(f"bloqueo: {exc}") from exc
    except WallClockExceeded as exc:
        disarm_wall_clock()
        output.mkdir(parents=True, exist_ok=True)
        stub = {
            "role": "preflight_de_rendimiento",
            "status": "wall_clock",
            "q_hat": None,
            "reason": "wall_clock",
            "partial": exc.partial,
            "work_wall_seconds": time.perf_counter() - process_started,
            "observed_order_ids": list(PREFLIGHT_ORDER_IDS),
        }
        (output / "preflight.json").write_text(json.dumps(stub, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        document = stub
    finally:
        disarm_wall_clock()
    if document is not None:
        print(document.get("status"), document.get("work_wall_seconds"))


if __name__ == "__main__":
    main()
