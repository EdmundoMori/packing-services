"""Evalúa una vez los seis modelos en los doce pedidos de development.

No entrena, no elige semilla y no abre el test final.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import torch

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
STUDY = HERE.parent
for _entry in (str(PAPER_TOOLS), str(HERE)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from actor_features import FEATURE_NAMES  # noqa: E402
from campaign import directory_must_be_new, file_sha256, recompute_u  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from model_spec import TRAINING_CONFIG  # noqa: E402
from packing_analysis import (  # noqa: E402
    SEEDS,
    aggregate_seeds,
    apply_gate,
    case_key,
    classify_episode,
    planned_cases,
    seed_report,
)
from pilot_common import REPO_ROOT, TIMEOUT_SECONDS, atomic_write_json, sha256_file  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import contrast_capture  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402

EXPECTED_PROTOCOL_SHA256 = "5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946"
EXPECTED_HEAD = "83b5e1c59808bd761f4c6fc47234c7dc232468d1"
EXPECTED_DATASET_SHA256 = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
WORKERS = 4
CODE_FILES = (
    "paper/studies/counterfactual_ranking/tools/actor_features.py",
    "paper/studies/counterfactual_ranking/tools/actor_policy.py",
    "paper/studies/counterfactual_ranking/tools/learning_worker.py",
    "paper/studies/counterfactual_ranking/tools/packing_analysis.py",
    "paper/studies/counterfactual_ranking/tools/run_learning_packing.py",
    "paper/tools/compact_study.py",
    "paper/tools/audit_internal_solution.py",
)
CHECKPOINT_SHA256 = {
    "classification_seed_11.pt": "6a5181fc303867c396048a66d5e84e290bd7926acb89a2a52db9e9a26bf7f647",
    "classification_seed_23.pt": "a7bc0e0e237d10587e9dd0bb6657aabd756975b665db27357b9d8a6e141de282",
    "classification_seed_37.pt": "169c2494ad124681aff2332b0872529b6b5e8c2812ead76fb37acdc93b558dbb",
    "preferences_seed_11.pt": "101ceaead264699be75283bef9e7ef62c4a8ae139316be370c2d4463975da617",
    "preferences_seed_23.pt": "3e646e889446ee00592816c895d39c7f48bba1318fc046bc578a958149b9db62",
    "preferences_seed_37.pt": "94c532b5dd57e936d9b797b1f5e10bd0bfd4f37964898b03f88f31f7ef2c0223",
}


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def _audit(document: dict[str, Any]) -> dict[str, Any]:
    import importlib.util

    path = PAPER_TOOLS / "audit_internal_solution.py"
    spec = importlib.util.spec_from_file_location("paper_tools_audit_internal_solution_packing", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_document(document)


def development_orders(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    orders = []
    for target in ("euro-pallet", "rollcontainer"):
        orders.extend(protocol["splits"][target]["development"])
    by_id = {order["order_id"]: order for order in orders}
    selected = [by_id[order_id] for order_id in protocol["execution_order"] if order_id in by_id]
    if len(selected) != 12 or len(by_id) != 12:
        raise SystemExit("bloqueo: development no tiene doce pedidos")
    return selected


def _check_checkpoints(stats: dict[str, Any]) -> None:
    verification = json.loads((STUDY / "training_verification.json").read_text(encoding="utf-8"))
    recorded = {row["checkpoint"]: row for row in verification["checkpoints"]}
    if set(recorded) != set(CHECKPOINT_SHA256):
        raise SystemExit("bloqueo: la verificación no lista los seis checkpoints")
    root = STUDY / "learning_training" / "checkpoints"
    for name, expected in CHECKPOINT_SHA256.items():
        path = root / name
        digest = file_sha256(path)
        if digest != expected or recorded[name]["sha256"] != expected:
            raise SystemExit(f"bloqueo: el hash de {name} no coincide")
        if recorded[name]["epoch"] != 40 or recorded[name]["logits_match"] is not True:
            raise SystemExit(f"bloqueo: {name} no es la época 40 verificada")
        blob = torch.load(path, map_location="cpu", weights_only=False)
        if int(blob["epoch"]) != 40:
            raise SystemExit(f"bloqueo: {name} no guarda la época 40")
        if blob["arm"] != recorded[name]["arm"] or int(blob["seed"]) != int(recorded[name]["seed"]):
            raise SystemExit(f"bloqueo: brazo o semilla de {name}")
        if blob["contract"] != "counterfactual-actor-v1" or list(blob["feature_names"]) != list(FEATURE_NAMES):
            raise SystemExit(f"bloqueo: el contrato de {name} no tiene 17 columnas")
        if list(blob["normalization"]["mean"]) != list(stats["mean"]) or list(blob["normalization"]["scale"]) != list(stats["scale"]):
            raise SystemExit(f"bloqueo: {name} no usa la normalización de train")
    campaign = json.loads((STUDY / "learning_training" / "campaign.json").read_text(encoding="utf-8"))
    if campaign.get("seed_selected") is not False:
        raise SystemExit("bloqueo: la campaña de ajuste seleccionó semilla")


def _provenance() -> str:
    aborted = STUDY / "learning_training_aborted_missing_checkpoint_dir"
    campaign = json.loads((aborted / "campaign.json").read_text(encoding="utf-8"))
    manifest = json.loads((aborted / "manifest.json").read_text(encoding="utf-8"))
    complete = json.loads((STUDY / "learning_training" / "manifest.json").read_text(encoding="utf-8"))
    return "\n".join(
        [
            "# Procedencia del intento abortado",
            "",
            "Hay dos registros distintos. `learning_training_aborted_missing_checkpoint_dir/` es un intento incompleto. `learning_training/` es una campaña posterior que volvió a construir los modelos.",
            "",
            f"El intento abortado terminó en {campaign['elapsed_seconds']} s con estado `{campaign['status']}`. Las tres semillas 11, 23 y 37 registran el mismo error: `{campaign['runs'][0]['error']}`. Esa frase es la de `torch.save` cuando el directorio padre no existe. No hay historiales, ranking ni checkpoints: `checkpoints` de su verificación está vacío.",
            "",
            "Los hashes de inicialización y de permutaciones de las tres semillas coinciden con los de la campaña completa. Esos hashes se calculan antes del bucle de cada brazo. El intento abortado no guardó pesos ni estado de Adam.",
            "",
            f"El hash de `train_loop.py` es el mismo en los dos manifiestos (`{manifest['code_sha256']['paper/studies/counterfactual_ranking/tools/train_loop.py']}`). El de `run_learning_training.py` no: el abortado tiene `{manifest['code_sha256']['paper/studies/counterfactual_ranking/tools/run_learning_training.py']}` y la campaña completa `{complete['code_sha256']['paper/studies/counterfactual_ranking/tools/run_learning_training.py']}`. El bloque `config` de los dos manifiestos es idéntico. El fuente abortado no está en git, así que el diff exacto queda desconocido. El ejecutor que sobrevivió crea el directorio de checkpoints inmediatamente antes de `torch.save`, y esa llamada está después de `train_arm`.",
            "",
            "Si en el fuente abortado el orden era el mismo, cada semilla habría dado 40 pasos de Adam en classification y habría fallado al guardar, sin llegar a preferences. Las marcas de tiempo entre semillas son de unos 0,7–0,9 s. La campaña completa tardó varios segundos por semilla. Con esa evidencia no se puede afirmar que los pasos de Adam ocurrieran. Tampoco se puede afirmar que no ocurrieran. Queda desconocido.",
            "",
            "No hay ranking ni historial en el intento abortado. Si alguien inspeccionó métricas en la salida estándar antes del relanzamiento, no quedó registro. La campaña completa no parte de pesos guardados: no existían. Su proceso nuevo llama a la inicialización documentada, crea un Adam nuevo dentro de `train_arm` y escribe los seis checkpoints de la época 40. Es un reinicio limpio de los artefactos, no una continuación del intento abortado, y tampoco es una campaña que no se hubiera vuelto a lanzar.",
            "",
            "Los hiperparámetros registrados no cambiaron. Lo que sí cambió, en el código que quedó, es la creación del directorio antes de guardar.",
            "",
        ]
    )


def _case_dir(output: Path, order_id: str, label: str) -> Path:
    return output / "cases" / order_id / label


def _label(arm: str, seed: int | None) -> str:
    if arm == "greedy":
        return "greedy"
    return f"{arm}_seed_{seed}"


def _finish_case(job: dict[str, Any], outcome: dict[str, Any], snapshot: dict[str, Any], started_audit: float) -> dict[str, Any]:
    capture = outcome.get("capture") if isinstance(outcome.get("capture"), dict) else None
    audit: dict[str, Any] | None = None
    contrast: dict[str, Any] | None = None
    raw = None
    status = str(outcome.get("status") or "crash")
    evaluator_exception = None
    try:
        if capture is not None:
            audit = _audit(capture)
            contrast = contrast_capture(capture, snapshot, order_id=job["order_id"], method=job["arm"])
            raw = recompute_u(capture)
            audited_volume = None
            per_container = audit.get("per_container") if isinstance(audit, dict) else None
            if isinstance(per_container, list) and per_container:
                audited_volume = float(per_container[0]["packed_volume_mm3"]) / float(per_container[0]["bin_volume_mm3"])
            if raw is not None and audited_volume is not None and abs(raw - audited_volume) > 1e-9:
                status = "ok"
                audit["internal_geometry_valid"] = False
                audit.setdefault("errors", []).append("U_geom recalculada no coincide con la auditoría")
    except Exception as exc:
        evaluator_exception = f"{type(exc).__name__}: {exc}"
        status = "evaluator_error"
    if evaluator_exception is not None:
        classified = {
            "method_failure": False,
            "evaluator_error": True,
            "geometry_invalid": False,
            "input_mismatch": False,
            "effective_u_geom": None,
            "raw_u_geom": raw,
            "in_denominator": False,
            "physical_stability_verified": None,
        }
    else:
        classified = classify_episode(
            status=status,
            raw_u_geom=raw,
            geometry_valid=bool(audit and audit.get("internal_geometry_valid")),
            contrast_matches=bool(contrast and contrast.get("matches")),
        )
    timings = dict(outcome.get("timings") or {}) if isinstance(outcome.get("timings"), dict) else {}
    timings["process_wall_seconds"] = outcome.get("duration_seconds")
    timings["audit_and_write_seconds"] = time.perf_counter() - started_audit
    timings["process_wall_is_not_policy_latency"] = True
    row = {
        "key": job["key"],
        "order_id": job["order_id"],
        "target": job["target"],
        "arm": job["arm"],
        "seed": job["seed"],
        "label": job["label"],
        "worker_status": outcome.get("status"),
        "error": evaluator_exception or outcome.get("error"),
        "checkpoint": job.get("checkpoint"),
        **classified,
        "n_packed": None if audit is None else audit.get("n_packed"),
        "n_unpacked": None if audit is None else audit.get("n_unpacked"),
        "timings": timings,
        "physical_stability_verified": None,
    }
    case_dir = Path(job["case_dir"])
    atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
    if capture is not None:
        atomic_write_json(case_dir / "capture.json", capture)
    atomic_write_json(case_dir / "audit.json", {"geometry": audit, "input_contrast": contrast, "evaluator_exception": evaluator_exception})
    atomic_write_json(case_dir / "result.json", row)
    return row


def _run_case(job: dict[str, Any]) -> dict[str, Any]:
    case_dir = Path(job["case_dir"])
    prepare_imports()
    from splits import load_orders

    loaded = load_orders(Path(job["dataset"]))
    problem = build_compact_problem(loaded, job["order_id"])
    snapshot = problem_snapshot(problem)
    atomic_write_json(case_dir / "input.json", snapshot)
    payload = {
        "order_id": job["order_id"],
        "dataset": job["dataset"],
        "dataset_sha256": job["dataset_sha256"],
        "arm": job["arm"],
        "seed": job["seed"],
        "attempts": 1,
        "checkpoint": job.get("checkpoint"),
        "normalization": job.get("normalization"),
    }
    outcome = invoke_worker(
        payload,
        case_dir=case_dir,
        timeout_s=TIMEOUT_SECONDS,
        command=[
            sys.executable,
            str(HERE / "learning_worker.py"),
            "--job",
            str(case_dir / "job.json"),
            "--result",
            str(case_dir / "worker_result.partial"),
        ],
    )
    try:
        return _finish_case(job, outcome, snapshot, time.perf_counter())
    except Exception as exc:
        row = {
            "key": job["key"],
            "order_id": job["order_id"],
            "target": job["target"],
            "arm": job["arm"],
            "seed": job["seed"],
            "label": job["label"],
            "worker_status": outcome.get("status"),
            "error": f"{type(exc).__name__}: {exc}",
            "method_failure": False,
            "evaluator_error": True,
            "geometry_invalid": False,
            "input_mismatch": False,
            "effective_u_geom": None,
            "raw_u_geom": None,
            "in_denominator": False,
            "physical_stability_verified": None,
            "timings": {},
        }
        atomic_write_json(case_dir / "audit.json", {"geometry": None, "input_contrast": None, "evaluator_exception": row["error"]})
        atomic_write_json(case_dir / "result.json", row)
        return row


def _timing_means(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    keys = (
        "startup_seconds",
        "packing_loop_seconds",
        "decision_seconds",
        "capture_build_seconds",
        "audit_and_write_seconds",
        "process_wall_seconds",
    )
    report = {}
    for key in keys:
        values = []
        for row in rows:
            value = (row.get("timings") or {}).get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        report[key] = sum(values) / len(values) if values else None
    report["candidate_generation_seconds"] = None
    report["note"] = "process_wall_seconds incluye el proceso aislado y no es la latencia de la política. La campaña puede solapar casos; esa pared no compara eficiencia."
    return report


def _verify(output: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues = []
    keys = [row["key"] for row in rows]
    if len(keys) != 84 or len(set(keys)) != 84:
        issues.append("no hay 84 claves únicas")
    for row in rows:
        capture_path = output / "cases" / row["order_id"] / row["label"] / "capture.json"
        if row["evaluator_error"]:
            continue
        if row["method_failure"]:
            if row["effective_u_geom"] != 0.0:
                issues.append(f"un fallo de método no entra como 0: {row['key']}")
            continue
        if not capture_path.is_file():
            issues.append(f"falta captura auditada: {row['key']}")
            continue
        capture = json.loads(capture_path.read_text(encoding="utf-8"))
        recomputed = recompute_u(capture)
        if recomputed is None or abs(float(recomputed) - float(row["effective_u_geom"])) > 1e-12:
            issues.append(f"U_geom no se reproduce: {row['key']}")
        if capture.get("physical_stability_verified") is not None:
            issues.append(f"estabilidad física alterada: {row['key']}")
    return {"ok": not issues, "issues": issues, "n_cases": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    protocol_path = Path(args.protocol)
    protocol_sha = file_sha256(protocol_path)
    if protocol_sha != EXPECTED_PROTOCOL_SHA256:
        raise SystemExit("bloqueo: el protocolo congelado cambió")
    head = _git_head()
    if head != EXPECTED_HEAD:
        raise SystemExit(f"bloqueo: HEAD es {head}")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    dataset = Path(protocol["dataset"]["path"])
    dataset_sha = sha256_file(dataset)
    if dataset_sha != EXPECTED_DATASET_SHA256 or dataset_sha != protocol["dataset"]["sha256"]:
        raise SystemExit("bloqueo: el dataset cambió")
    if list(protocol["features"]["kept_columns"]) != list(FEATURE_NAMES):
        raise SystemExit("bloqueo: el contrato de columnas no coincide")
    stats = json.loads((STUDY / "learning_labels" / "normalization.json").read_text(encoding="utf-8"))
    _check_checkpoints(stats)
    gate = protocol["gate"]["advance_if_all"]
    expected_gate = [
        "media de preferencias menos clasificación >= 0.005",
        "preferencias menos clasificación positiva en al menos dos de tres semillas",
        "media de preferencias menos Greedy >= 0.01",
        "media de preferencias menos Greedy >= 0 en cada target",
        "integridad del evaluador y cobertura suficientes: los 12 pedidos de desarrollo con episodio auditado para las tres semillas y para Greedy, sin tratar un fallo geométrico como retorno 0, con physical_stability_verified null",
    ]
    if gate != expected_gate:
        raise SystemExit("bloqueo: la puerta congelada no coincide con el resumen; no se ejecuta")
    orders = development_orders(protocol)
    cases = planned_cases(orders)
    if len(cases) != 84:
        raise SystemExit("bloqueo: no salen 84 casos")
    output = Path(args.output)
    directory_must_be_new(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "provenance_aborted_attempt.md").write_text(_provenance(), encoding="utf-8")
    checkpoints = STUDY / "learning_training" / "checkpoints"
    jobs = []
    for case in cases:
        label = _label(case["arm"], case["seed"])
        checkpoint = None
        if case["arm"] != "greedy":
            checkpoint = str(checkpoints / f"{case['arm']}_seed_{case['seed']}.pt")
        jobs.append(
            {
                **case,
                "label": label,
                "case_dir": str(_case_dir(output, case["order_id"], label)),
                "dataset": str(dataset),
                "dataset_sha256": dataset_sha,
                "checkpoint": checkpoint,
                "normalization": None if case["arm"] == "greedy" else {"mean": stats["mean"], "scale": stats["scale"]},
            }
        )
    manifest = {
        "role": "manifiesto_previo_a_los_episodios",
        "episodes_started": False,
        "head": head,
        "protocol_sha256": protocol_sha,
        "dataset_sha256": dataset_sha,
        "normalization_sha256": file_sha256(STUDY / "learning_labels" / "normalization.json"),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "code_sha256": {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES},
        "orders": orders,
        "n_cases": 84,
        "seeds": list(SEEDS),
        "timeout_seconds": TIMEOUT_SECONDS,
        "workers": WORKERS,
        "workers_note": "El solapamiento solo afecta a la pared de la campaña. La latencia de cada política es decision_seconds, medida dentro de su proceso.",
        "gate_text": gate,
        "ranking_used_for_selection": False,
        "seed_selected": False,
        "training_executed": False,
        "final_test_selected": False,
        "physical_stability_verified": None,
        "config_reference": {
            "learning_rate": TRAINING_CONFIG["learning_rate"],
            "epochs": TRAINING_CONFIG["epochs"],
            "unchanged": True,
        },
    }
    atomic_write_json(output / "manifest.json", manifest)
    manifest["episodes_started"] = True
    atomic_write_json(output / "manifest.json", manifest)
    rows = []
    errors = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_run_case, job) for job in jobs]
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                continue
            rows.append(row)
            print(f"{row['key']} {row.get('worker_status')} {row.get('effective_u_geom')}", flush=True)
    rows.sort(key=lambda item: item["key"])
    expected = {case["key"] for case in cases}
    missing = sorted(expected.difference(row["key"] for row in rows))
    evaluator_errors = sum(1 for row in rows if row.get("evaluator_error")) + len(errors)
    denominator = [row for row in rows if row.get("in_denominator")]
    reports = []
    aggregate = None
    gate_result = None
    if not missing and evaluator_errors == 0 and len(denominator) == 84:
        reports = [seed_report(denominator, orders, seed) for seed in SEEDS]
        aggregate = aggregate_seeds(reports)
        gate_result = apply_gate(reports, evaluator_errors=0, missing_keys=0)
    else:
        gate_result = apply_gate([], evaluator_errors=evaluator_errors, missing_keys=len(missing))
    verification = _verify(output, rows)
    if not verification["ok"]:
        gate_result = apply_gate([], evaluator_errors=evaluator_errors + len(verification["issues"]), missing_keys=len(missing))
    document = {
        "role": "agregado_de_episodios",
        "n_cases": len(rows),
        "missing_keys": missing,
        "parent_errors": errors,
        "by_seed": reports,
        "aggregate": aggregate,
        "gate": gate_result,
        "timings": _timing_means(rows),
        "failures": {
            "method": sum(1 for row in rows if row.get("method_failure")),
            "evaluator": evaluator_errors,
        },
        "physical_stability_verified": None,
        "seed_selected": False,
        "elapsed_seconds": time.perf_counter() - started,
        "ranking_relation": "El ranking de etiquetas y estos episodios describen elecciones distintas. Sus diferencias no se atribuyen a una causa.",
    }
    atomic_write_json(output / "aggregate.json", document)
    atomic_write_json(
        STUDY / "packing_verification.json",
        {
            "role": "verificacion_de_episodios",
            "status": "completed" if gate_result["classification"] != "inconcluso" and verification["ok"] else "incomplete",
            "verification": verification,
            "gate": gate_result,
            "elapsed_seconds": time.perf_counter() - started,
            "physical_stability_verified": None,
            "final_test_selected": False,
            "training_executed": False,
        },
    )
    print(gate_result["classification"], time.perf_counter() - started)


if __name__ == "__main__":
    main()
