"""Capa operativa segura de campaña: persistencia atómica y progreso post-validación.

Conserva las fórmulas y límites del ejecutor original. No amplía presupuestos.
Compatible con recuperación que referencia evidencia verificada.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
COUNTERFACTUAL_TOOLS = HERE.parents[1] / "counterfactual_ranking" / "tools"
for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

import labeling_campaign as base  # noqa: E402
from diagnostic import WallClockExceeded  # noqa: E402
from labeling_contracts import PUBLISHED_PREFLIGHT_WALL_SECONDS  # noqa: E402
from labeling_integrity import verify_order_artifacts  # noqa: E402
from labeling_io import (  # noqa: E402
    AtomicWriteError,
    atomic_write_json,
    install_termination_flags,
    restore_signal_handlers,
)
from labeling_reuse import PreflightReuseIndex  # noqa: E402

LabelBudget = base.LabelBudget


def label_order_safe_from_spec(
    orders_blob: dict[str, Any],
    spec: dict[str, Any],
    *,
    dataset: str,
    dataset_sha256: str,
    output_order_dir: Path,
    budget: LabelBudget,
    reuse: PreflightReuseIndex,
    deadline: float,
    now: Callable[[], float],
) -> dict[str, Any]:
    staging = output_order_dir.parent / f".staging_{output_order_dir.name}"
    if staging.exists() and any(staging.iterdir()):
        raise RuntimeError(f"staging no vacío: {staging}")
    staging.mkdir(parents=True, exist_ok=True)
    try:
        result = base.label_order(
            orders_blob,
            spec,
            dataset=dataset,
            dataset_sha256=dataset_sha256,
            output_order_dir=staging,
            budget=budget,
            reuse=reuse,
            deadline=deadline,
            now=now,
        )
        # Copiar capturas staging → destino con replace atómico de JSON textuales
        output_order_dir.mkdir(parents=True, exist_ok=True)
        states_src = staging / "states"
        if states_src.is_dir():
            for choice_dir in states_src.iterdir():
                dest_choice = output_order_dir / "states" / choice_dir.name
                dest_choice.mkdir(parents=True, exist_ok=True)
                for path in choice_dir.iterdir():
                    if path.suffix != ".json":
                        continue
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    atomic_write_json(dest_choice / path.name, payload, indent=2 if path.name == "state.json" else None)
        # result sin depender de progress
        public_states = result.get("states")
        atomic_write_json(output_order_dir / "result.json", result)
        check = verify_order_artifacts(output_order_dir, expected=spec)
        if result.get("status") == "ok" and check["classification"] != "reusable_valid":
            # degradar status en disco si la integridad falla
            result = {
                **result,
                "status": "incomplete_persistence",
                "integrity_issues": check["issues"],
            }
            atomic_write_json(output_order_dir / "result.json", result)
        return result
    finally:
        # Conservar staging si falló a medias podría ayudar al forense; si éxito, limpiar staging vacío de riesgo
        # No borramos staging automáticamente para no destruir evidencia de fallo.
        pass


def run_labeling_campaign_safe(
    *,
    protocol: dict[str, Any],
    ordered: list[dict[str, Any]],
    orders_blob: dict[str, Any],
    dataset: str,
    dataset_sha256: str,
    output: Path,
    reuse: PreflightReuseIndex,
    now: Callable[[], float] | None = None,
    deadline: float | None = None,
    prior_wall_charged_seconds: float = 0.0,
    reuse_verified_orders: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Campaña segura: progreso solo tras persistir+validar; manifiesto de cierre/interrupción."""

    clock = now or time.perf_counter
    budget = LabelBudget(protocol)
    # No reinicia ni amplía: el techo efectivo resta el tiempo ya cargado
    effective_wall = max(0.0, budget.wall_seconds - float(prior_wall_charged_seconds))
    started = clock()
    labeling_deadline = deadline if deadline is not None else started + effective_wall
    done: list[dict[str, Any]] = []
    pending = [row["order_id"] for row in ordered]
    status = "completed"
    stop_flag: dict[str, Any] = {"stop": False, "signal": None}
    handlers = install_termination_flags(stop_flag)
    reuse_verified_orders = reuse_verified_orders or {}
    try:
        atomic_write_json(
            output / "attempt_manifest.json",
            {
                "kind": "labeling_attempt_manifest",
                "status": "running",
                "prior_wall_charged_seconds": prior_wall_charged_seconds,
                "effective_labeling_wall_seconds": effective_wall,
                "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
                "reuse_verified_order_ids": sorted(reuse_verified_orders),
            },
        )
        for spec in ordered:
            if stop_flag["stop"]:
                status = "incomplete_signal"
                break
            if spec["split"] == "test":
                raise RuntimeError("bloqueo: test en la campaña de etiquetado")
            if clock() > labeling_deadline:
                status = "incomplete_wall_clock"
                break
            order_id = spec["order_id"]
            order_dir = output / "orders" / order_id
            if order_id in reuse_verified_orders:
                src = Path(reuse_verified_orders[order_id])
                check = verify_order_artifacts(src, expected=spec)
                if check["classification"] != "reusable_valid":
                    raise RuntimeError(f"reuso rechazado por integridad: {order_id} {check['issues']}")
                # Referenciar procedencia sin reejecutar
                atomic_write_json(
                    order_dir / "provenance.json",
                    {
                        "source_order_dir": str(src),
                        "source_result_sha256": check["result_sha256"],
                        "action": "reused_verified_without_reexecution",
                    },
                )
                result = json.loads((src / "result.json").read_text(encoding="utf-8"))
                # copiar result validado
                atomic_write_json(order_dir / "result.json", result)
            else:
                result = label_order_safe_from_spec(
                    orders_blob,
                    spec,
                    dataset=dataset,
                    dataset_sha256=dataset_sha256,
                    output_order_dir=order_dir,
                    budget=budget,
                    reuse=reuse,
                    deadline=labeling_deadline,
                    now=clock,
                )
            # Validación obligatoria antes de progress
            check = verify_order_artifacts(order_dir, expected=spec)
            if result.get("status") == "ok" and check["classification"] != "reusable_valid":
                result = {**result, "status": "incomplete_persistence", "integrity_issues": check["issues"]}
                atomic_write_json(order_dir / "result.json", result)
            public = {key: value for key, value in result.items() if key != "states"}
            public["n_states"] = result.get("n_states")
            public["content_classification"] = check["classification"]
            done.append(public)
            pending = [row["order_id"] for row in ordered[len(done) :]]
            atomic_write_json(
                output / "progress.json",
                {
                    "status": "running",
                    "orders_done": done,
                    "pending_order_ids": pending,
                    "budget": {
                        "states_used": budget.states_used,
                        "continuations_new": budget.continuations_new,
                        "continuations_reused": budget.continuations_reused,
                        "continuations_unknown": budget.continuations_unknown,
                        "pending_continuations": budget.pending_continuations,
                    },
                    "integrity_note": "progress actualizado solo tras persistir y validar result.json",
                },
            )
    except WallClockExceeded:
        status = "incomplete_wall_clock"
    except AtomicWriteError as exc:
        status = "incomplete_persistence"
        atomic_write_json(output / "runtime_error.json", {"error": str(exc), "class": "AtomicWriteError"})
    except RuntimeError as exc:
        if "error interno del evaluador" in str(exc):
            status = "incomplete_evaluator_internal"
        else:
            status = "incomplete_runtime"
            atomic_write_json(output / "runtime_error.json", {"error": str(exc)})
            raise
    finally:
        restore_signal_handlers(handlers)

    pending = [row["order_id"] for row in ordered if row["order_id"] not in {item["order_id"] for item in done}]
    if pending and status == "completed":
        status = "incomplete_pending_orders"
    labeling_wall = clock() - started
    summary = {
        "status": status,
        "orders": done,
        "pending_order_ids": pending,
        "n_orders_done": len(done),
        "n_orders_expected": len(ordered),
        "states_used": budget.states_used,
        "continuations_new": budget.continuations_new,
        "continuations_reused": budget.continuations_reused,
        "continuations_unknown": budget.continuations_unknown,
        "pending_continuations": budget.pending_continuations,
        "labeling_wall_seconds_this_attempt": labeling_wall,
        "prior_wall_charged_seconds": prior_wall_charged_seconds,
        "labeling_wall_seconds_accounted_cumulative": labeling_wall + prior_wall_charged_seconds,
        "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "global_accounted_wall_seconds": labeling_wall
        + prior_wall_charged_seconds
        + PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "reuse": reuse.summary(),
        "training_executed": False,
        "development_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
        "signal": stop_flag.get("signal"),
    }
    atomic_write_json(output / "labeling_summary.json", summary)
    atomic_write_json(
        output / "attempt_manifest.json",
        {
            "kind": "labeling_attempt_manifest",
            "status": status,
            "closed": True,
            "prior_wall_charged_seconds": prior_wall_charged_seconds,
            "labeling_wall_seconds_this_attempt": labeling_wall,
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "progress_is_source_of_truth": False,
            "uncatchable_interruptions_note": (
                "SIGKILL/SIGSTOP/power_loss cannot be handled in-process; "
                "no absolute durability guarantee is claimed"
            ),
        },
    )
    return summary


