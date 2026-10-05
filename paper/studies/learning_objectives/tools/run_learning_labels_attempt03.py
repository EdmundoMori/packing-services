#!/usr/bin/env python3
"""Worker real del intento 03: cableado a labeling_runctl.

Valida hashes/fuentes antes de packing; referencia 46 content-verified;
ejecuta únicamente los 26 pendientes; hereda presupuesto acumulado;
escribe heartbeat/pedido actual; cierra con estado y código de salida.

La salida del proceso NO equivale a campaña completa: la completitud
depende de verificación independiente (verify_labeling_output).
SIGKILL y caída del host pueden impedir un cierre normal.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_campaign_safe import run_attempt03_recovery  # noqa: E402
from labeling_contracts import static_preflight  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
from labeling_reuse import PreflightReuseIndex  # noqa: E402
from labeling_runctl import write_heartbeat, write_state  # noqa: E402
from labeling_verify import verify_labeling_output  # noqa: E402


def _run_dir() -> Path | None:
    raw = os.environ.get("LABELING_RUN_DIR")
    return Path(raw) if raw else None


def _close_state(*, status: str, exit_code: int, extra: dict[str, Any] | None = None) -> None:
    run_dir = _run_dir()
    if not run_dir:
        return
    payload = {
        "run_id": os.environ.get("LABELING_RUN_ID"),
        "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
        "status": status,
        "exit_code": exit_code,
        "pid": os.getpid(),
        "finished_unix": time.time(),
        "process_exit_is_not_campaign_complete": True,
    }
    if extra:
        payload.update(extra)
    write_state(run_dir, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Intento 03 de recuperación persistente")
    p.add_argument("--study-dir", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--mock-packing",
        action="store_true",
        help="Solo pruebas de integración: sustituye packing por artefactos sintéticos auditables",
    )
    return p.parse_args(argv)


def _mock_pack_order(
    orders_blob: dict[str, Any],
    spec: dict[str, Any],
    *,
    dataset: str,
    dataset_sha256: str,
    output_order_dir: Path,
    budget: Any,
    reuse: Any,
    deadline: float,
    now: Any,
) -> dict[str, Any]:
    """Packing sintético: escribe estados/capturas válidos; el auditor real sigue aplicándose."""

    del orders_blob, dataset, dataset_sha256, budget, reuse, deadline, now
    if spec["split"] == "test":
        raise RuntimeError("bloqueo: test en intento 03")
    output_order_dir.mkdir(parents=True, exist_ok=True)
    states_dir = output_order_dir / "states" / "choice_0"
    states_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "choice_index": 0,
        "support_contract": "greedy_plus_orientation_position_diversity_v1",
        "greedy_in_support": True,
        "support_ids": [[0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]],
        "n_support": 1,
        "alternatives": [
            {
                "action": [0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "q_hat": 0.5,
                "recomputed_u_geom": 0.5,
                "capture_saved": True,
                "is_greedy": True,
                "source": "mock_packing_integration",
            }
        ],
        "complete": True,
        "eligible_for_learning": True,
    }
    atomic_write_json(states_dir / "state.json", state)
    atomic_write_json(states_dir / "alt_0_capture.json", {"packed": True, "mock": True}, indent=None)
    result = {
        "order_id": spec["order_id"],
        "split": spec["split"],
        "target": spec["target"],
        "selection_hash": spec["selection_hash"],
        "signature": spec["signature"],
        "status": "ok",
        "selected_indices": [0],
        "states": [state],
        "n_states": 1,
        "wall_seconds": 0.01,
        "mock_packing": True,
    }
    atomic_write_json(output_order_dir / "result.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    plan_path = args.plan.resolve()
    output = args.output.resolve()
    run_dir = _run_dir()

    stop = {"flag": False, "signal": None}

    def _on_signal(signum, _frame):  # noqa: ANN001
        stop["flag"] = True
        stop["signal"] = int(signum)
        if run_dir:
            write_state(
                run_dir,
                {
                    "run_id": os.environ.get("LABELING_RUN_ID"),
                    "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
                    "status": "interrupted_signal",
                    "signal": int(signum),
                    "pid": os.getpid(),
                },
            )

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    if output.exists() and any(output.iterdir()):
        msg = {"status": "refused", "reason": "output_exists", "path": str(output)}
        print(json.dumps(msg, ensure_ascii=False))
        _close_state(status="refused_output_exists", exit_code=2, extra=msg)
        return 2

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("kind") != "attempt_03_plan":
        print(json.dumps({"status": "refused", "reason": "bad_plan_kind"}))
        _close_state(status="refused_bad_plan", exit_code=2)
        return 2

    if run_dir:
        write_heartbeat(
            run_dir,
            {
                "pid": os.getpid(),
                "unix": time.time(),
                "phase": "preflight",
                "current_order_id": None,
            },
        )

    # Hashes y fuentes antes de packing (static_preflight)
    static = static_preflight(study_dir=study_dir, output=output, preflight_dir=study_dir / "preflight")
    protocol = static["protocol"]
    reuse = PreflightReuseIndex(static["preflight_dir"], protocol=protocol, study_dir=study_dir)
    dataset = Path(static["contracts"]["dataset"])
    orders_blob = json.loads(dataset.read_text(encoding="utf-8"))

    # Filtrar ordered al universo del plan (manifiesto: train+dev; excluye test)
    plan_reusable = set(plan["reusable_content_verified_order_ids"])
    by_id = {row["order_id"]: row for row in static["ordered"]}
    ordered_exec = [row for row in static["ordered"] if row["order_id"] in plan_reusable]
    pending_ordered = []
    for oid in plan["pending_in_manifest_order"]:
        if oid not in by_id:
            print(json.dumps({"status": "refused", "reason": "pending_not_in_manifest", "order_id": oid}))
            _close_state(status="refused_pending_missing", exit_code=2)
            return 2
        pending_ordered.append(by_id[oid])
    ordered_final = ordered_exec + pending_ordered

    source_dir = Path(plan["source_attempt_02_dir"]).resolve()
    if args.mock_packing:
        # En fixture de integración, source_attempt_02_dir puede ser relativo al plan
        source_dir = Path(plan["source_attempt_02_dir"])
        if not source_dir.is_absolute():
            source_dir = (plan_path.parent / source_dir).resolve()

    label_fn = _mock_pack_order if args.mock_packing else None
    summary = run_attempt03_recovery(
        protocol=protocol,
        ordered=ordered_final,
        orders_blob=orders_blob,
        dataset=str(dataset),
        dataset_sha256=static["contracts"]["dataset_sha256"],
        output=output,
        reuse=reuse,
        plan=plan,
        source_attempt02_dir=source_dir,
        execution_manifest=static["manifest"],
        label_order_fn=label_fn,
    )

    if args.mock_packing:
        # Integración: auditor real por pedido; no exige cobertura completa del protocolo.
        from labeling_integrity import verify_order_artifacts

        issues: list[str] = []
        for row in ordered_final:
            check = verify_order_artifacts(output / "orders" / row["order_id"], expected=row)
            if check["classification"] != "reusable_valid":
                issues.append(f"{row['order_id']}:{check['classification']}:{check['issues']}")
        if any(row["split"] == "test" for row in ordered_final):
            issues.append("test_in_plan")
        verification = {
            "status": "verified_integration" if not issues and summary.get("status") == "completed" else "issues_found",
            "issues": issues,
            "mock_packing": True,
            "process_exit_is_not_campaign_complete": True,
            "ready_for_training": False,
            "test_executed": False,
            "prior_wall_accounted_seconds": summary.get("prior_wall_accounted_seconds"),
        }
        atomic_write_json(output / "labeling_verification.json", verification)
        ok = summary.get("status") == "completed" and verification["status"] == "verified_integration"
    else:
        verification = verify_labeling_output(
            output=output,
            manifest=static["manifest"],
            summary=summary,
            protocol=protocol,
        )
        ok = summary.get("status") == "completed" and verification.get("status") == "verified"

    atomic_write_json(
        output / "attempt03_worker_report.json",
        {
            "summary_status": summary.get("status"),
            "verification_status": verification.get("status"),
            "ready_for_training": verification.get("ready_for_training"),
            "process_exit_is_not_campaign_complete": True,
            "mock_packing": bool(args.mock_packing),
            "prior_wall_accounted_seconds": summary.get("prior_wall_accounted_seconds"),
            "n_referenced": len(summary.get("referenced_order_ids") or []),
            "n_newly_executed": len(summary.get("newly_executed_order_ids") or []),
            "test_executed": False,
        },
    )

    exit_code = 0 if ok else 1
    _close_state(
        status="completed" if ok else "exited_nonzero",
        exit_code=exit_code,
        extra={
            "summary_status": summary.get("status"),
            "verification_status": verification.get("status"),
            "campaign_complete_requires_independent_verification": True,
        },
    )
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "verification": verification.get("status"),
                "exit_code": exit_code,
                "output": str(output),
                "n_referenced": len(summary.get("referenced_order_ids") or []),
                "n_newly_executed": len(summary.get("newly_executed_order_ids") or []),
                "process_exit_is_not_campaign_complete": True,
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
