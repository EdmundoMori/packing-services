"""Plan de intento 03 (NO ejecutar en este paso).

Referencia los 46 pedidos content-verified del intento 02.
Ejecuta únicamente los 26 pendientes en orden de manifiesto.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_budget import budget_ledger  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402


def build_attempt03_plan(*, study_dir: Path) -> dict:
    study_dir = study_dir.resolve()
    recon = json.loads((study_dir / "forensics" / "evidence_reconciliation_launcher_prep.json").read_text())
    ledger = budget_ledger()
    pending_ids = recon["pending"]["ids"]
    reusable = []
    for key in (
        "referenced_readonly_from_attempt01",
        "newly_executed_attempt02_excluding_repeat",
        "inevitable_repeat_00108806",
    ):
        reusable.extend(recon["mutually_exclusive_categories"][key]["ids"])
    return {
        "kind": "attempt_03_plan",
        "status": "designed_not_executed",
        "campaign": "learning_objectives_frozen_protocol",
        "attempt_id": "attempt_03_persistent_recovery",
        "source_attempt_02_dir": str(study_dir / "learning_labels_recovery"),
        "output_dir_proposed": str(study_dir / "learning_labels_attempt03"),
        "run_dir_proposed": str(study_dir / "runs" / "attempt_03"),
        "reusable_content_verified_order_ids": sorted(reusable),
        "n_reusable": len(reusable),
        "pending_in_manifest_order": pending_ids,
        "n_pending": len(pending_ids),
        "pending_train": recon["pending"]["train"],
        "pending_development": recon["pending"]["development"],
        "staging_policy": {
            "auto_promote": False,
            "valid_recoverable_candidates": recon["staging"]["valid_recoverable_candidates"],
            "note": "ningún staging pasó validación de resultado completo independiente",
        },
        "budget": ledger,
        "launcher": {
            "module": "tools/labeling_runctl.py",
            "requires_explicit_start": True,
            "no_auto_restart_on_failure": True,
        },
        "authorization": {
            "executed": False,
            "attempt_03_authorized_when_worker_wired": True,
            "note": "Ejecutar solo vía labeling_runctl + run_learning_labels_attempt03.py",
        },
    }


if __name__ == "__main__":
    study = Path(__file__).resolve().parents[1]
    plan = build_attempt03_plan(study_dir=study)
    atomic_write_json(study / "attempt_03_plan.json", plan)
    atomic_write_json(study / "forensics" / "attempt_03_plan.json", plan)
    print(json.dumps({"status": "plan_written", "n_reusable": plan["n_reusable"], "n_pending": plan["n_pending"]}, ensure_ascii=False))