def _symlink_relative(target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"enlace destino ya existe: {link}")
    rel = os.path.relpath(target, start=link.parent)
    os.symlink(rel, link)


def reference_verified_order(
    *,
    src_order_dir: Path,
    dest_order_dir: Path,
    spec: dict[str, Any],
    source_attempt: str = "attempt_01_interrupted_20261005",
) -> dict[str, Any]:
    """Referencia de solo lectura a un pedido content-verified (sin mutarlo ni reejecutarlo)."""

    check = verify_order_artifacts(src_order_dir, expected=spec)
    if check["classification"] != "reusable_valid":
        raise RuntimeError(f"reuso rechazado por integridad: {spec['order_id']} {check['issues']}")
    dest_order_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        dest_order_dir / "provenance.json",
        {
            "source_attempt": source_attempt,
            "source_order_dir": str(src_order_dir.resolve()),
            "source_result_sha256": check["result_sha256"],
            "action": "symlink_readonly_reference_without_reexecution",
            "originals_mutated": False,
        },
    )
    _symlink_relative(src_order_dir / "result.json", dest_order_dir / "result.json")
    _symlink_relative(src_order_dir / "states", dest_order_dir / "states")
    result = json.loads((src_order_dir / "result.json").read_text(encoding="utf-8"))
    return result


