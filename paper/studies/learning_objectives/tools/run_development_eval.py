#!/usr/bin/env python3
"""Evaluación de development: Greedy + actores bajo contrato S.

No abre test. Máximo 2 workers. Cupo development 3600 s (no se reinicia).
El intérprete de workers usa Path.absolute() sobre .venv/bin/python (no resolve).
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
    evaluation_integrity,
    filter_cases,
    looks_like_harness_failure,
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
from worker_env import environment_preflight, preserve_executable, venv_python  # noqa: E402

DEVELOPMENT_WALL = 3600.0
CASE_TIMEOUT = 300.0
MAX_WORKERS = 2
WORKER = HERE / "episode_worker.py"
FAILED_DEV_WALL = 22.538368225097656  # intento 240/240 crash; no reiniciar reloj


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


def first_development_order_per_target(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Primer pedido development de cada target según orden del manifiesto."""

    seen: dict[str, dict[str, Any]] = {}
    for row in orders:
        if row["target"] not in seen:
            seen[row["target"]] = row
    # preserve manifest encounter order
    out = []
    for row in orders:
        if seen.get(row["target"]) is row:
            out.append(row)
    return out


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
    del normalization
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
    python: str,
) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    job_path = case_dir / "job.json"
    result_path = case_dir / "worker_result.partial"
    atomic_write_json(job_path, job)
    atomic_write_json(case_dir / "input.json", job.get("input_snapshot") or {})
    cmd = [
        preserve_executable(python),
        "-u",
        str(WORKER.absolute()),
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
            "failure_class": "method",
            "attempts": 1,
            "duration_seconds": time.perf_counter() - started,
            "stderr": (exc.stderr or "")[:2000] if isinstance(exc.stderr, str) else None,
            "capture": None,
            "invoked_python": preserve_executable(python),
        }
    wall = time.perf_counter() - started
    payload = None
    if result_path.is_file() and result_path.stat().st_size > 0:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        result_path.unlink()
    if payload is None:
        stderr = (completed.stderr or "")[:2000]
        harness = looks_like_harness_failure(f"sin resultado worker rc={completed.returncode}", stderr)
        return {
            "status": "crash",
            "error": f"sin resultado worker rc={completed.returncode}",
            "worker_failure": "crash",
            "failure_class": "harness" if harness else "method",
            "attempts": 1,
            "duration_seconds": wall,
            "stderr": stderr,
            "capture": None,
            "invoked_python": preserve_executable(python),
        }
    payload["duration_seconds"] = wall
    payload["attempts"] = 1
    payload["invoked_python"] = preserve_executable(python)
    if payload.get("status") != "ok" and looks_like_harness_failure(payload.get("error"), None):
        payload["failure_class"] = "harness"
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--study-dir", type=Path, required=True)
    p.add_argument("--models-dir", type=Path, required=True)
    p.add_argument("--labels-output", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--wall-seconds", type=float, default=None)
    p.add_argument(
        "--prior-development-wall-seconds",
        type=float,
        default=FAILED_DEV_WALL,
        help="Tiempo ya consumido del cupo development (intento fallido inclusive).",
    )
    p.add_argument("--smoke-first-target-orders", action="store_true")
    p.add_argument("--only-seeds", type=str, default=None, help="p.ej. 11")
    p.add_argument("--only-arms", type=str, default=None, help="greedy,classification,...")
    p.add_argument("--only-order-ids", type=str, default=None, help="comma-separated")
    p.add_argument(
        "--reuse-from",
        type=Path,
        default=None,
        help="Directorio de smoke auditado cuyas claves se integran una sola vez (sin relanzar).",
    )
    p.add_argument("--skip-checkpoint-validation", action="store_true")
    return p.parse_args(argv)


def _case_label(arm: str, seed: int | None) -> str:
    return "greedy" if arm == "greedy" else f"{arm}_seed_{seed}"


def integrate_smoke_reuse(
    *,
    reuse_dir: Path,
    output: Path,
    models: Path,
    normalization: dict[str, Any],
    dataset_sha: str,
    snapshots: dict[str, Any],
    ckpt_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Copia y valida claves smoke. Devuelve (filas_reutilizadas, claves)."""

    reuse_dir = reuse_dir.resolve()
    rows = json.loads((reuse_dir / "case_results.json").read_text(encoding="utf-8"))
    smoke_man = json.loads((reuse_dir / "evaluation_manifest.json").read_text(encoding="utf-8"))
    if smoke_man.get("normalization_sha256") != normalization.get("sha256"):
        raise RuntimeError("normalización smoke incompatible")
    if smoke_man.get("dataset_sha256") != dataset_sha:
        raise RuntimeError("dataset smoke incompatible")
    ckpt_by = {(c["arm"], int(c["seed"])): c["sha256"] for c in ckpt_rows}
    smoke_ckpt = {(c["arm"], int(c["seed"])): c["sha256"] for c in (smoke_man.get("checkpoints") or [])}
    if ckpt_by and smoke_ckpt and ckpt_by != smoke_ckpt:
        raise RuntimeError("checkpoints smoke incompatibles con modelos actuales")

    out_rows: list[dict[str, Any]] = []
    keys: list[str] = []
    for row in rows:
        key = row["key"]
        if key in keys:
            raise RuntimeError(f"clave smoke duplicada: {key}")
        label = _case_label(row["arm"], row["seed"])
        src = reuse_dir / "cases" / row["order_id"] / label
        dst = output / "cases" / row["order_id"] / label
        if not (src / "capture.json").is_file() or not (src / "audit.json").is_file():
            raise RuntimeError(f"smoke sin captura/auditoría: {key}")
        capture = json.loads((src / "capture.json").read_text(encoding="utf-8"))
        audit = json.loads((src / "audit.json").read_text(encoding="utf-8"))
        contrast = json.loads((src / "contrast.json").read_text(encoding="utf-8"))
        u = recompute_u(capture)
        if u is None or abs(float(u) - float(row["effective_u_geom"])) > 1e-15:
            raise RuntimeError(f"U_geom smoke no recompuesto: {key} {u} vs {row.get('effective_u_geom')}")
        if not audit.get("internal_geometry_valid"):
            raise RuntimeError(f"geometría smoke inválida: {key}")
        if not contrast.get("matches"):
            raise RuntimeError(f"contraste smoke fallido: {key}")
        # snapshot de entrada equivalente al de esta campaña
        snap_sha = hashlib.sha256(json.dumps(snapshots[row["order_id"]], sort_keys=True).encode()).hexdigest()
        smoke_snap_index = json.loads((reuse_dir / "input_snapshots.json").read_text(encoding="utf-8"))
        if smoke_snap_index.get(row["order_id"], {}).get("sha256") != snap_sha:
            raise RuntimeError(f"snapshot de entrada distinto para {row['order_id']}")
        # recipiente S / greedy
        recipe = capture.get("recipe") or {}
        if row["arm"] == "greedy":
            if recipe.get("scores_all_legal_candidates") is not True:
                raise RuntimeError(f"greedy smoke no puntuó lista legal: {key}")
        else:
            if recipe.get("support_constrained") is not True:
                raise RuntimeError(f"actor smoke no limitado a S: {key}")
            ckpt_path = models / f"seed_{row['seed']}" / row["arm"] / "checkpoint_epoch_40.pt"
            if file_sha256(ckpt_path) != ckpt_by[(row["arm"], int(row["seed"]))]:
                raise RuntimeError(f"hash modelo distinto al validado: {key}")
        # copiar artefactos sin modificar
        import shutil

        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise RuntimeError(f"destino reuse ya existe: {dst}")
        shutil.copytree(src, dst)
        integrated = {
            **row,
            "reused_from_smoke": True,
            "smoke_run_id": "dev_smoke_ee9e0ec854c3_20261005T173933Z",
            "audited": True,
            "physical_stability_verified": None,
        }
        atomic_write_json(dst / "result.json", integrated)
        out_rows.append(integrated)
        keys.append(key)
    if len(keys) != 8:
        raise RuntimeError(f"se esperaban 8 claves smoke, got {len(keys)}")
    return out_rows, keys


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study = args.study_dir.resolve()
    models = args.models_dir.resolve()
    labels = args.labels_output.resolve()
    output = args.output.resolve()
    prior_dev = float(args.prior_development_wall_seconds)
    remaining_cup = DEVELOPMENT_WALL - prior_dev
    if remaining_cup <= 0:
        print(json.dumps({"status": "refused", "reason": "development_cup_exhausted", "prior": prior_dev}))
        return 2
    wall = float(args.wall_seconds) if args.wall_seconds is not None else remaining_cup
    if wall > remaining_cup + 1e-9:
        print(json.dumps({"status": "refused", "reason": "wall_exceeds_remaining_development_cup", "remaining": remaining_cup}))
        return 2
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

    # Preflight de entorno ANTES de crear casos / cuadrícula
    preflight = environment_preflight(REPO, require_actor_imports=True)
    if not preflight.get("ok"):
        output.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output / "environment_preflight.json", preflight)
        atomic_write_json(
            output / "evaluation_summary.json",
            {
                "status": "harness_preflight_failed",
                "harness_failure": True,
                "gate_applicable": False,
                "gate_decision": "evaluacion_incompleta_por_fallo_del_arnes",
                "n_cases": 0,
                "expected_cases": 0,
                "preflight": preflight,
                "prior_development_wall_seconds": prior_dev,
                "test_executed": False,
            },
        )
        print(json.dumps({"status": "harness_preflight_failed", "reason": preflight.get("reason")}))
        return 3

    python = str(venv_python(REPO))
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
    ckpt_rows = [] if args.skip_checkpoint_validation else validate_checkpoints(models, normalization)
    cases = planned_cases(orders)

    order_ids = None
    arms = None
    seeds = None
    if args.smoke_first_target_orders:
        smoke_orders = first_development_order_per_target(orders)
        order_ids = {o["order_id"] for o in smoke_orders}
        arms = {"greedy", *ARMS}
        seeds = {11}
        orders = smoke_orders
    if args.only_order_ids:
        order_ids = {x.strip() for x in args.only_order_ids.split(",") if x.strip()}
        orders = [o for o in orders if o["order_id"] in order_ids]
    if args.only_arms:
        arms = {x.strip() for x in args.only_arms.split(",") if x.strip()}
    if args.only_seeds:
        seeds = {int(x.strip()) for x in args.only_seeds.split(",") if x.strip()}
    if order_ids is not None or arms is not None or seeds is not None:
        # planned_cases over filtered orders when order filter set via smoke
        base = planned_cases(orders) if (args.smoke_first_target_orders or args.only_order_ids) else cases
        cases = filter_cases(base, order_ids=order_ids, arms=arms, seeds=seeds)

    all_planned = list(cases)
    expected = len(all_planned)
    if expected == 0:
        print(json.dumps({"status": "refused", "reason": "no_cases"}))
        return 2

    prepare_imports()
    from splits import load_orders

    orders_blob = load_orders(dataset)
    # snapshots para todos los pedidos del plan (desarrollo completo o smoke)
    snap_orders = development_orders(manifest) if args.reuse_from else orders
    if args.reuse_from and not (args.smoke_first_target_orders or args.only_order_ids):
        orders = snap_orders
        all_planned = planned_cases(orders)
        expected = len(all_planned)
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
        "development_wall_seconds_cup": DEVELOPMENT_WALL,
        "prior_development_wall_seconds": prior_dev,
        "this_run_wall_seconds_limit": wall,
        "recorded_before_launch": True,
        "decision_fixed": True,
        "worker_python": python,
        "worker_python_uses_absolute_not_resolve": True,
    }
    output.mkdir(parents=True, exist_ok=True)

    reused_rows: list[dict[str, Any]] = []
    reused_keys: list[str] = []
    if args.reuse_from:
        reused_rows, reused_keys = integrate_smoke_reuse(
            reuse_dir=args.reuse_from,
            output=output,
            models=models,
            normalization=normalization,
            dataset_sha=dataset_sha,
            snapshots=snapshots,
            ckpt_rows=ckpt_rows,
        )
        cases = [c for c in all_planned if c["key"] not in set(reused_keys)]
        if len(reused_keys) + len(cases) != expected:
            raise RuntimeError("plan reuse inconsistente")
    else:
        cases = all_planned

    atomic_write_json(output / "environment_preflight.json", preflight)
    atomic_write_json(output / "operational_decision.json", ops)
    eval_manifest = {
        "kind": "development_evaluation_manifest",
        "n_cases": expected,
        "n_orders": len(orders),
        "n_reused": len(reused_keys),
        "n_new": len(cases),
        "reused_keys": reused_keys,
        "orders": orders,
        "cases": [{"key": c["key"], "order_id": c["order_id"], "arm": c["arm"], "seed": c["seed"]} for c in all_planned],
        "cases_to_execute": [{"key": c["key"], "order_id": c["order_id"], "arm": c["arm"], "seed": c["seed"]} for c in cases],
        "checkpoints": ckpt_rows,
        "normalization_sha256": normalization.get("sha256"),
        "dataset_sha256": dataset_sha,
        "training_summary_status": training_summary.get("status"),
        "ops": ops,
        "test_excluded": True,
        "written_before_episodes": True,
        "smoke": bool(args.smoke_first_target_orders),
        "reuse_from": str(args.reuse_from.resolve()) if args.reuse_from else None,
        "evaluator_sha256": file_sha256(Path(__file__)),
        "worker_sha256": file_sha256(WORKER),
        "worker_env_sha256": file_sha256(HERE / "worker_env.py"),
    }
    atomic_write_json(output / "evaluation_manifest.json", eval_manifest)
    atomic_write_json(
        output / "input_snapshots.json",
        {oid: {"sha256": hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()} for oid, snap in snapshots.items()},
    )
    snap_dir = output / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for oid, snap in snapshots.items():
        atomic_write_json(snap_dir / f"{oid}.json", snap)

    deadline = time.perf_counter() + wall
    started_unix = time.time()
    results_rows: list[dict[str, Any]] = list(reused_rows)
    progress = {
        "status": "running",
        "done": len(reused_rows),
        "total": expected,
        "reused": len(reused_rows),
        "new_pending": len(cases),
        "started_unix": started_unix,
    }
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
                "harness_failure": False,
                "evaluator_error": False,
                "effective_u_geom": 0.0,
                "in_denominator": True,
                "physical_stability_verified": None,
                "failure_class": "method",
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
        outcome = invoke_case(job, case_dir=case_dir, timeout_s=timeout, python=python)
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
                geometry_valid = bool(audit.get("internal_geometry_valid", False))
                raw_u = recompute_u(capture)
                # El auditor no publica u_geom; la fuente de U es recompute_u sobre la captura.
            except Exception as exc:
                classified = {
                    "method_failure": False,
                    "harness_failure": False,
                    "evaluator_error": True,
                    "geometry_invalid": False,
                    "input_mismatch": False,
                    "effective_u_geom": None,
                    "raw_u_geom": None,
                    "in_denominator": False,
                    "physical_stability_verified": None,
                    "failure_class": "evaluator",
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
            error=outcome.get("error"),
            stderr=outcome.get("stderr"),
            failure_class=outcome.get("failure_class"),
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
            "audited": audit is not None and not classified.get("evaluator_error") and capture is not None,
            "invoked_python": outcome.get("invoked_python"),
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
    labeling_prior = 1452.6413891145087 + 702.6418765110001
    preflight_once = 35.121554053999716
    training_wall = float(training_summary.get("wall_seconds") or 38.334516525268555)
    total_budget = float(protocol["budget"]["total_wall_seconds"])
    # prior_dev already includes failed full attempt; this_run adds smoke/full
    accounted = labeling_prior + preflight_once + training_wall + prior_dev + wall_used
    remaining_for_test = total_budget - accounted

    by_key = {row["key"]: row for row in results_rows}
    missing = [c["key"] for c in all_planned if c["key"] not in by_key]
    evaluator_errors = sum(1 for row in results_rows if row.get("evaluator_error"))
    method_failures = sum(1 for row in results_rows if row.get("method_failure"))
    harness_failures = sum(1 for row in results_rows if row.get("harness_failure"))
    n_ok = sum(1 for row in results_rows if row.get("status") == "ok" and not row.get("evaluator_error"))
    n_audited = sum(1 for row in results_rows if row.get("audited"))
    n_reused = sum(1 for row in results_rows if row.get("reused_from_smoke"))

    integrity = evaluation_integrity(
        n_keys_received=len(results_rows),
        expected_keys=expected,
        n_episodes_executed=n_ok,
        n_audited_captures=n_audited,
        method_failures=method_failures,
        harness_failures=harness_failures,
        evaluator_errors=evaluator_errors,
        harness_preflight_ok=True,
    )

    status = "completed"
    if missing or len(results_rows) != expected:
        status = "incomplete"
    if harness_failures or evaluator_errors:
        status = "incomplete" if status == "completed" else status
    if not integrity["scientifically_valid"]:
        if status == "completed":
            status = "completed_keys_but_not_scientifically_valid"

    seed_reports: list[dict[str, Any]] = []
    analysis: dict[str, Any]
    if integrity["gate_applicable"] and expected >= 240:
        seed_reports = [seed_report(results_rows, orders, seed) for seed in SEEDS]
        order_agg = order_then_seed_aggregate(seed_reports, orders)
        gate = apply_development_gate(
            seed_reports,
            order_agg,
            evaluator_errors=evaluator_errors,
            missing_keys=len(missing),
            remaining_seconds_for_test=remaining_for_test,
            test_wall_seconds=float(protocol["budget"]["test_wall_seconds"]),
            integrity=integrity,
        )
        analysis = {
            "seed_reports": seed_reports,
            "order_then_seed_aggregate": order_agg,
            "gate": gate,
            "integrity": integrity,
        }
    else:
        gate = apply_development_gate(
            [],
            {
                "preferences_minus_classification": {
                    "mean": 0.0,
                    "by_target": {"euro-pallet": {"mean": 0.0}, "rollcontainer": {"mean": 0.0}},
                }
            },
            evaluator_errors=evaluator_errors,
            missing_keys=len(missing),
            remaining_seconds_for_test=remaining_for_test,
            test_wall_seconds=float(protocol["budget"]["test_wall_seconds"]),
            integrity={**integrity, "gate_applicable": False},
        )
        analysis = {"gate": gate, "integrity": integrity, "smoke_or_invalid": True}

    summary = {
        "status": status,
        "n_cases": len(results_rows),
        "expected_cases": expected,
        "n_reused_from_smoke": n_reused,
        "n_newly_executed": len(results_rows) - n_reused,
        "reused_keys": reused_keys,
        "missing_keys": missing,
        "method_failures": method_failures,
        "harness_failures": harness_failures,
        "evaluator_errors": evaluator_errors,
        "episodes_ok": n_ok,
        "captures_audited": n_audited,
        "integrity": integrity,
        "wall_seconds": wall_used,
        "prior_development_wall_seconds": prior_dev,
        "development_cup_seconds": DEVELOPMENT_WALL,
        "development_cup_remaining_after_run": DEVELOPMENT_WALL - prior_dev - wall_used,
        "campaign_accounted_wall_seconds": accounted,
        "remaining_seconds_for_test": remaining_for_test,
        "test_executed": False,
        "seed_selected": False,
        "ops": ops,
        "gate_decision": gate.get("decision"),
        "gate_passed": gate.get("passed"),
        "gate_applicable": gate.get("gate_applicable"),
        "environment_preflight_ok": True,
        "worker_python": python,
        "failed_240_crash_attempt_excluded_from_packing": True,
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
                "status": "completed" if integrity.get("scientifically_valid") or (expected < 240 and harness_failures == 0 and not missing) else "exited_nonzero",
                "exit_code": 0 if harness_failures == 0 and not missing else 1,
                "pid": os.getpid(),
                "finished_unix": time.time(),
                "gate_decision": gate.get("decision"),
            },
        )
    print(
        json.dumps(
            {
                "status": status,
                "gate": gate.get("decision"),
                "gate_applicable": gate.get("gate_applicable"),
                "wall_seconds": wall_used,
                "n_cases": len(results_rows),
                "audited": n_audited,
                "output": str(output),
            }
        )
    )
    if harness_failures:
        return 3
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
