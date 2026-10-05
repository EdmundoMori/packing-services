"""Plan de recuperación operativa.

Distingue campaña / intento 01 interrumpido / intento 02 recuperación.
El tiempo 214.80… s es tiempo registrado (suma de paredes por pedido en
progress), no una cota demostrada del wall total del proceso.
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

REGISTERED_ORDER_WALL_SUM_SECONDS = 214.80055754699697
# progress.mtime - execution_manifest.mtime (artefactos del lanzador)
LAUNCHER_ARTIFACT_SPAN_SECONDS = 216.745745165
# Reserva operativa explícita dentro del cupo 13500 (no amplía presupuesto)
OPERATIONAL_RESERVE_SECONDS = 120.0
PRIOR_ATTEMPT_ID = "attempt_01_interrupted_20261005"


def prior_wall_accounted_seconds() -> dict[str, Any]:
    """Documenta tiempo registrado, span verificable y reserva."""

    registered = REGISTERED_ORDER_WALL_SUM_SECONDS
    span = LAUNCHER_ARTIFACT_SPAN_SECONDS
    reserve = OPERATIONAL_RESERVE_SECONDS
    # Para el deadline del intento 02: max(registrado, span) + reserva
    accounted = max(registered, span) + reserve
    return {
        "labeling_wall_budget_seconds": 13500.0,
        "registered_order_wall_sum_seconds": registered,
        "registered_includes": [
            "suma de wall_seconds por pedido en progress.orders_done",
            "incluye la reclamación de pared de 00108806 (result vacío)",
            "fases por pedido según el ejecutor (estados+continuaciones+captura+auditoría+escritura de ese pedido)",
        ],
        "registered_excludes_or_uncertain": [
            "arranque del proceso y static_preflight del intento 01",
            "huecos entre pedidos no reflejados en wall_seconds",
            "teardown tras la última escritura",
            "si alguna pared interna fue concurrente (el diseño es secuencial por pedido; no hay evidencia de concurrencia)",
        ],
        "walls_are_successive_by_design": True,
        "registered_is_proven_total_wall_bound": False,
        "launcher_artifact_span_seconds": span,
        "launcher_artifact_span_definition": (
            "mtime(progress.json) - mtime(execution_manifest.json); "
            "cota verificable inferior del wall del intento 01 entre artefactos"
        ),
        "operational_reserve_seconds": reserve,
        "prior_wall_accounted_for_deadline_seconds": accounted,
        "remaining_labeling_wall_seconds": 13500.0 - accounted,
        "preflight_wall_seconds_separate": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "preflight_already_accounted_once": True,
        "do_not_recharge_preflight": True,
        "training_budget_unaffected_undemonstrated": True,
        "note": (
            "No se denomina 'cargo conservador demostrado'. "
            "Se usa tiempo registrado + span de artefactos + reserva operativa explícita."
        ),
    }


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
    # Pendiente registrado en progress vs sin salida
    pending_registered = list(progress.get("pending_order_ids") or []) if progress else []
    present_dirs = {
        p.name for p in (interrupted_output / "orders").iterdir()
    } if (interrupted_output / "orders").is_dir() else set()
    expected_ids = [row["order_id"] for row in manifest["execution_order"] if row.get("split") != "test"]
    never_with_dir = sorted(oid for oid in expected_ids if oid not in present_dirs and oid not in reusable)
    # "never_executed" del audit = sin result válido; subdividir
    pending_set = set(pending_registered)
    unprovable_execution = sorted(
        oid for oid in (audit["by_class"].get("never_executed") or [])
        if oid not in pending_set and oid not in present_dirs
    )
    pending_registered_only = sorted(oid for oid in pending_registered if oid in (audit["by_class"].get("never_executed") or []))

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
                        "comprobable": True,
                        "note": "JSON legibles parciales; no constituyen etiqueta completa de pedido",
                    }
                )
            elif files and any(size == 0 for size in files.values()):
                partial_refs.append(
                    {
                        "order_id": order_id,
                        "choice_dir": choice_dir.name,
                        "provenance": str(choice_dir),
                        "usable_as_complete_order_label": False,
                        "comprobable": False,
                        "note": "archivos vacíos; trabajo no comprobable",
                    }
                )

    pending_work = []
    for row in manifest["execution_order"]:
        if row.get("split") == "test":
            continue
        oid = row["order_id"]
        if oid in reusable:
            action = "reference_verified_result_readonly"
            inevitable_repeat = False
            work_class = "reuse_verified"
        elif oid in corrupt:
            action = "reexecute_order_insufficient_evidence"
            inevitable_repeat = True
            work_class = "inevitable_repeat_corrupt"
        elif oid in pending_set:
            action = "execute_pending_registered"
            inevitable_repeat = False
            work_class = "pending_registered"
        else:
            action = "execute_unprovable_or_missing"
            inevitable_repeat = False
            work_class = "execution_unprovable_missing_output"
        pending_work.append(
            {
                "order_id": oid,
                "split": row["split"],
                "target": row["target"],
                "selection_hash": row["selection_hash"],
                "action": action,
                "work_class": work_class,
                "inevitable_repeat": inevitable_repeat,
                "source_attempt": PRIOR_ATTEMPT_ID if oid in reusable or oid in corrupt else None,
            }
        )

    budget = prior_wall_accounted_seconds()
    plan = {
        "kind": "labeling_recovery_plan",
        "status": "designed_not_executed",
        "campaign": "learning_objectives_frozen_protocol",
        "prior_attempt": {
            "attempt_id": PRIOR_ATTEMPT_ID,
            "directory": str(interrupted_output),
            "execution_manifest_sha256": file_sha256(interrupted_output / "execution_manifest.json"),
            "progress_trusted": False,
            "exit_code": None,
            "cause": "unknown",
            "demonstrated_facts": [
                "non_atomic_write_text_in_attempt_01_executor",
                "eleven_empty_json_files_under_00108806",
                "progress_content_inconsistency_for_00108806",
                "exact_corruption_mechanism_not_established",
            ],
            "not_demonstrated": [
                "SIGKILL",
                "sandbox_kill",
                "OOM",
                "durability_failure_as_proven_cause",
            ],
        },
        "recovery_attempt": {
            "attempt_id": "attempt_02_recovery",
            "directory": str(recovery_output),
            "must_not_exist_before_start": True,
            "references_prior_evidence": True,
            "not_a_single_attempt_campaign": True,
        },
        "integrity_audit_summary": audit["counts"],
        "reusable_order_ids": reusable,
        "corrupt_order_ids": corrupt,
        "pending_registered_order_ids": pending_registered_only,
        "execution_unprovable_or_missing_output_ids": unprovable_execution,
        "never_executed_order_ids_legacy_alias": list(audit["by_class"].get("never_executed") or []),
        "orders_without_directory": never_with_dir,
        "insufficient_order_ids": list(audit["by_class"].get("insufficient") or []),
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
            "preflight_16_counted_once_globally": True,
            "reference_readonly_no_mutate_attempt_01": True,
        },
        "budget_accounting": budget,
        "operational_executor": {
            "persistence_module": "tools/labeling_io.py",
            "integrity_module": "tools/labeling_integrity.py",
            "safe_campaign_module": "tools/labeling_campaign_safe.py",
            "entry": "tools/run_learning_labels_recover.py",
            "execute_recovery_previously": "deliberately_refused_plan_only_step_now_implemented",
            "compatibility": (
                "No modifica protocol_frozen.json, sample_manifest.json, preflight ni losses.py. "
                "labeling_campaign.py del intento 01 se conserva."
            ),
        },
        "authorization": {
            "recovery_authorized": False,
            "executed": False,
            "note": "Actualizar al ejecutar.",
        },
    }
    return plan


def write_recovery_plan(plan: dict[str, Any], path: Path) -> None:
    atomic_write_json(path, plan)