def _emit_runctl_heartbeat(*, current_order_id: str | None, phase: str, extra: dict[str, Any] | None = None) -> None:
    """Heartbeat opcional cuando el worker corre bajo labeling_runctl (LABELING_RUN_DIR)."""

    run_dir_raw = os.environ.get("LABELING_RUN_DIR")
    if not run_dir_raw:
        return
    from labeling_runctl import write_heartbeat  # import diferido: evita ciclo en tests unitarios

    payload: dict[str, Any] = {
        "pid": os.getpid(),
        "unix": time.time(),
        "phase": phase,
        "current_order_id": current_order_id,
        "run_id": os.environ.get("LABELING_RUN_ID"),
        "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
    }
    if extra:
        payload.update(extra)
    write_heartbeat(Path(run_dir_raw), payload)


def _continuation_keys_from_order_result(result: dict[str, Any]) -> set[tuple[Any, ...]]:
    keys: set[tuple[Any, ...]] = set()
    oid = result.get("order_id")
    for state in result.get("states") or []:
        choice = state.get("choice_index")
        for alt in state.get("alternatives") or []:
            action = alt.get("action")
            source = alt.get("source")
            keys.add((oid, choice, json.dumps(action, sort_keys=True, default=str), source))
    return keys


def run_recovery_attempt(
    *,
    protocol: dict[str, Any],
    ordered: list[dict[str, Any]],
    orders_blob: dict[str, Any],
    dataset: str,
    dataset_sha256: str,
    output: Path,
    reuse: PreflightReuseIndex,
    plan: dict[str, Any],
    interrupted_output: Path,
    execution_manifest: dict[str, Any],
    now: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Intento 02: referencia 12 verificados; ejecuta pendientes y repetición de corrupto."""

    clock = now or time.perf_counter
    budget = LabelBudget(protocol)
    prior = float(plan["budget_accounting"]["prior_wall_accounted_for_deadline_seconds"])
    effective_wall = max(0.0, budget.wall_seconds - prior)
    started = clock()
    labeling_deadline = started + effective_wall
    reusable = set(plan["reusable_order_ids"])
    corrupt = set(plan["corrupt_order_ids"])
    reuse_paths = {
        oid: interrupted_output / "orders" / oid for oid in reusable
    }
    done: list[dict[str, Any]] = []
    status = "completed"
    stop_flag: dict[str, Any] = {"stop": False, "signal": None}
    handlers = install_termination_flags(stop_flag)
    global_keys: set[tuple[Any, ...]] = set()
    preflight_keys: set[tuple[Any, ...]] = set()
    inevitable_repeats: list[str] = []
    referenced: list[str] = []
    newly_executed: list[str] = []

    output.mkdir(parents=True, exist_ok=True)
    # Copiar manifiesto de ejecución (bytes nuevos, no muta el del intento 01)
    atomic_write_json(output / "execution_manifest.json", execution_manifest)
    atomic_write_json(
        output / "attempt_manifest.json",
        {
            "kind": "labeling_attempt_manifest",
            "attempt_id": "attempt_02_recovery",
            "status": "running",
            "prior_wall_accounted_seconds": prior,
            "effective_labeling_wall_seconds": effective_wall,
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "referenced_order_ids": sorted(reusable),
            "corrupt_inevitable_repeat": sorted(corrupt),
            "progress_is_source_of_truth": False,
            "cause_of_attempt_01": "unknown",
        },
    )
    try:
        for spec in ordered:
            if stop_flag["stop"]:
                status = "incomplete_signal"
                break
            if spec["split"] == "test":
                raise RuntimeError("bloqueo: test en recuperación")
            if clock() > labeling_deadline:
                status = "incomplete_wall_clock"
                break
            order_id = spec["order_id"]
            order_dir = output / "orders" / order_id
            if order_id in reusable:
                result = reference_verified_order(
                    src_order_dir=reuse_paths[order_id],
                    dest_order_dir=order_dir,
                    spec=spec,
                )
                referenced.append(order_id)
                # Contabilizar preflight embebido una sola vez por clave global
                for key in _continuation_keys_from_order_result(result):
                    if key in global_keys:
                        raise RuntimeError(f"clave global duplicada al referenciar: {key[:3]}")
                    global_keys.add(key)
                    if key[3] == "preflight_reused":
                        preflight_keys.add(key[:3])
            else:
                if order_id in corrupt:
                    inevitable_repeats.append(order_id)
                    atomic_write_json(
                        order_dir / "repeat_record.json",
                        {
                            "order_id": order_id,
                            "reason": "insufficient_on_disk_evidence",
                            "not_because_of_return_value": True,
                            "prior_partial_comprobable": [
                                p for p in plan.get("partial_state_references_not_complete_labels") or []
                                if p.get("order_id") == order_id and p.get("comprobable")
                            ],
                            "prior_uncomprobable": [
                                p for p in plan.get("partial_state_references_not_complete_labels") or []
                                if p.get("order_id") == order_id and not p.get("comprobable")
                            ],
                        },
                    )
                result = label_order_safe_from_spec(
                    orders_blob,
                    spec,
                    dataset=dataset,
                    dataset_sha256=dataset_sha256,
                    output_order_dir=order_dir,
                    budget=budget,
                    reuse=reuse,
                    deadline=labeling_deadline,
                    now=clock,
                )
                newly_executed.append(order_id)
                for key in _continuation_keys_from_order_result(result):
                    short = key[:3]
                    if short in {k[:3] for k in global_keys}:
                        if order_id in corrupt:
                            # repetición inevitable: misma clave geométrica permitida y registrada
                            pass
                        else:
                            raise RuntimeError(f"clave global duplicada: {short}")
                    global_keys.add(key)
                    if key[3] == "preflight_reused":
                        if short in preflight_keys:
                            raise RuntimeError(f"preflight recontado: {short}")
                        preflight_keys.add(short)

            check = verify_order_artifacts(order_dir, expected=spec)
            if result.get("status") == "ok" and check["classification"] != "reusable_valid":
                result = {
                    **result,
                    "status": "incomplete_persistence",
                    "integrity_issues": check["issues"],
                }
                # No mutar originales: si es symlink de result, escribir result_local
                if (order_dir / "result.json").is_symlink():
                    atomic_write_json(order_dir / "result_integrity_override.json", result)
                else:
                    atomic_write_json(order_dir / "result.json", result)
            public = {key: value for key, value in result.items() if key != "states"}
            public["n_states"] = result.get("n_states")
            public["content_classification"] = check["classification"]
            public["referenced_from_attempt_01"] = order_id in reusable
            public["inevitable_repeat"] = order_id in corrupt
            done.append(public)
            pending = [row["order_id"] for row in ordered[len(done) :]]
            atomic_write_json(
                output / "progress.json",
                {
                    "status": "running",
                    "attempt_id": "attempt_02_recovery",
                    "orders_done": done,
                    "pending_order_ids": pending,
                    "budget": {
                        "states_used": budget.states_used,
                        "continuations_new": budget.continuations_new,
                        "continuations_reused_this_attempt_via_index": budget.continuations_reused,
                        "continuations_unknown": budget.continuations_unknown,
                        "pending_continuations": budget.pending_continuations,
                        "preflight_reused_global_unique": len(preflight_keys),
                    },
                    "integrity_note": "progress solo tras persistir/referenciar y validar",
                },
            )
    except WallClockExceeded:
        status = "incomplete_wall_clock"
    except AtomicWriteError as exc:
        status = "incomplete_persistence"
        atomic_write_json(output / "runtime_error.json", {"error": str(exc), "class": "AtomicWriteError"})
    except RuntimeError as exc:
        if "error interno del evaluador" in str(exc):
            status = "incomplete_evaluator_internal"
        else:
            status = "incomplete_runtime"
            atomic_write_json(output / "runtime_error.json", {"error": str(exc)})
            raise
    finally:
        restore_signal_handlers(handlers)

    pending = [row["order_id"] for row in ordered if row["order_id"] not in {item["order_id"] for item in done}]
    if pending and status == "completed":
        status = "incomplete_pending_orders"
    labeling_wall = clock() - started
    # El índice de reuso no debe haberse usado para los 12 referenciados; preflight global = claves únicas
    if len(preflight_keys) > 16:
        status = "incomplete_preflight_recount"
    summary = {
        "status": status,
        "attempt_id": "attempt_02_recovery",
        "orders": done,
        "pending_order_ids": pending,
        "n_orders_done": len(done),
        "n_orders_expected": len(ordered),
        "referenced_order_ids": referenced,
        "newly_executed_order_ids": newly_executed,
        "inevitable_repeat_order_ids": inevitable_repeats,
        "states_used": budget.states_used,
        "continuations_new": budget.continuations_new,
        "continuations_reused": len(preflight_keys),  # global único para verificación
        "continuations_reused_via_index_this_attempt": reuse.reused,
        "continuations_unknown": budget.continuations_unknown,
        "pending_continuations": budget.pending_continuations,
        "preflight_reused_global": len(preflight_keys),
        "labeling_wall_seconds_this_attempt": labeling_wall,
        "prior_wall_accounted_seconds": prior,
        "labeling_wall_seconds_accounted_cumulative": labeling_wall + prior,
        "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "global_accounted_wall_seconds": labeling_wall + prior + PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "reuse": reuse.summary(),
        "training_executed": False,
        "development_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
        "signal": stop_flag.get("signal"),
        "provisional_normalization_used": False,
    }
    atomic_write_json(output / "labeling_summary.json", summary)
    atomic_write_json(
        output / "attempt_manifest.json",
        {
            "kind": "labeling_attempt_manifest",
            "attempt_id": "attempt_02_recovery",
            "status": status,
            "closed": True,
            "prior_wall_accounted_seconds": prior,
            "labeling_wall_seconds_this_attempt": labeling_wall,
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "preflight_reused_global_unique": len(preflight_keys),
            "progress_is_source_of_truth": False,
            "uncatchable_interruptions_note": (
                "No absolute durability; uncatchable signals may still interrupt. "
                "SIGKILL/host crash may prevent a normal close."
            ),
        },
    )
    return summary


def run_attempt03_recovery(
    *,
    protocol: dict[str, Any],
    ordered: list[dict[str, Any]],
    orders_blob: dict[str, Any],
    dataset: str,
    dataset_sha256: str,
    output: Path,
    reuse: PreflightReuseIndex,
    plan: dict[str, Any],
    source_attempt02_dir: Path,
    execution_manifest: dict[str, Any],
    label_order_fn: Callable[..., dict[str, Any]] | None = None,
    now: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Intento 03: referencia 46 content-verified del intento 02; ejecuta solo 26 pendientes.

    Completitud de campaña ≠ salida de proceso: requiere verificación independiente.
    No reinicia el presupuesto; hereda prior del plan/ledger.
    """

    clock = now or time.perf_counter
    pack_order = label_order_fn or label_order_safe_from_spec
    budget = LabelBudget(protocol)
    prior = float(plan["budget"]["prior_wall_accounted_for_next_deadline_seconds"])
    effective_wall = max(0.0, budget.wall_seconds - prior)
    started = clock()
    labeling_deadline = started + effective_wall
    reusable = set(plan["reusable_content_verified_order_ids"])
    pending_set = set(plan["pending_in_manifest_order"])
    if reusable & pending_set:
        raise RuntimeError("plan inválido: intersección reusable∩pending")
    expected_reusable = int(plan["n_reusable"])
    expected_pending = int(plan["n_pending"])
    if len(reusable) != expected_reusable or len(pending_set) != expected_pending:
        raise RuntimeError(
            f"plan inválido: esperados {expected_reusable}+{expected_pending}, "
            f"got {len(reusable)}+{len(pending_set)}"
        )
    if len(plan["pending_in_manifest_order"]) != expected_pending:
        raise RuntimeError("plan inválido: pending_in_manifest_order length mismatch")
    if len(plan["reusable_content_verified_order_ids"]) != expected_reusable:
        raise RuntimeError("plan inválido: reusable list length mismatch")
    reuse_paths = {oid: source_attempt02_dir / "orders" / oid for oid in reusable}
    done: list[dict[str, Any]] = []
    status = "completed"
    stop_flag: dict[str, Any] = {"stop": False, "signal": None}
    handlers = install_termination_flags(stop_flag)
    global_keys: set[tuple[Any, ...]] = set()
    preflight_keys: set[tuple[Any, ...]] = set()
    referenced: list[str] = []
    newly_executed: list[str] = []

    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / "execution_manifest.json", execution_manifest)
    atomic_write_json(
        output / "attempt_manifest.json",
        {
            "kind": "labeling_attempt_manifest",
            "attempt_id": "attempt_03_persistent_recovery",
            "status": "running",
            "prior_wall_accounted_seconds": prior,
            "effective_labeling_wall_seconds": effective_wall,
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "referenced_order_ids": sorted(reusable),
            "pending_order_ids": list(plan["pending_in_manifest_order"]),
            "progress_is_source_of_truth": False,
            "process_exit_is_not_campaign_complete": True,
        },
    )
    _emit_runctl_heartbeat(
        current_order_id=None,
        phase="start",
        extra={"n_reusable": expected_reusable, "n_pending": expected_pending},
    )

    try:
        for spec in ordered:
            if stop_flag["stop"]:
                status = "incomplete_signal"
                break
            if spec["split"] == "test":
                raise RuntimeError("bloqueo: test en intento 03")
            order_id = spec["order_id"]
            if order_id not in reusable and order_id not in pending_set:
                raise RuntimeError(f"pedido fuera de plan attempt03: {order_id}")
            if clock() > labeling_deadline:
                status = "incomplete_wall_clock"
                break
            order_dir = output / "orders" / order_id
            _emit_runctl_heartbeat(current_order_id=order_id, phase="order_begin")
            if order_id in reusable:
                result = reference_verified_order(
                    src_order_dir=reuse_paths[order_id],
                    dest_order_dir=order_dir,
                    spec=spec,
                    source_attempt="attempt_02_recovery_content_verified",
                )
                referenced.append(order_id)
                for key in _continuation_keys_from_order_result(result):
                    if key in global_keys:
                        raise RuntimeError(f"clave global duplicada al referenciar: {key[:3]}")
                    global_keys.add(key)
                    if key[3] == "preflight_reused":
                        preflight_keys.add(key[:3])
            else:
                result = pack_order(
                    orders_blob,
                    spec,
                    dataset=dataset,
                    dataset_sha256=dataset_sha256,
                    output_order_dir=order_dir,
                    budget=budget,
                    reuse=reuse,
                    deadline=labeling_deadline,
                    now=clock,
                )
                newly_executed.append(order_id)
                for key in _continuation_keys_from_order_result(result):
                    short = key[:3]
                    if short in {k[:3] for k in global_keys}:
                        raise RuntimeError(f"clave global duplicada: {short}")
                    global_keys.add(key)
                    if key[3] == "preflight_reused":
                        if short in preflight_keys:
                            raise RuntimeError(f"preflight recontado: {short}")
                        preflight_keys.add(short)

            check = verify_order_artifacts(order_dir, expected=spec)
            if result.get("status") == "ok" and check["classification"] != "reusable_valid":
                result = {
                    **result,
                    "status": "incomplete_persistence",
                    "integrity_issues": check["issues"],
                }
                if (order_dir / "result.json").is_symlink():
                    atomic_write_json(order_dir / "result_integrity_override.json", result)
                else:
                    atomic_write_json(order_dir / "result.json", result)
            public = {key: value for key, value in result.items() if key != "states"}
            public["n_states"] = result.get("n_states")
            public["content_classification"] = check["classification"]
            public["referenced_from_attempt_02"] = order_id in reusable
            public["newly_executed_attempt_03"] = order_id in pending_set
            done.append(public)
            remaining_pending = [oid for oid in plan["pending_in_manifest_order"] if oid not in newly_executed]
            atomic_write_json(
                output / "progress.json",
                {
                    "status": "running",
                    "attempt_id": "attempt_03_persistent_recovery",
                    "orders_done": done,
                    "pending_order_ids": remaining_pending,
                    "budget": {
                        "states_used": budget.states_used,
                        "continuations_new": budget.continuations_new,
                        "continuations_reused_this_attempt_via_index": budget.continuations_reused,
                        "continuations_unknown": budget.continuations_unknown,
                        "pending_continuations": budget.pending_continuations,
                        "preflight_reused_global_unique": len(preflight_keys),
                        "prior_wall_accounted_seconds": prior,
                        "effective_labeling_wall_seconds": effective_wall,
                    },
                    "integrity_note": "progress solo tras persistir/referenciar y validar",
                },
            )
            _emit_runctl_heartbeat(
                current_order_id=order_id,
                phase="order_persisted",
                extra={
                    "last_persisted_key": order_id,
                    "n_done": len(done),
                    "n_newly_executed": len(newly_executed),
                },
            )
    except WallClockExceeded:
        status = "incomplete_wall_clock"
    except AtomicWriteError as exc:
        status = "incomplete_persistence"
        atomic_write_json(output / "runtime_error.json", {"error": str(exc), "class": "AtomicWriteError"})
    except RuntimeError as exc:
        if "error interno del evaluador" in str(exc):
            status = "incomplete_evaluator_internal"
        elif "bloqueo: test" in str(exc):
            status = "refused_test_split"
            atomic_write_json(output / "runtime_error.json", {"error": str(exc)})
        else:
            status = "incomplete_runtime"
            atomic_write_json(output / "runtime_error.json", {"error": str(exc)})
            raise
    finally:
        restore_signal_handlers(handlers)

    pending = [oid for oid in plan["pending_in_manifest_order"] if oid not in newly_executed]
    if pending and status == "completed":
        status = "incomplete_pending_orders"
    if len(referenced) != len(reusable) and status == "completed":
        status = "incomplete_reference"
    labeling_wall = clock() - started
    if len(preflight_keys) > 16:
        status = "incomplete_preflight_recount"
    summary = {
        "status": status,
        "attempt_id": "attempt_03_persistent_recovery",
        "orders": done,
        "pending_order_ids": pending,
        "n_orders_done": len(done),
        "n_orders_expected": expected_reusable + expected_pending,
        "referenced_order_ids": referenced,
        "newly_executed_order_ids": newly_executed,
        "states_used": budget.states_used,
        "continuations_new": budget.continuations_new,
        "continuations_reused": len(preflight_keys),
        "continuations_reused_via_index_this_attempt": reuse.reused,
        "continuations_unknown": budget.continuations_unknown,
        "pending_continuations": budget.pending_continuations,
        "preflight_reused_global": len(preflight_keys),
        "labeling_wall_seconds_this_attempt": labeling_wall,
        "prior_wall_accounted_seconds": prior,
        "labeling_wall_seconds_accounted_cumulative": labeling_wall + prior,
        "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "global_accounted_wall_seconds": labeling_wall + prior + PUBLISHED_PREFLIGHT_WALL_SECONDS,
        "reuse": reuse.summary(),
        "training_executed": False,
        "development_evaluated": False,
        "test_executed": False,
        "physical_stability_verified": None,
        "signal": stop_flag.get("signal"),
        "provisional_normalization_used": False,
        "process_exit_is_not_campaign_complete": True,
    }
    atomic_write_json(output / "labeling_summary.json", summary)
    atomic_write_json(
        output / "attempt_manifest.json",
        {
            "kind": "labeling_attempt_manifest",
            "attempt_id": "attempt_03_persistent_recovery",
            "status": status,
            "closed": True,
            "prior_wall_accounted_seconds": prior,
            "labeling_wall_seconds_this_attempt": labeling_wall,
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "preflight_reused_global_unique": len(preflight_keys),
            "progress_is_source_of_truth": False,
            "process_exit_is_not_campaign_complete": True,
            "uncatchable_interruptions_note": (
                "SIGKILL and host crash may prevent a normal close; "
                "no absolute durability is promised."
            ),
        },
    )
    _emit_runctl_heartbeat(
        current_order_id=None,
        phase="closed",
        extra={"status": status, "exit_pending_verification": True},
    )
    return summary
