#!/usr/bin/env python3
"""Evaluación única de development: 24 Greedy + 216 actores = 240 casos.

No abre test. Máximo 2 workers. Presupuesto 3600 s de development.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REPO = HERE.parents[3]
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(COUNTERFACTUAL_TOOLS), str(PAPER_TOOLS), str(HERE)):
    if entry in sys.path:
        sys.path.remove(entry)
sys.path.insert(0, str(COUNTERFACTUAL_TOOLS))
sys.path.insert(0, str(PAPER_TOOLS))
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

from campaign import recompute_u  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from episode_analysis import (  # noqa: E402
    ARMS,
    SEEDS,
    apply_development_gate,
    classify_episode,
    order_then_seed_aggregate,
    planned_cases,
    seed_report,
)
from labeling_contracts import verify_frozen_artifacts  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
from labeling_runctl import write_heartbeat, write_state  # noqa: E402
from model_spec import TRAINING_CONFIG, build_actor  # noqa: E402
from pilot_metrics import contrast_capture  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402
from training_loop import configure_training_runtime, load_checkpoint_logits  # noqa: E402

DEVELOPMENT_WALL = 3600.0
CASE_TIMEOUT = 300.0
MAX_WORKERS = 2
WORKER = HERE / "episode_worker.py"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_dir() -> Path | None:
    raw = os.environ.get("LABELING_RUN_DIR")
    return Path(raw) if raw else None


def development_orders(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [row for row in manifest["execution_order"] if row["split"] == "development"]
    if len(rows) != 24:
        raise RuntimeError(f"development debe tener 24 pedidos, got {len(rows)}")
    if any(row["split"] == "test" for row in rows):
        raise RuntimeError("test en development")
    return rows


def validate_checkpoints(models_dir: Path, normalization: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for seed in SEEDS:
        for arm in ARMS:
            path = models_dir / f"seed_{seed}" / arm / "checkpoint_epoch_40.pt"
            if not path.is_file():
                raise RuntimeError(f"checkpoint ausente: {path}")
            blob = torch.load(path, map_location="cpu", weights_only=False)
            meta = blob.get("meta") or {}
            if int(meta.get("epoch", -1)) != 40:
                raise RuntimeError(f"época distinta de 40: {path}")
            if int(meta.get("n_optimizer_steps", -1)) != 40:
                raise RuntimeError(f"pasos Adam distintos de 40: {path}")
            if meta.get("arm") != arm or int(meta.get("seed")) != int(seed):
                raise RuntimeError(f"meta brazo/semilla: {path}")
            model = build_actor(0)
            model.load_state_dict(blob["state_dict"])
            # logits reproducibles sobre un vector sintético
            feats = torch.zeros(2, 17, dtype=torch.float32)
            a = load_checkpoint_logits(path, feats)
            b = load_checkpoint_logits(path, feats)
            if a != b:
                raise RuntimeError(f"logits no reproducibles: {path}")
            rows.append(
                {
                    "path": str(path),
                    "arm": arm,
                    "seed": seed,
                    "sha256": file_sha256(path),
                    "initialization_sha256": meta.get("initialization_sha256"),
                    "permutation_sha256": meta.get("permutation_sha256"),
                    "logits_match": True,
                    "epoch": 40,
                }
            )
    if len(rows) != 9:
        raise RuntimeError("no hay nueve checkpoints")
    del normalization  # validación de uso ocurre al cargar stats en jobs
    return rows


def _audit(document: dict[str, Any]) -> dict[str, Any]:
    import importlib.util

    path = PAPER_TOOLS / "audit_internal_solution.py"
    spec = importlib.util.spec_from_file_location("audit_dev_eval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_document(document)


def invoke_case(
    job: dict[str, Any],
    *,
    case_dir: Path,
    timeout_s: float,
) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    job_path = case_dir / "job.json"
    result_path = case_dir / "worker_result.partial"
    atomic_write_json(job_path, job)
    atomic_write_json(case_dir / "input.json", job.get("input_snapshot") or {})
    cmd = [
        str((REPO / ".venv" / "bin" / "python").resolve()),
        "-u",
        str(WORKER.resolve()),
        "--job",
        str(job_path),
        "--result",
        str(result_path),
    ]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    env["OMP_NUM_THREADS"] = "1"
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "error": f"timeout de {timeout_s} s",
            "worker_failure": "timeout",
            "attempts": 1,
            "duration_seconds": time.perf_counter() - started,
            "stderr": (exc.stderr or "")[:2000] if isinstance(exc.stderr, str) else None,
            "capture": None,
        }
    wall = time.perf_counter() - started
    payload = None
    if result_path.is_file() and result_path.stat().st_size > 0:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        result_path.unlink()
    if payload is None:
        return {
            "status": "crash",
            "error": f"sin resultado worker rc={completed.returncode}",
            "worker_failure": "crash",
            "attempts": 1,
            "duration_seconds": wall,
            "stderr": (completed.stderr or "")[:2000],
            "capture": None,
        }
    payload["duration_seconds"] = wall
    payload["attempts"] = 1
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--study-dir", type=Path, required=True)
    p.add_argument("--models-dir", type=Path, required=True)
    p.add_argument("--labels-output", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--wall-seconds", type=float, default=DEVELOPMENT_WALL)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study = args.study_dir.resolve()
    models = args.models_dir.resolve()
    labels = args.labels_output.resolve()
    output = args.output.resolve()
    wall = float(args.wall_seconds)
    if wall > DEVELOPMENT_WALL:
        print(json.dumps({"status": "refused", "reason": "wall_exceeds_development_budget"}))
        return 2
    if output.exists() and any(output.iterdir()):
        print(json.dumps({"status": "refused", "reason": "output_exists"}))
        return 2

    configure_training_runtime()
    run_dir = _run_dir()
    if run_dir:
        write_state(
            run_dir,
            {
                "run_id": os.environ.get("LABELING_RUN_ID"),
                "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
                "status": "running",
                "pid": os.getpid(),
            },
        )

    contracts = verify_frozen_artifacts(
        protocol_path=study / "protocol_frozen.json",
        sample_path=study / "sample_manifest.json",
        study_dir=study,
    )
    protocol = contracts["protocol"]
    dataset = Path(contracts["dataset"])
    dataset_sha = contracts["dataset_sha256"]
    manifest = json.loads((labels / "execution_manifest.json").read_text(encoding="utf-8"))
    orders = development_orders(manifest)
    normalization = json.loads((labels / "normalization_train.json").read_text(encoding="utf-8"))
    stats = {"mean": normalization["mean"], "scale": normalization["scale"]}
    ckpt_rows = validate_checkpoints(models, normalization)
    cases = planned_cases(orders)

    # snapshots independientes de entrada
    prepare_imports()
    from splits import load_orders

    orders_blob = load_orders(dataset)
    snapshots = {}
    for order in orders:
        problem = build_compact_problem(orders_blob, order["order_id"])
        snapshots[order["order_id"]] = problem_snapshot(problem)

    training_summary = json.loads((models / "training_summary.json").read_text(encoding="utf-8"))
    ops = {
        "max_workers": MAX_WORKERS,
        "torch_num_threads": 1,
        "torch_num_interop_threads": 1,
        "case_timeout_seconds": CASE_TIMEOUT,
        "development_wall_seconds": wall,
        "recorded_before_launch": True,
        "decision_fixed": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / "operational_decision.json", ops)
    eval_manifest = {
        "kind": "development_evaluation_manifest",
        "n_cases": len(cases),
        "n_orders": len(orders),
        "n_greedy": 24,
        "n_actor": 216,
        "orders": orders,
        "cases": [{"key": c["key"], "order_id": c["order_id"], "arm": c["arm"], "seed": c["seed"]} for c in cases],
        "checkpoints": ckpt_rows,
        "normalization_sha256": normalization.get("sha256"),
        "dataset_sha256": dataset_sha,
        "training_summary_status": training_summary.get("status"),
        "ops": ops,
        "test_excluded": True,
        "written_before_episodes": True,
    }
    atomic_write_json(output / "evaluation_manifest.json", eval_manifest)
    atomic_write_json(
        output / "input_snapshots.json",
        {oid: {"sha256": hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()} for oid, snap in snapshots.items()},
    )
    # guardar snapshots completos por pedido
    snap_dir = output / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for oid, snap in snapshots.items():
        atomic_write_json(snap_dir / f"{oid}.json", snap)

    deadline = time.perf_counter() + wall
    started_unix = time.time()
    results_rows: list[dict[str, Any]] = []
    progress = {"status": "running", "done": 0, "total": 240, "started_unix": started_unix}
    atomic_write_json(output / "progress.json", progress)

    def _one(case: dict[str, Any]) -> dict[str, Any]:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            return {
                "key": case["key"],
                "order_id": case["order_id"],
                "arm": case["arm"],
                "seed": case["seed"],
                "status": "timeout",
                "error": "global_wall_clock",
                "method_failure": True,
                "evaluator_error": False,
                "effective_u_geom": 0.0,
                "in_denominator": True,
                "physical_stability_verified": None,
            }
        timeout = min(CASE_TIMEOUT, remaining)
        label = "greedy" if case["arm"] == "greedy" else f"{case['arm']}_seed_{case['seed']}"
        case_dir = output / "cases" / case["order_id"] / label
        ckpt = None
        if case["arm"] != "greedy":
            ckpt = str(models / f"seed_{case['seed']}" / case["arm"] / "checkpoint_epoch_40.pt")
        job = {
            "order_id": case["order_id"],
            "arm": case["arm"],
            "seed": case["seed"],
            "key": case["key"],
            "dataset": str(dataset),
            "dataset_sha256": dataset_sha,
            "checkpoint": ckpt,
            "normalization": stats,
            "input_snapshot": snapshots[case["order_id"]],
        }
        outcome = invoke_case(job, case_dir=case_dir, timeout_s=timeout)
        capture = outcome.get("capture") if isinstance(outcome.get("capture"), dict) else None
        audit = None
        contrast_ok = False
        raw_u = None
        geometry_valid = False
        if capture is not None:
            atomic_write_json(case_dir / "capture.json", capture)
            try:
                audit = _audit(capture)
                atomic_write_json(case_dir / "audit.json", audit)
                contrast = contrast_capture(
                    capture,
                    snapshots[case["order_id"]],
                    order_id=case["order_id"],
                    method=case["arm"],
                )
                atomic_write_json(case_dir / "contrast.json", contrast)
                contrast_ok = bool(contrast.get("matches"))
                geometry_valid = bool(audit.get("geometry_valid", False))
                raw_u = recompute_u(capture)
                if audit.get("u_geom") is not None and raw_u is not None:
                    if abs(float(audit["u_geom"]) - float(raw_u)) > 1e-12:
                        geometry_valid = False
            except Exception as exc:
                classified = {
                    "method_failure": False,
                    "evaluator_error": True,
                    "geometry_invalid": False,
                    "input_mismatch": False,
                    "effective_u_geom": None,
                    "raw_u_geom": None,
                    "in_denominator": False,
                    "physical_stability_verified": None,
                    "evaluator_exception": f"{type(exc).__name__}: {exc}",
                }
                atomic_write_json(case_dir / "worker.json", {k: v for k, v in outcome.items() if k != "capture"})
                atomic_write_json(case_dir / "result.json", {**case, **classified, "status": "incomplete_evaluator"})
                return {**case, **classified, "status": "incomplete_evaluator", "key": case["key"]}

        classified = classify_episode(
            status=str(outcome.get("status")),
            raw_u_geom=float(raw_u) if raw_u is not None else None,
            geometry_valid=geometry_valid,
            contrast_matches=contrast_ok,
        )
        atomic_write_json(case_dir / "worker.json", {k: v for k, v in outcome.items() if k != "capture"})
        result = {
            **case,
            **classified,
            "status": outcome.get("status"),
            "error": outcome.get("error"),
            "duration_seconds": outcome.get("duration_seconds"),
            "timings": outcome.get("timings"),
            "key": case["key"],
        }
        atomic_write_json(case_dir / "result.json", result)
        return result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_one, case): case for case in cases}
        for fut in as_completed(futures):
            row = fut.result()
            results_rows.append(row)
            progress["done"] = len(results_rows)
            if run_dir:
                write_heartbeat(
                    run_dir,
                    {
                        "pid": os.getpid(),
                        "unix": time.time(),
                        "phase": "cases",
                        "current_order_id": row.get("order_id"),
                        "n_done": progress["done"],
                    },
                )
            atomic_write_json(output / "progress.json", progress)

    wall_used = time.time() - started_unix
    # presupuesto de campaña acumulado (aproximación documentada)
    labeling_prior = 1452.6413891145087 + 702.6418765110001  # prior al 03 + wall 03
    preflight = 35.121554053999716
    training_wall = float(training_summary.get("wall_seconds") or 38.334516525268555)
    total_budget = float(protocol["budget"]["total_wall_seconds"])
    accounted = labeling_prior + preflight + training_wall + wall_used
    remaining_for_test = total_budget - accounted

    by_key = {row["key"]: row for row in results_rows}
    missing = [c["key"] for c in cases if c["key"] not in by_key]
    evaluator_errors = sum(1 for row in results_rows if row.get("evaluator_error"))
    method_failures = sum(1 for row in results_rows if row.get("method_failure"))

    status = "completed"
    if missing or len(results_rows) != 240:
        status = "incomplete"
    if evaluator_errors:
        status = "incomplete_evaluator" if status == "completed" else status

    seed_reports = []
    analysis: dict[str, Any]
    gate: dict[str, Any]
    if status == "completed" and not evaluator_errors:
        seed_reports = [seed_report(results_rows, orders, seed) for seed in SEEDS]
        order_agg = order_then_seed_aggregate(seed_reports, orders)
        gate = apply_development_gate(
            seed_reports,
            order_agg,
            evaluator_errors=evaluator_errors,
            missing_keys=len(missing),
            remaining_seconds_for_test=remaining_for_test,
            test_wall_seconds=float(protocol["budget"]["test_wall_seconds"]),
        )
        analysis = {
            "seed_reports": seed_reports,
            "order_then_seed_aggregate": order_agg,
            "seed_means_preferences_minus_classification": [
                {"seed": r["seed"], "mean": r["preferences_minus_classification"]["mean"]} for r in seed_reports
            ],
            "gate": gate,
        }
    else:
        gate = {
            "passed": False,
            "decision": "evaluacion_incompleta",
            "evaluator_errors": evaluator_errors,
            "missing_keys": len(missing),
        }
        analysis = {"gate": gate, "seed_reports": seed_reports}

    summary = {
        "status": status,
        "n_cases": len(results_rows),
        "expected_cases": 240,
        "missing_keys": missing,
        "method_failures": method_failures,
        "evaluator_errors": evaluator_errors,
        "wall_seconds": wall_used,
        "development_budget_seconds": wall,
        "campaign_accounted_wall_seconds": accounted,
        "remaining_seconds_for_test": remaining_for_test,
        "test_executed": False,
        "seed_selected": False,
        "ops": ops,
        "gate_decision": gate.get("decision"),
        "gate_passed": gate.get("passed"),
    }
    atomic_write_json(output / "evaluation_summary.json", summary)
    atomic_write_json(output / "evaluation_analysis.json", analysis)
    atomic_write_json(output / "case_results.json", results_rows)
    atomic_write_json(output / "progress.json", {**progress, "status": status, "done": len(results_rows)})

    if run_dir:
        write_state(
            run_dir,
            {
                "run_id": os.environ.get("LABELING_RUN_ID"),
                "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
                "status": "completed" if status == "completed" else "exited_nonzero",
                "exit_code": 0 if status == "completed" else 1,
                "pid": os.getpid(),
                "finished_unix": time.time(),
                "gate_decision": gate.get("decision"),
            },
        )
    print(json.dumps({"status": status, "gate": gate.get("decision"), "wall_seconds": wall_used, "output": str(output)}))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
