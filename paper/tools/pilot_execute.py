"""Orquesta el preflight y, si se pide, la corrida aislada."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from pilot_common import (
    METHODS,
    REPO_ROOT,
    TIMEOUT_SECONDS,
    PilotError,
    atomic_write_json,
    atomic_write_text,
    load_json,
)
from pilot_metrics import aggregate, build_pairs, evaluate_outcome, render_summary, secondary_summary
from pilot_preflight import preflight

WORKER_SCRIPT = Path(__file__).resolve().parent / "pilot_worker.py"
Worker = Callable[[dict[str, Any]], dict[str, Any]]


def _clip(text: Any) -> str | None:
    if text is None:
        return None
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    value = str(text).strip()
    if not value:
        return None
    return value[:2000]


def invoke_worker(
    job: dict[str, Any],
    *,
    case_dir: Path,
    timeout_s: float,
    command: list[str] | None = None,
) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    job_path = case_dir / "job.json"
    result_path = case_dir / "worker_result.partial"
    atomic_write_json(job_path, job)
    cmd = command or [sys.executable, str(WORKER_SCRIPT), "--job", str(job_path), "--result", str(result_path)]
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ""
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if result_path.exists():
            result_path.unlink()
        return {
            "status": "timeout",
            "error": f"timeout de {timeout_s} segundos",
            "attempts": 1,
            "duration_seconds": time.perf_counter() - started,
            "stderr": _clip(exc.stderr),
            "capture": None,
        }
    wall = time.perf_counter() - started
    if result_path.is_file():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        result_path.unlink()
        if isinstance(payload, dict):
            payload["wall_seconds"] = wall
            payload["duration_seconds"] = wall
            return payload
    return {
        "status": "crash",
        "error": f"el worker terminó con código {completed.returncode}",
        "attempts": 1,
        "duration_seconds": wall,
        "stderr": _clip(completed.stderr) or _clip(completed.stdout),
        "capture": None,
    }


def _public_preflight(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "checkpoint_loaded": False,
        "workers_started": False,
        "equivalent_configs": True,
        "amendment": report["amendment"],
        "n_orders": report["n_orders"],
        "files": report["files"],
        "provenance": report["provenance"],
        "orders": report["orders"],
    }


def _write_incomplete(output_dir: Path, manifest: dict[str, Any], status: str, errors: list[str]) -> None:
    manifest["status"] = status
    manifest["complete"] = False
    manifest["errors"] = errors
    atomic_write_json(output_dir / "manifest.json", manifest)
    summary = {
        "status": status,
        "complete": False,
        "run_id": manifest["run_id"],
        "errors": errors,
        "mean_delta": None,
        "physical_stability_verified": None,
        "time_is_diagnostic_only": True,
    }
    atomic_write_json(output_dir / "summary.json", summary)
    atomic_write_text_summary(output_dir / "summary.md", render_summary(summary))


def atomic_write_text_summary(path: Path, text: str) -> None:
    atomic_write_text(path, text)


def execute_pilot(
    *,
    protocol_path: Path,
    dataset_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    preflight_only: bool = False,
    manifest_path: Path | None = None,
    subset_path: Path | None = None,
    worker: Worker | None = None,
    timeout_s: float = TIMEOUT_SECONDS,
) -> dict[str, Any]:
    output_dir = output_dir.expanduser().resolve()
    if preflight_only:
        report = preflight(
            protocol_path=protocol_path,
            dataset_path=dataset_path,
            checkpoint_path=checkpoint_path,
            manifest_path=manifest_path,
            subset_path=subset_path,
        )
        return {"public": _public_preflight(report)}
    if output_dir.exists():
        raise PilotError("el directorio de ejecución ya existe", code="output_exists")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(exist_ok=False)
    run_id = secrets.token_hex(8)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "running",
        "complete": False,
        "pilot_executed_on_protocol": False,
        "timeout_seconds": timeout_s,
        "attempts_per_case": 1,
        "device": "cpu",
        "method_order": list(METHODS),
        "arguments": {
            "protocol": str(protocol_path.expanduser().resolve()),
            "dataset": str(dataset_path.expanduser().resolve()),
            "checkpoint": str(checkpoint_path.expanduser().resolve()),
            "output_dir": str(output_dir),
        },
    }
    atomic_write_json(output_dir / "manifest.json", manifest)
    try:
        report = preflight(
            protocol_path=protocol_path,
            dataset_path=dataset_path,
            checkpoint_path=checkpoint_path,
            manifest_path=manifest_path,
            subset_path=subset_path,
        )
    except PilotError as exc:
        _write_incomplete(output_dir, manifest, "preflight_failed", list(exc.details.get("errors") or [str(exc)]))
        raise
    manifest["preflight"] = _public_preflight(report)
    manifest["provenance"] = report["provenance"]
    atomic_write_json(output_dir / "manifest.json", manifest)
    protocol = load_json(protocol_path.expanduser().resolve())
    rows: list[dict[str, Any]] = []
    audits: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        _run_cases(
            protocol=protocol,
            report=report,
            dataset_path=dataset_path,
            checkpoint_path=checkpoint_path,
            output_dir=output_dir,
            run_id=run_id,
            timeout_s=timeout_s,
            worker=worker,
            rows=rows,
            audits=audits,
        )
    except PilotError:
        raise
    except Exception as exc:
        _write_incomplete(output_dir, manifest, "incomplete", [f"{type(exc).__name__}: {exc}"])
        raise PilotError("corrida incompleta", code="incomplete") from exc
    return _finalize(output_dir, manifest, protocol, rows, run_id)


def _run_cases(
    *,
    protocol: dict[str, Any],
    report: dict[str, Any],
    dataset_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    run_id: str,
    timeout_s: float,
    worker: Worker | None,
    rows: list[dict[str, Any]],
    audits: dict[tuple[str, str], dict[str, Any]],
) -> None:
    for item in protocol["orders"]["items"]:
        for method in METHODS:
            case_dir = output_dir / "cases" / item["order_id"] / method
            case_dir.mkdir(parents=True, exist_ok=True)
            snapshot = report["snapshots"][item["order_id"]][method]
            atomic_write_json(case_dir / "input.json", snapshot)
            job = {
                "run_id": run_id,
                "method": method,
                "order_id": item["order_id"],
                "dataset": str(dataset_path.expanduser().resolve()),
                "checkpoint": str(checkpoint_path.expanduser().resolve()),
                "lookahead_p": report["lookahead_p"],
                "select_s": report["select_s"],
                "attempts": 1,
            }
            if worker is None:
                outcome = invoke_worker(job, case_dir=case_dir, timeout_s=timeout_s)
            else:
                try:
                    outcome = worker(job)
                except subprocess.TimeoutExpired:
                    outcome = {
                        "status": "timeout",
                        "error": f"timeout de {timeout_s} segundos",
                        "attempts": 1,
                        "duration_seconds": float(timeout_s),
                        "capture": None,
                    }
                except Exception as exc:
                    outcome = {
                        "status": "crash",
                        "error": f"{type(exc).__name__}: {exc}",
                        "attempts": 1,
                        "duration_seconds": None,
                        "capture": None,
                    }
            row = evaluate_outcome(
                outcome,
                order_id=item["order_id"],
                method=method,
                target=item["target"],
                container_volume_mm3=float(item["container_volume_mm3"]),
                run_id=run_id,
            )
            audits[(item["order_id"], method)] = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
            atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
            if isinstance(outcome.get("capture"), dict):
                atomic_write_json(case_dir / "capture.json", outcome["capture"])
            atomic_write_json(case_dir / "audit.json", audits[(item["order_id"], method)])
            atomic_write_json(case_dir / "row.json", row)
            rows.append(row)


def _finalize(
    output_dir: Path,
    manifest: dict[str, Any],
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
    run_id: str,
) -> dict[str, Any]:
    if len(rows) != protocol["orders"]["n"] * len(METHODS):
        _write_incomplete(output_dir, manifest, "incomplete", ["la corrida no produjo las filas esperadas"])
        raise PilotError("corrida incompleta", code="incomplete")
    pairs = build_pairs(rows)
    stats = aggregate(pairs)
    if stats["n"] != protocol["orders"]["n"]:
        _write_incomplete(output_dir, manifest, "incomplete", ["el número de pares no es el del protocolo"])
        raise PilotError("corrida incompleta", code="incomplete")
    results = {"schema_version": 1, "complete": True, "run_id": run_id, "n_rows": len(rows), "rows": rows}
    paired = {"schema_version": 1, "complete": True, "run_id": run_id, "n_pairs": len(pairs), "pairs": pairs}
    summary = {
        "schema_version": 1,
        "status": "complete",
        "complete": True,
        "run_id": run_id,
        "protocol_pilot_executed": False,
        "time_is_diagnostic_only": True,
        "physical_stability_verified": None,
        "secondary": secondary_summary(rows),
        **stats,
    }
    atomic_write_json(output_dir / "results.json", results)
    atomic_write_json(output_dir / "paired_results.json", paired)
    atomic_write_json(output_dir / "summary.json", summary)
    atomic_write_text_summary(output_dir / "summary.md", render_summary(summary))
    manifest["status"] = "complete"
    manifest["complete"] = True
    manifest["n_rows"] = len(rows)
    manifest["n_pairs"] = len(pairs)
    atomic_write_json(output_dir / "manifest.json", manifest)
    return {
        "public": {
            "ok": True,
            "status": "complete",
            "run_id": run_id,
            "output_dir": str(output_dir),
            "n_rows": len(rows),
            "n_pairs": len(pairs),
            "mean_delta": stats["mean_delta"],
            "checkpoint_loaded_by_preflight": False,
            "workers_started": True,
        }
    }
