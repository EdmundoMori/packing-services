"""Plan de recuperación operativa (no ejecuta continuaciones).

Distingue: campaña (protocolo), intento (una invocación del ejecutor),
continuación/recuperación (nuevo directorio que reutiliza evidencia válida).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_contracts import PUBLISHED_PREFLIGHT_WALL_SECONDS  # noqa: E402
from labeling_integrity import audit_labeling_tree, file_sha256  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402

# Contabilidad conservadora del intento interrumpido (mtimes / sumas de paredes).
CONSERVATIVE_PRIOR_LABELING_WALL_SECONDS = 214.80055754699697  # suma progress.orders_done[*].wall_seconds
APPROX_MTIME_LABELING_WALL_SECONDS = 205.09
PRIOR_ATTEMPT_ID = "attempt_01_interrupted_20261005"


def build_recovery_plan(
    *,
    study_dir: Path,
    interrupted_output: Path,
    recovery_output: Path,
) -> dict[str, Any]:
    study_dir = study_dir.resolve()
    interrupted_output = interrupted_output.resolve()
    recovery_output = recovery_output.resolve()
    manifest = json.loads((interrupted_output / "execution_manifest.json").read_text(encoding="utf-8"))
    progress = None
    progress_path = interrupted_output / "progress.json"
    if progress_path.is_file() and progress_path.stat().st_size > 0:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    audit = audit_labeling_tree(interrupted_output, manifest=manifest, progress=progress)

    reusable = list(audit["by_class"].get("reusable_valid") or [])
    corrupt = sorted(
        set(audit["by_class"].get("corrupt") or [])
        | set(audit["by_class"].get("corrupt_or_incomplete") or [])
    )
    never = list(audit["by_class"].get("never_executed") or [])
    insufficient = list(audit["by_class"].get("insufficient") or [])

    # 00108806: partial intact states may be referenced but order is not complete.
    partial_refs: list[dict[str, Any]] = []
    for order_id in corrupt:
        states_dir = interrupted_output / "orders" / order_id / "states"
        if not states_dir.is_dir():
            continue
        for choice_dir in sorted(states_dir.iterdir()):
            if not choice_dir.is_dir():
                continue
            files = {p.name: p.stat().st_size for p in choice_dir.iterdir() if p.is_file()}
            if files and all(size > 0 for size in files.values()):
                partial_refs.append(
                    {
                        "order_id": order_id,
                        "choice_dir": choice_dir.name,
                        "provenance": str(choice_dir),
                        "usable_as_complete_order_label": False,
                        "note": "capturas parciales presentes; pedido incompleto/corrupto a nivel result.json",
                    }
                )

    pending_work = []
    for row in manifest["execution_order"]:
        if row.get("split") == "test":
            continue
        oid = row["order_id"]
        if oid in reusable:
            action = "link_or_copy_verified_result"
            inevitable_repeat = False
        elif oid in corrupt:
            action = "reexecute_order_incomplete_or_corrupt"
            inevitable_repeat = True  # al menos estados no duraderos
        elif oid in never or oid in insufficient:
            action = "execute_never_run_or_insufficient"
            inevitable_repeat = False
        else:
            action = "review"
            inevitable_repeat = False
        pending_work.append(
            {
                "order_id": oid,
                "split": row["split"],
                "target": row["target"],
                "selection_hash": row["selection_hash"],
                "action": action,
                "inevitable_repeat": inevitable_repeat,
                "source_attempt": PRIOR_ATTEMPT_ID if oid in reusable or oid in corrupt else None,
            }
        )

    labeling_budget = float(manifest.get("labeling_wall_budget_seconds") or 13500)
    prior_charged = CONSERVATIVE_PRIOR_LABELING_WALL_SECONDS
    remaining = max(0.0, labeling_budget - prior_charged)

    plan = {
        "kind": "labeling_recovery_plan",
        "status": "designed_not_executed",
        "campaign": "learning_objectives_frozen_protocol",
        "prior_attempt": {
            "attempt_id": PRIOR_ATTEMPT_ID,
            "directory": str(interrupted_output),
            "execution_manifest_sha256": file_sha256(interrupted_output / "execution_manifest.json"),
            "progress_trusted": False,
        },
        "recovery_attempt": {
            "attempt_id": "attempt_02_recovery_proposed",
            "directory": str(recovery_output),
            "must_not_exist_before_start": True,
            "references_prior_evidence": True,
            "not_a_single_attempt_campaign": True,
        },
        "integrity_audit_summary": audit["counts"],
        "reusable_order_ids": reusable,
        "corrupt_order_ids": corrupt,
        "never_executed_order_ids": never,
        "insufficient_order_ids": insufficient,
        "partial_state_references_not_complete_labels": partial_refs,
        "pending_work_in_manifest_order": pending_work,
        "rules": {
            "no_selection_by_signal_or_margins": True,
            "do_not_reexecute_verified_complete_continuations": True,
            "corrupt_order_not_treated_as_valid_labels": True,
            "inevitable_repeats_recorded_explicitly": True,
            "do_not_reset_or_expand_budget": True,
            "preserve_interrupted_attempt_directory": True,
            "test_excluded": True,
            "provisional_normalization_not_for_training": True,
        },
        "budget_accounting": {
            "labeling_wall_budget_seconds": labeling_budget,
            "prior_labeling_wall_charged_seconds": prior_charged,
            "prior_charge_method": (
                "conservative_sum_of_progress_order_wall_seconds_including_corrupt_claim; "
                f"mtime_span_approx={APPROX_MTIME_LABELING_WALL_SECONDS}s_not_used_as_charge"
            ),
            "remaining_labeling_wall_seconds": remaining,
            "preflight_wall_seconds_separate": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "preflight_already_accounted_once": True,
            "do_not_recharge_preflight": True,
            "training_budget_unaffected_undemonstrated": True,
        },
        "operational_executor": {
            "persistence_module": "tools/labeling_io.py",
            "integrity_module": "tools/labeling_integrity.py",
            "safe_campaign_module": "tools/labeling_campaign_safe.py",
            "entry": "tools/run_learning_labels_recover.py",
            "compatibility": (
                "No modifica protocol_frozen.json, sample_manifest.json, preflight ni losses.py. "
                "El ejecutor original tools/labeling_campaign.py se conserva; la recuperación usa "
                "la capa safe con escritura atómica y progreso post-validación."
            ),
        },
        "authorization": {
            "recovery_authorized": False,
            "executed": False,
            "note": "Plan solamente; no ejecutar en este paso.",
        },
    }
    return plan


def write_recovery_plan(plan: dict[str, Any], path: Path) -> None:
    atomic_write_json(path, plan)
