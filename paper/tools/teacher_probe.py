"""Diagnóstico del teacher receding_horizon_ep. No entrena ni abre pickle."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

from pilot_common import (
    NO_CANDIDATE_REASON,
    REPO_ROOT,
    TIE_EPS,
    TIMEOUT_SECONDS,
    atomic_write_json,
    sha256_file,
)
from pilot_problems import capture_document, prepare_imports, problem_snapshot

TEACHER_NAME = "receding_horizon_ep"
TEACHER_ALGORITHM = "teacher_receding_horizon_ep"
PROTOCOL_10 = REPO_ROOT / "paper/protocols/10_normalization_ablation.json"
PROTOCOL_07 = REPO_ROOT / "paper/protocols/07_independent_evaluation.json"
PACKING_DIR = REPO_ROOT / "paper/results/11_normalization_ablation/packing"
CODE_FILES = (
    "online_policy_ml/src_ml/teacher.py",
    "online_policy_ml/src_ml/collect.py",
    "src/packing_services/algorithms/online_3d_bpp_heuristic.py",
    "src/packing_services/online/policies.py",
    "src/packing_services/online/loop.py",
    "paper/tools/ablation_pack.py",
    "paper/tools/ablation_worker.py",
)
EXPECTED_FLAGS = {
    "non_overlap": True,
    "containment": True,
    "allow_rotation": True,
    "max_weight": True,
    "basic_stability": False,
    "load_bearing": False,
    "fragility": False,
    "unloading_sequence": False,
}
TARGET_BOXES = {
    "euro-pallet": ("EURO_PALLET", 1200.0, 800.0, 2000.0),
    "rollcontainer": ("ROLLCONTAINER", 800.0, 700.0, 2000.0),
}
Worker = Callable[[dict[str, Any]], dict[str, Any]]


class ProbeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def development_orders() -> list[dict[str, Any]]:
    document = json.loads(PROTOCOL_10.read_text(encoding="utf-8"))
    return list(document["development_sample"]["execution_items"])


def dataset_sha256_expected() -> str:
    document = json.loads(PROTOCOL_07.read_text(encoding="utf-8"))
    return str(document["orders"]["source_dataset_sha256"])


def code_sha256() -> dict[str, str]:
    return {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}


def _fingerprint(session: Any) -> tuple:
    bins = []
    for state in session.states:
        bins.append(
            (
                float(state.loaded_weight),
                tuple((point.x, point.y, point.z) for point in state.extreme_points),
                tuple(
                    (
                        box.position.x,
                        box.position.y,
                        box.position.z,
                        box.dimensions.length,
                        box.dimensions.width,
                        box.dimensions.height,
                    )
                    for box in state.placed
                ),
            )
        )
    packed = tuple(
        (item.item_id, item.position.x, item.position.y, item.position.z) for item in session.packed
    )
    return tuple(bins), packed


def teacher_decision(options: list[Any], **kwargs: Any) -> tuple[int | None, bool]:
    """Llama al teacher existente. El booleano indica que usó el fallback de volumen."""

    prepare_imports()
    import teacher as teacher_module

    calls = {"n": 0}
    original = teacher_module.privileged_volume_ep_index

    def wrapped(candidates: Any) -> int | None:
        calls["n"] += 1
        return original(candidates)

    teacher_module.privileged_volume_ep_index = wrapped
    try:
        index = teacher_module.receding_horizon_ep_index(options, **kwargs)
    finally:
        teacher_module.privileged_volume_ep_index = original
    return index, calls["n"] > 0


def run_teacher_rollout(problem: Any) -> tuple[Any, dict[str, Any]]:
    """Mismo control que collect_order_transitions: una decisión nueva y un commit real por paso."""

    prepare_imports()
    from packing_services.algorithms._constructive import order_items
    from packing_services.algorithms.base import build_solution
    from packing_services.algorithms.online_3d_bpp_heuristic import METADATA
    from packing_services.domain.enums import SortStrategy
    from packing_services.domain.models import UnpackedItem
    from packing_services.online.budget import InformationBudget
    from packing_services.online.mask import ValidatorMask
    from packing_services.online.params import resolve_selection, support_threshold
    from packing_services.online.session import ExtremePointOnlineSession
    from packing_services.online.types import StepOption
    from packing_services.utils.timing import measure_time

    constraints = problem.constraints
    params = dict(problem.algorithm.parameters)
    budget = InformationBudget.from_parameters(params)
    session = ExtremePointOnlineSession(problem.containers, selection=resolve_selection(params))
    mask = ValidatorMask(problem, min_support_ratio=support_threshold(params, constraints.basic_stability))
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
    unpacked: list[Any] = []
    fallback_steps = 0
    multi_candidate_steps = 0
    decisions = 0
    discards = 0
    metadata = METADATA.model_copy(
        update={
            "name": TEACHER_ALGORITHM,
            "display_name": "Teacher receding horizon EP",
            "description": (
                "Rollout secuencial de receding_horizon_ep. "
                "La simulación interna ve el resto de la cola y se restaura antes del commit."
            ),
        }
    )
    with measure_time() as elapsed:
        while remaining:
            select_s, _observe_p = budget.window(len(remaining))
            selectable = remaining[:select_s]
            options: list[Any] = []
            for buffer_index, item in enumerate(selectable):
                for candidate in session.candidates(item, constraints):
                    if mask.allows(candidate, item, session, constraints):
                        options.append(StepOption(item=item, candidate=candidate, buffer_index=buffer_index))
            if not options:
                skipped = remaining.pop(0)
                unpacked.append(UnpackedItem(item_id=skipped.id, reason=NO_CANDIDATE_REASON))
                discards += 1
                continue
            before = _fingerprint(session)
            packed_before = len(session.packed)
            chosen_index, used_fallback = teacher_decision(
                options,
                remaining=remaining,
                session=session,
                constraints=constraints,
                mask=mask,
            )
            if _fingerprint(session) != before or len(session.packed) != packed_before:
                raise ProbeError("la simulación del teacher no restauró el estado")
            if chosen_index is None or not 0 <= int(chosen_index) < len(options):
                raise ProbeError("el teacher no devolvió una candidata del conjunto legal")
            if used_fallback:
                fallback_steps += 1
            if len(options) > 1:
                multi_candidate_steps += 1
            chosen = options[int(chosen_index)]
            session.commit(chosen.candidate, chosen.item)
            if len(session.packed) != packed_before + 1:
                raise ProbeError("el commit real no avanzó una sola colocación")
            decisions += 1
            remaining = [item for item in remaining if item.id != chosen.item.id]
    solution = build_solution(
        problem=problem,
        metadata=metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=elapsed.seconds,
    )
    diagnostics = {
        "teacher": TEACHER_NAME,
        "fallback_steps": fallback_steps,
        "multi_candidate_steps": multi_candidate_steps,
        "decisions": decisions,
        "discards": discards,
        "n_packed": len(session.packed),
        "n_unpacked": len(unpacked),
        "observes_remaining_queue": True,
        "same_observability_as_greedy": False,
        "physical_stability_verified": None,
    }
    return solution, diagnostics


def build_teacher_problem(orders: dict[str, Any], order_id: str) -> Any:
    prepare_imports()
    from problems import order_to_problem

    return order_to_problem(
        orders,
        order_id,
        lookahead_p=1,
        select_s=1,
        algorithm_name=TEACHER_ALGORITHM,
        model_path=None,
    )


def capture_teacher_case(
    orders: dict[str, Any],
    order_id: str,
    *,
    dataset_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    problem = build_teacher_problem(orders, order_id)
    snapshot = problem_snapshot(problem)
    solution, diagnostics = run_teacher_rollout(problem)
    document = capture_document(
        problem,
        solution,
        method="teacher",
        order_id=order_id,
        orders_path=dataset_path,
        orders_sha256=sha256_file(dataset_path) if dataset_path.is_file() else "",
        checkpoint_path=dataset_path,
    )
    return snapshot, document, diagnostics


def _finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def assess_comparator(
    packing_dir: Path,
    orders: list[dict[str, Any]],
    *,
    expected_digest: str | None = None,
    expected_code: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Lee los 50 heurísticos guardados. No vuelve a ejecutar la heurística."""

    issues: list[str] = []
    root = packing_dir.expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        issues.append("falta el manifiesto del packing")
        manifest: dict[str, Any] = {}
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "complete":
            issues.append("el packing heurístico no está complete")
    recorded = []
    seen: set[str] = set()
    for order in orders:
        order_id = order["order_id"]
        target = order["target"]
        case_dir = root / "cases" / f"heuristic__{order_id}"
        result_path = case_dir / "result.json"
        input_path = case_dir / "input.json"
        if not result_path.is_file() or not input_path.is_file():
            issues.append(f"falta el heurístico de {order_id}")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        snapshot = json.loads(input_path.read_text(encoding="utf-8"))
        if order_id in seen:
            issues.append(f"pedido repetido: {order_id}")
        seen.add(order_id)
        if result.get("order_id") != order_id or result.get("role") != "heuristic" or result.get("seed") not in (None,):
            issues.append(f"la fila heurística no corresponde al pedido: {order_id}")
        if result.get("target") != target:
            issues.append(f"el target heurístico no coincide: {order_id}")
        if result.get("physical_stability_verified") is not None:
            issues.append(f"el heurístico declara estabilidad física: {order_id}")
        utility = result.get("effective_u_geom")
        if not _finite(utility):
            issues.append(f"U_geom heurístico no finito: {order_id}")
        elif result.get("failure") and float(utility) != 0:
            issues.append(f"un fallo heurístico no entra con U_geom 0: {order_id}")
        if snapshot.get("lookahead_p") != 1 or snapshot.get("select_s") != 1:
            issues.append(f"p o s del heurístico no son 1: {order_id}")
        if snapshot.get("algorithm") != "online_3d_bpp_heuristic" or snapshot.get("model_path") is not None:
            issues.append(f"el comparador no es GreedyBestFit sin modelo: {order_id}")
        if snapshot.get("sort_strategy") != "input_order" or snapshot.get("selection") != "best_fit":
            issues.append(f"el orden o la selección del heurístico cambian: {order_id}")
        flags = snapshot.get("constraints") or {}
        for key, value in EXPECTED_FLAGS.items():
            if flags.get(key) is not value:
                issues.append(f"la restricción {key} del heurístico cambia: {order_id}")
        identity, length, width, height = TARGET_BOXES[target]
        container = (snapshot.get("containers") or [{}])[0]
        if container.get("id") != identity or (container.get("length_mm"), container.get("width_mm"), container.get("height_mm")) != (length, width, height):
            issues.append(f"el contenedor heurístico no es el del target: {order_id}")
        if not (case_dir / "audit.json").is_file() or not (case_dir / "capture.json").is_file():
            issues.append(f"el heurístico no conserva captura y auditoría: {order_id}")
        recorded.append(
            {
                "order_id": order_id,
                "result_sha256": sha256_file(result_path),
                "input_sha256": sha256_file(input_path),
                "effective_u_geom": result.get("effective_u_geom"),
            }
        )
    if seen != {order["order_id"] for order in orders}:
        issues.append("los pedidos heurísticos no son exactamente la muestra")
    digest_payload = json.dumps(recorded, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    import hashlib

    digest = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
    if expected_digest is not None and digest != expected_digest:
        issues.append("el hash del comparador no coincide con el protocolo")
    live_code = code_sha256()
    manifest_code = manifest.get("packing_code_sha256") or {}
    for relative in ("paper/tools/ablation_pack.py", "paper/tools/ablation_worker.py"):
        if manifest_code.get(relative) != live_code.get(relative):
            issues.append(f"el código que escribió el heurístico ya no coincide: {relative}")
    if expected_code is not None:
        for relative, expected in expected_code.items():
            if live_code.get(relative) != expected:
                issues.append(f"el código relevante cambió: {relative}")
    return {
        "accepted": not issues,
        "issues": issues,
        "n": len(recorded),
        "digest": digest,
        "records": recorded,
        "code_sha256": live_code,
    }


def compare_teacher_to_heuristic(
    teacher_rows: list[dict[str, Any]],
    heuristic_rows: list[dict[str, Any]],
    orders: list[dict[str, Any]],
) -> dict[str, Any]:
    """Media de 50 diferencias. No trata el resultado como confirmación."""

    teacher = {row["order_id"]: row for row in teacher_rows}
    heuristic = {row["order_id"]: row for row in heuristic_rows}
    if set(teacher) != {order["order_id"] for order in orders} or set(heuristic) != set(teacher):
        raise ProbeError("la comparación no tiene exactamente los pedidos de la muestra")
    if len(teacher) != len(teacher_rows) or len(heuristic) != len(heuristic_rows):
        raise ProbeError("hay pedidos duplicados en la comparación")
    deltas = []
    by_target: dict[str, list[float]] = {}
    wins = ties = losses = 0
    failure_types: dict[str, int] = {}
    fallback_orders = 0
    multi_candidate_orders = 0
    for order in orders:
        order_id = order["order_id"]
        teacher_row = teacher[order_id]
        heuristic_row = heuristic[order_id]
        for row, label in ((teacher_row, "teacher"), (heuristic_row, "heuristic")):
            utility = row.get("effective_u_geom")
            if not _finite(utility):
                raise ProbeError(f"U_geom no finito: {label} {order_id}")
            if row.get("failure") and float(utility) != 0:
                raise ProbeError(f"un fallo no entra con U_geom 0: {label} {order_id}")
            for kind in row.get("failure_types") or []:
                failure_types[f"{label}:{kind}"] = failure_types.get(f"{label}:{kind}", 0) + 1
        delta = float(teacher_row["effective_u_geom"]) - float(heuristic_row["effective_u_geom"])
        deltas.append(delta)
        by_target.setdefault(order["target"], []).append(delta)
        if delta > TIE_EPS:
            wins += 1
        elif delta < -TIE_EPS:
            losses += 1
        else:
            ties += 1
        if int(teacher_row.get("fallback_steps") or 0) > 0:
            fallback_orders += 1
        if int(teacher_row.get("multi_candidate_steps") or 0) > 0:
            multi_candidate_orders += 1
    mean_delta = sum(deltas) / len(deltas)
    return {
        "confirmatory": False,
        "not_upper_bound": True,
        "n_orders": len(orders),
        "mean_teacher_minus_greedy": mean_delta,
        "by_target": {target: sum(values) / len(values) for target, values in sorted(by_target.items())},
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "failure_types": failure_types,
        "orders_with_fallback": fallback_orders,
        "orders_with_multi_candidate_decisions": multi_candidate_orders,
        "time_is_diagnostic_only": True,
        "physical_stability_verified": None,
        "interpretation": _interpretation(mean_delta),
    }


def _interpretation(mean_delta: float) -> str:
    if mean_delta > 0:
        return (
            "Hay ventaja media observada. Cabe investigar si esa ventaja puede aprenderse "
            "con la observación limitada del actor."
        )
    return (
        "No hay ventaja media observada. No justifica otra campaña BC que solo imite este teacher "
        "sin revisar antes sus etiquetas u objetivo."
    )


def run_probe_stage(
    *,
    protocol: dict[str, Any],
    comparator_dir: Path,
    dataset_path: Path,
    output_dir: Path,
    command: list[str],
) -> dict[str, Any]:
    """Cincuenta teachers. No relanza la heurística si el comparador guardado es válido."""

    orders = development_orders()
    report = assess_comparator(
        comparator_dir,
        orders,
        expected_digest=protocol["comparator"]["digest"],
        expected_code=protocol["comparator"]["code_sha256"],
    )
    output = output_dir.expanduser().resolve()
    if output.exists():
        raise ProbeError("la carpeta de salida ya existe")
    output.mkdir()
    manifest: dict[str, Any] = {
        "stage": "teacher_probe",
        "status": "blocked" if not report["accepted"] else "running",
        "confirmatory": False,
        "packing_executed": False,
        "command": command,
        "comparator_accepted": report["accepted"],
        "issues": report["issues"],
        "timeout_seconds": TIMEOUT_SECONDS,
        "attempts": 1,
        "device": "cpu",
    }
    atomic_write_json(output / "manifest.json", manifest)
    if not report["accepted"]:
        raise ProbeError("el comparador heurístico no es reutilizable")
    dataset = dataset_path.expanduser().resolve()
    if sha256_file(dataset) != dataset_sha256_expected():
        manifest["status"] = "incomplete"
        manifest["error"] = "el hash del dataset no es el del protocolo geométrico"
        atomic_write_json(output / "manifest.json", manifest)
        raise ProbeError(manifest["error"])
    prepare_imports()
    from splits import load_orders

    loaded = load_orders(dataset)
    snapshots = {order["order_id"]: problem_snapshot(build_teacher_problem(loaded, order["order_id"])) for order in orders}
    cases = [
        {"order_id": order["order_id"], "target": order["target"], "dataset": str(dataset)}
        for order in orders
    ]
    try:
        rows = execute_teacher_cases(cases, snapshots, output)
        heuristic_rows = []
        for order in orders:
            heuristic_rows.append(
                json.loads((comparator_dir / "cases" / f"heuristic__{order['order_id']}" / "result.json").read_text(encoding="utf-8"))
            )
        summary = compare_teacher_to_heuristic(rows, heuristic_rows, orders)
        atomic_write_json(output / "comparison.json", summary)
        manifest["status"] = "complete"
        manifest["packing_executed"] = True
        manifest["mean_teacher_minus_greedy"] = summary["mean_teacher_minus_greedy"]
    except Exception as exc:
        manifest["status"] = "incomplete"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        atomic_write_json(output / "manifest.json", manifest)
        raise
    atomic_write_json(output / "manifest.json", manifest)
    return manifest


def execute_teacher_cases(
    cases: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    output_dir: Path,
    *,
    timeout_s: float = TIMEOUT_SECONDS,
    worker: Worker | None = None,
) -> list[dict[str, Any]]:
    """Un proceso por pedido. Un fallo de worker continúa; un error interno se propaga."""

    import subprocess
    import sys

    from pilot_execute import invoke_worker
    from pilot_metrics import evaluate_outcome

    rows: list[dict[str, Any]] = []
    worker_script = Path(__file__).resolve().parent / "teacher_probe_worker.py"
    for case in cases:
        order_id = case["order_id"]
        case_dir = output_dir / "cases" / order_id
        if (case_dir / "result.json").exists():
            raise ProbeError(f"el pedido {order_id} ya existe; no hay reintento")
        case_dir.mkdir(parents=True, exist_ok=True)
        snapshot = snapshots.get(order_id)
        if snapshot is None:
            raise ProbeError(f"no hay snapshot independiente para {order_id}")
        atomic_write_json(case_dir / "input.json", snapshot)
        job = {
            "order_id": order_id,
            "target": case["target"],
            "dataset": case["dataset"],
            "lookahead_p": 1,
            "select_s": 1,
            "attempts": 1,
        }
        if worker is None:
            outcome = invoke_worker(
                job,
                case_dir=case_dir,
                timeout_s=timeout_s,
                command=[
                    sys.executable,
                    str(worker_script),
                    "--job",
                    str(case_dir / "job.json"),
                    "--result",
                    str(case_dir / "worker_result.partial"),
                ],
            )
        else:
            try:
                outcome = worker(job)
            except subprocess.TimeoutExpired:
                outcome = {
                    "status": "timeout",
                    "error": f"timeout de {timeout_s} segundos",
                    "worker_failure": "timeout",
                    "attempts": 1,
                    "duration_seconds": float(timeout_s),
                    "capture": None,
                }
            except Exception as exc:
                outcome = {
                    "status": "crash",
                    "error": f"{type(exc).__name__}: {exc}",
                    "worker_failure": "crash",
                    "attempts": 1,
                    "duration_seconds": None,
                    "capture": None,
                }
        if not isinstance(outcome, dict):
            raise ProbeError("el evaluador recibió un resultado que no es un objeto")
        volume = float(snapshot["containers"][0]["volume_mm3"])
        row = evaluate_outcome(
            outcome,
            order_id=order_id,
            method="teacher",
            target=case["target"],
            container_volume_mm3=volume,
            run_id="teacher-probe",
            snapshot=snapshot,
        )
        diagnostics = outcome.get("diagnostics") if isinstance(outcome.get("diagnostics"), dict) else {}
        row["fallback_steps"] = int(diagnostics.get("fallback_steps") or 0)
        row["multi_candidate_steps"] = int(diagnostics.get("multi_candidate_steps") or 0)
        row["failure"] = bool(row["failure_types"])
        row["physical_stability_verified"] = None
        if row["failure"]:
            row["effective_u_geom"] = 0.0
        audit = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
        atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
        if isinstance(outcome.get("capture"), dict):
            atomic_write_json(case_dir / "capture.json", outcome["capture"])
        atomic_write_json(case_dir / "audit.json", audit)
        atomic_write_json(case_dir / "result.json", row)
        rows.append(row)
    return rows
