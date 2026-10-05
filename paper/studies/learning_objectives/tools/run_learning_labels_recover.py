"""CLI de recuperación: plan por defecto; ejecución con --execute-recovery.

El rechazo previo de --execute-recovery fue deliberado (paso solo-plan):
la capa safe existía parcialmente, pero este binario no cableaba la ejecución.
Ahora --execute-recovery ejecuta el intento 02 según el plan.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_campaign_safe import run_recovery_attempt  # noqa: E402
from labeling_contracts import static_preflight  # noqa: E402
from labeling_recovery import build_recovery_plan, write_recovery_plan  # noqa: E402
from labeling_reuse import PreflightReuseIndex  # noqa: E402
from labeling_verify import verify_labeling_output  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan o recuperación de etiquetado learning_objectives")
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--interrupted", type=Path, required=True)
    parser.add_argument("--recovery-output", type=Path, required=True)
    parser.add_argument(
        "--write-plan-only",
        action="store_true",
        help="Solo escribe/actualiza el plan (sin packing).",
    )
    parser.add_argument(
        "--execute-recovery",
        action="store_true",
        help="Ejecuta el intento 02 de recuperación según el plan.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    interrupted = args.interrupted.resolve()
    recovery_output = args.recovery_output.resolve()

    if args.execute_recovery and args.write_plan_only:
        print(json.dumps({"status": "refused", "reason": "flags_mutually_exclusive"}, ensure_ascii=False))
        return 2

    if not args.execute_recovery:
        plan = build_recovery_plan(
            study_dir=study_dir,
            interrupted_output=interrupted,
            recovery_output=recovery_output,
        )
        plan_path = study_dir / "learning_labels_recovery_plan.json"
        write_recovery_plan(plan, plan_path)
        forensics_dir = study_dir / "forensics"
        forensics_dir.mkdir(parents=True, exist_ok=True)
        write_recovery_plan(plan, forensics_dir / "recovery_plan.json")
        print(
            json.dumps(
                {
                    "status": "plan_written",
                    "plan": str(plan_path),
                    "reusable": len(plan["reusable_order_ids"]),
                    "corrupt": len(plan["corrupt_order_ids"]),
                    "pending_registered": len(plan["pending_registered_order_ids"]),
                    "prior_accounted": plan["budget_accounting"]["prior_wall_accounted_for_deadline_seconds"],
                    "remaining_labeling_wall_seconds": plan["budget_accounting"]["remaining_labeling_wall_seconds"],
                    "executed": False,
                    "note": "execute_recovery_not_requested",
                },
                ensure_ascii=False,
            )
        )
        return 0

    if recovery_output.exists():
        print(json.dumps({"status": "refused", "reason": "recovery_output_exists", "path": str(recovery_output)}))
        return 2

    plan = build_recovery_plan(
        study_dir=study_dir,
        interrupted_output=interrupted,
        recovery_output=recovery_output,
    )
    plan["authorization"] = {
        "recovery_authorized": True,
        "executed": False,
        "note": "execution_starting",
    }
    write_recovery_plan(plan, study_dir / "learning_labels_recovery_plan.json")

    started = time.perf_counter()
    static = static_preflight(study_dir=study_dir, output=recovery_output, preflight_dir=study_dir / "preflight")
    protocol = static["protocol"]
    reuse = PreflightReuseIndex(static["preflight_dir"], protocol=protocol, study_dir=study_dir)
    dataset = Path(static["contracts"]["dataset"])
    orders_blob = json.loads(dataset.read_text(encoding="utf-8"))

    summary = run_recovery_attempt(
        protocol=protocol,
        ordered=static["ordered"],
        orders_blob=orders_blob,
        dataset=str(dataset),
        dataset_sha256=static["contracts"]["dataset_sha256"],
        output=recovery_output,
        reuse=reuse,
        plan=plan,
        interrupted_output=interrupted,
        execution_manifest=static["manifest"],
    )
    verification = verify_labeling_output(
        output=recovery_output,
        manifest=static["manifest"],
        summary=summary,
        protocol=protocol,
    )
    plan["authorization"]["executed"] = True
    plan["authorization"]["attempt_02_status"] = summary.get("status")
    plan["authorization"]["verification_status"] = verification.get("status")
    write_recovery_plan(plan, study_dir / "learning_labels_recovery_plan.json")
    write_recovery_plan(plan, recovery_output / "recovery_plan_executed.json")
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "verification": verification.get("status"),
                "ready_for_training": verification.get("ready_for_training"),
                "labeling_wall_seconds_this_attempt": summary.get("labeling_wall_seconds_this_attempt"),
                "prior_registered_plus_reserve_seconds": summary.get("prior_wall_accounted_seconds"),
                "preflight_wall_seconds_accounted_once": summary.get("preflight_wall_seconds_accounted_once"),
                "continuations_reused_preflight_global": summary.get("preflight_reused_global"),
                "n_orders_done": summary.get("n_orders_done"),
                "pending": summary.get("pending_order_ids"),
                "wall_seconds_cli": time.perf_counter() - started,
                "output": str(recovery_output),
            },
            ensure_ascii=False,
        )
    )
    if summary.get("status") != "completed" or verification.get("status") != "verified":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
