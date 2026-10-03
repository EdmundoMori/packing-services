"""Calibración congelada del selector compacto. No amplía la cuadrícula ni entrena."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_selector import (  # noqa: E402
    FORMULA,
    FORMULA_VERSION,
    GATE_MEAN_DELTA,
    choose_top,
    config_id,
    engineering_gate,
    grid_configurations,
    mean_effective,
)
from compact_study import build_compact_problem  # noqa: E402
from pilot_common import REPO_ROOT, TIE_EPS, TIMEOUT_SECONDS, atomic_write_json, sha256_file  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402
from pilot_problems import prepare_imports, problem_snapshot  # noqa: E402

PROTOCOL_16 = REPO_ROOT / "paper/protocols/16_compact_selector_study.json"
PROTOCOL_10 = REPO_ROOT / "paper/protocols/10_normalization_ablation.json"
PROTOCOL_07 = REPO_ROOT / "paper/protocols/07_independent_evaluation.json"
PROTOCOL_17 = REPO_ROOT / "paper/protocols/17_compact_calibration.json"
PROTOCOL_17_MD = REPO_ROOT / "paper/protocols/17_compact_calibration.md"
TRAIN_IDS = REPO_ROOT / "online_policy_ml/data/splits/train_order_ids_full.json"
OUTPUT = REPO_ROOT / "paper/results/17_compact_calibration"
DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
EXPECTED_DATASET_SHA = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
CODE_FILES = (
    "paper/tools/compact_selector.py",
    "paper/tools/compact_study.py",
    "paper/tools/compact_worker.py",
    "paper/tools/run_compact_calibration.py",
    "src/packing_services/online/policies.py",
    "src/packing_services/online/session.py",
    "src/packing_services/online/loop.py",
)
SMOKE_GREEDY = REPO_ROOT / "paper/results/16_baseline_smoke"
WORKERS = min(4, os.cpu_count() or 1)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head() -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _signature(snapshot: dict[str, Any], target: str) -> str:
    items = [
        [
            item["length_mm"],
            item["width_mm"],
            item["height_mm"],
            item["weight_kg"],
            item["allowed_orientations"],
        ]
        for item in snapshot["items"]
    ]
    raw = json.dumps({"target": target, "items": items}, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _orders() -> dict[str, Any]:
    protocol_16 = _load(PROTOCOL_16)
    protocol_10 = _load(PROTOCOL_10)
    protocol_07 = _load(PROTOCOL_07)["orders"]
    euro = list(protocol_16["future_selector"]["calibration"]["orders"]["euro-pallet"])
    roll = list(protocol_16["future_selector"]["calibration"]["orders"]["rollcontainer"])
    train = [{"order_id": order_id, "target": "euro-pallet", "split_list": "euro-pallet"} for order_id in euro]
    train += [{"order_id": order_id, "target": "rollcontainer", "split_list": "rollcontainer"} for order_id in roll]
    development = [
        {"order_id": row["order_id"], "target": row["target"], "position": row["position"]}
        for row in protocol_10["development_sample"]["execution_items"]
    ]
    return {
        "train": train,
        "development": development,
        "evaluation_ids": [row["order_id"] for row in protocol_07["items"]],
        "positive_exclusion_ids": list(protocol_07["positive_exclusion_ids"]),
        "full_train_ids": _load(TRAIN_IDS),
    }


def _validate(loaded: dict[str, Any], groups: dict[str, Any]) -> dict[str, Any]:
    train = groups["train"]
    development = groups["development"]
    train_ids = [row["order_id"] for row in train]
    dev_ids = [row["order_id"] for row in development]
    problems = []
    if len(train_ids) != 40 or len(set(train_ids)) != 40:
        problems.append("train no tiene 40 identidades únicas")
    if sum(row["target"] == "euro-pallet" for row in train) != 20 or sum(row["target"] == "rollcontainer" for row in train) != 20:
        problems.append("train no tiene 20 pedidos por target")
    if len(dev_ids) != 50 or len(set(dev_ids)) != 50:
        problems.append("desarrollo no tiene 50 identidades únicas")
    if sum(row["target"] == "euro-pallet" for row in development) != 25 or sum(row["target"] == "rollcontainer" for row in development) != 25:
        problems.append("desarrollo no tiene 25 pedidos por target")
    if set(train_ids) & set(dev_ids):
        problems.append("train y desarrollo comparten identidades")
    if set(train_ids) & set(groups["evaluation_ids"]):
        problems.append("train intersecta la evaluación 07")
    if set(train_ids) & set(groups["positive_exclusion_ids"]):
        problems.append("train intersecta positive_exclusion_ids")
    missing = [order_id for order_id in train_ids if order_id not in set(groups["full_train_ids"])]
    if missing:
        problems.append(f"train fuera de full.train: {missing}")
    signatures: dict[str, list[dict[str, str]]] = {}
    snapshots = {}
    for split, rows in (("train", train), ("development", development)):
        for row in rows:
            problem = build_compact_problem(loaded, row["order_id"])
            snapshot = problem_snapshot(problem)
            snapshots[(split, row["order_id"])] = snapshot
            digest = _signature(snapshot, row["target"])
            signatures.setdefault(digest, []).append({"split": split, "order_id": row["order_id"], "target": row["target"]})
    crosses = [rows for rows in signatures.values() if len({item["split"] for item in rows}) > 1]
    if crosses:
        problems.append(f"hay {len(crosses)} firmas compartidas entre train y desarrollo")
    return {"problems": problems, "crosses": crosses, "snapshots": snapshots, "n_signatures": len(signatures)}


def _published_cost() -> dict[str, Any]:
    walls = []
    loops = []
    for path in (SMOKE_GREEDY / "cases").glob("*/greedy/timings.json"):
        row = _load(path)
        if isinstance(row.get("process_wall_seconds"), (int, float)):
            walls.append(float(row["process_wall_seconds"]))
        if isinstance(row.get("packing_loop_seconds"), (int, float)):
            loops.append(float(row["packing_loop_seconds"]))
    consumed = 0.0
    counted = 0
    for root in (SMOKE_GREEDY, REPO_ROOT / "paper/results/16a_onlinebph_capture_smoke"):
        for path in root.glob("cases/*/*/timings.json"):
            row = _load(path)
            wall = row.get("process_wall_seconds")
            if isinstance(wall, (int, float)):
                consumed += float(wall)
                counted += 1
    mean_wall = sum(walls) / len(walls) if walls else None
    max_wall = max(walls) if walls else None
    planned = 40 + 50 + 32 * 40 + 3 * 50
    return {
        "smoke_greedy_n": len(walls),
        "smoke_greedy_mean_wall_seconds": mean_wall,
        "smoke_greedy_max_wall_seconds": max_wall,
        "smoke_greedy_mean_loop_seconds": (sum(loops) / len(loops)) if loops else None,
        "planned_cases": planned,
        "estimate_at_mean_wall_seconds": None if mean_wall is None else planned * mean_wall,
        "estimate_at_max_wall_seconds": None if max_wall is None else planned * max_wall,
        "consumed_process_wall_seconds_steps_16_and_16a": consumed,
        "consumed_timing_files": counted,
        "budget_seconds": 12 * 3600,
        "uncertainty": (
            "La media y el máximo salen de cinco Greedy de desarrollo. "
            "Un pedido más largo o el arranque por proceso pueden alejarse de esa muestra. "
            "No es una garantía."
        ),
    }


def _protocol_document(groups: dict[str, Any], cost: dict[str, Any], head: str) -> dict[str, Any]:
    grid = [{"a": a, "b": b, "c": c, "config_id": config_id(a, b, c)} for a, b, c in grid_configurations()]
    return {
        "schema_version": 1,
        "protocol_id": "17_compact_calibration",
        "status": "congelado antes de ejecutar",
        "reference_commit": head,
        "parent_protocol": "paper/protocols/16_compact_selector_study.json",
        "development_protocol": "paper/protocols/10_normalization_ablation.json",
        "dataset": str(DATASET),
        "dataset_sha256": EXPECTED_DATASET_SHA,
        "formula_version": FORMULA_VERSION,
        "formula": FORMULA,
        "definitions": {
            "contacto_normalizado": "(-rank_key[0]) / (2 * (l*w + l*h + w*h))",
            "techo_normalizado": "(z + h) / H",
            "incremento_altura_normalizado": "(max(altura_actual, z+h) - altura_actual) / H",
            "apoyo": "candidate.support_ratio",
            "altura_actual": "techo máximo de las cajas ya colocadas; 0 si el bin está vacío",
            "contact_is_stability_test": False,
        },
        "grid": grid,
        "n_configurations": len(grid),
        "grid_order": "lexicográfico por (a, b, c)",
        "train_orders": groups["train"],
        "development_orders": groups["development"],
        "signature_rule": (
            "SHA256 de JSON canónico con target y la secuencia de longitud, anchura, altura, "
            "peso y allowed_orientations del snapshot compacto, antes de colocar. "
            "El origen BED-BPP no trae un permiso por ítem; el permiso relevante es el de ese snapshot."
        ),
        "selection": {
            "train_mean": "media aritmética de U_geom efectivo de los 40 pedidos, fallos en 0",
            "train_tie": "(a, b, c) ascendente",
            "top_k": 3,
            "development_choice": "mayor media de U_geom efectivo entre las tres; empate por (a, b, c) ascendente",
            "gate_applies_only_to_chosen": True,
            "gate": {
                "A": GATE_MEAN_DELTA,
                "B": "media pareada euro-pallet >= 0",
                "C": "media pareada rollcontainer >= 0",
                "statistical_test": False,
            },
        },
        "execution": {
            "device": "cpu",
            "attempts": 1,
            "timeout_seconds": TIMEOUT_SECONDS,
            "online_bph": False,
            "training": False,
            "greedy_train": 40,
            "grid_train": 1280,
            "greedy_development": 50,
            "top3_development": 150,
            "maximum_cases": 1520,
            "workers": WORKERS,
        },
        "cost_estimate_before_execution": cost,
        "physical_stability_verified": None,
        "superiority_claimed": False,
        "confirmatory": False,
    }


def _write_protocol_md(document: dict[str, Any]) -> None:
    text = f"""# 17 — calibración del selector compacto

Congelado antes de empaquetar, sobre `{document["reference_commit"]}`. No modifica el protocolo 16 ni sus resultados.

La fórmula es `{document["formula"]}`, versión `{document["formula_version"]}`. El contacto sale de `-rank_key[0]` y no es una prueba de estabilidad. La cuadrícula tiene {document["n_configurations"]} configuraciones en orden lexicográfico. No se amplía después de ver resultados.

Train usa los 40 IDs ya guardados en el protocolo 16, primero los euro-pallet y después los rollcontainer, en el orden de cada lista. Desarrollo usa los 50 `execution_items` del protocolo 10, en ese orden.

La selección de train conserva los fallos en el denominador. Las tres primeras pasan a los 50 pedidos. La puerta A/B/C se aplica solo a la configuración elegida entre esas tres. No es una prueba estadística ni una comparación con OnlineBPH o PCT.

Presupuesto estimado antes de ejecutar: media de pared del smoke Greedy por {document["execution"]["maximum_cases"]} casos, y también el máximo de esos cinco. La incertidumbre queda en el JSON. `physical_stability_verified` permanece null.
"""
    PROTOCOL_17_MD.write_text(text, encoding="utf-8")


def prepare() -> int:
    if OUTPUT.exists():
        print("la carpeta de calibración ya existe", file=sys.stderr)
        return 2
    dataset_sha = sha256_file(DATASET)
    if dataset_sha != EXPECTED_DATASET_SHA:
        print("el hash del dataset no coincide", file=sys.stderr)
        return 2
    prepare_imports()
    from splits import load_orders

    groups = _orders()
    loaded = load_orders(DATASET)
    checked = _validate(loaded, groups)
    cost = _published_cost()
    head = _git_head()
    document = _protocol_document(groups, cost, head)
    document["identity_problems"] = checked["problems"]
    atomic_write_json(PROTOCOL_17, document)
    _write_protocol_md(document)
    OUTPUT.mkdir(parents=True)
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}
    smoke_code = _load(SMOKE_GREEDY / "preflight.json").get("code_sha256", {})
    relevant = (
        "paper/tools/compact_study.py",
        "paper/tools/compact_worker.py",
        "src/packing_services/online/policies.py",
        "src/packing_services/online/session.py",
        "src/packing_services/online/loop.py",
    )
    reuse = all(code.get(path) == smoke_code.get(path) for path in relevant)
    estimate = cost["estimate_at_max_wall_seconds"] or 0
    consumed = cost["consumed_process_wall_seconds_steps_16_and_16a"]
    fits = estimate + consumed <= cost["budget_seconds"]
    freeze = {
        "status": "bloqueado" if checked["problems"] or not fits else "congelado_antes_de_ejecutar",
        "reference_commit": head,
        "protocol": str(PROTOCOL_17),
        "protocol_sha256": sha256_file(PROTOCOL_17),
        "protocol_md_sha256": sha256_file(PROTOCOL_17_MD),
        "dataset_sha256": dataset_sha,
        "code_sha256": code,
        "origin_manifests": {
            "protocol_16_sha256": sha256_file(PROTOCOL_16),
            "protocol_10_sha256": sha256_file(PROTOCOL_10),
            "protocol_07_sha256": sha256_file(PROTOCOL_07),
            "train_ids_sha256": sha256_file(TRAIN_IDS),
            "smoke_preflight_sha256": sha256_file(SMOKE_GREEDY / "preflight.json"),
        },
        "signature_rule": document["signature_rule"],
        "n_signatures": checked["n_signatures"],
        "clone_crosses": checked["crosses"],
        "identity_problems": checked["problems"],
        "greedy_smoke_reuse": reuse,
        "greedy_smoke_reuse_reason": (
            "los hashes del código relevante coinciden con el smoke"
            if reuse
            else "compact_study.py o el worker cambiaron después del smoke; no se reutilizan sus U_geom"
        ),
        "cost_estimate_before_execution": cost,
        "budget_fits_at_max_smoke_wall": fits,
        "commands": {
            "prepare": ".venv/bin/python paper/tools/run_compact_calibration.py --prepare",
            "execute": ".venv/bin/python paper/tools/run_compact_calibration.py --execute",
        },
        "physical_stability_verified": None,
        "grid_executed": False,
    }
    atomic_write_json(OUTPUT / "freeze.json", freeze)
    if checked["problems"] or not fits:
        print(json.dumps({"problems": checked["problems"], "fits": fits, "estimate": estimate, "consumed": consumed}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": freeze["status"], "estimate_max_seconds": estimate, "consumed_seconds": consumed, "reuse": reuse}, ensure_ascii=False))
    return 0


def _case_dir(split: str, order_id: str, label: str) -> Path:
    return OUTPUT / "cases" / split / order_id / label


def _snapshot_for(snapshot: dict[str, Any], coefficients: dict[str, float] | None) -> dict[str, Any]:
    copied = dict(snapshot)
    if coefficients is not None:
        copied["algorithm"] = "compact_selector"
    return copied


def _run_case(job: dict[str, Any]) -> dict[str, Any]:
    split = job["split"]
    order_id = job["order_id"]
    label = job["label"]
    case_dir = _case_dir(split, order_id, label)
    result_path = case_dir / "result.json"
    if result_path.is_file():
        row = _load(result_path)
        row["resumed"] = True
        return row
    prepare_imports()
    from splits import load_orders

    loaded = load_orders(DATASET)
    problem = build_compact_problem(loaded, order_id)
    snapshot = problem_snapshot(problem)
    coefficients = job.get("coefficients")
    contrasted = _snapshot_for(snapshot, coefficients)
    payload = {
        "order_id": order_id,
        "dataset": str(DATASET),
        "dataset_sha256": EXPECTED_DATASET_SHA,
        "attempts": 1,
    }
    if coefficients is not None:
        payload["coefficients"] = coefficients
    outcome = invoke_worker(
        payload,
        case_dir=case_dir,
        timeout_s=TIMEOUT_SECONDS,
        command=[
            sys.executable,
            str(TOOLS / "compact_worker.py"),
            "--job",
            str(case_dir / "job.json"),
            "--result",
            str(case_dir / "worker_result.partial"),
        ],
    )
    started = time.perf_counter()
    row = evaluate_outcome(
        outcome,
        order_id=order_id,
        method="compact_selector" if coefficients is not None else "greedy",
        target=job["target"],
        container_volume_mm3=float(snapshot["containers"][0]["volume_mm3"]),
        run_id="17-compact-calibration",
        snapshot=contrasted,
    )
    recipe = (outcome.get("capture") or {}).get("recipe") if isinstance(outcome.get("capture"), dict) else {}
    if not isinstance(recipe, dict):
        recipe = {}
    if recipe.get("input_changed") is True:
        row["failure_types"] = list(dict.fromkeys([*(row.get("failure_types") or []), "input_changed"]))
    if coefficients is not None:
        observed = recipe.get("coefficients")
        expected = {"a": float(coefficients["a"]), "b": float(coefficients["b"]), "c": float(coefficients["c"])}
        if observed != expected or recipe.get("formula_version") != FORMULA_VERSION:
            row["failure_types"] = list(dict.fromkeys([*(row.get("failure_types") or []), "input_mismatch"]))
            row["input_mismatch"] = True
    row["physical_stability_verified"] = None
    if row.get("failure_types"):
        row["effective_u_geom"] = 0.0
    audit = row.pop("audits", {"status": outcome.get("status"), "error": outcome.get("error")})
    atomic_write_json(case_dir / "worker.json", {key: value for key, value in outcome.items() if key != "capture"})
    if isinstance(outcome.get("capture"), dict):
        atomic_write_json(case_dir / "capture.json", outcome["capture"])
    atomic_write_json(case_dir / "audit.json", audit)
    atomic_write_json(case_dir / "input.json", snapshot)
    atomic_write_json(case_dir / "result.json", row)
    timings = dict(outcome.get("timings") or {}) if isinstance(outcome.get("timings"), dict) else {}
    timings["process_wall_seconds"] = outcome.get("duration_seconds")
    timings["audit_and_write_seconds"] = time.perf_counter() - started
    atomic_write_json(case_dir / "timings.json", timings)
    row["label"] = label
    row["split"] = split
    row["timings"] = timings
    print(f"{split} {order_id} {label} {row.get('worker_status')} {row.get('effective_u_geom')}", flush=True)
    return row


def _jobs(rows: list[dict[str, Any]], split: str, labels: list[tuple[str, dict[str, float] | None]]) -> list[dict[str, Any]]:
    jobs = []
    for row in rows:
        for label, coefficients in labels:
            jobs.append(
                {
                    "split": split,
                    "order_id": row["order_id"],
                    "target": row["target"],
                    "label": label,
                    "coefficients": coefficients,
                }
            )
    return jobs


def _execute_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors = []
    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_run_case, job) for job in jobs]
        for future in as_completed(futures):
            try:
                rows.append(future.result())
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors[:5]))
    return rows


def _read_case(split: str, order_id: str, label: str) -> dict[str, Any]:
    path = _case_dir(split, order_id, label) / "result.json"
    if not path.is_file():
        raise RuntimeError(f"falta {path}")
    row = _load(path)
    timings_path = _case_dir(split, order_id, label) / "timings.json"
    row["timings"] = _load(timings_path) if timings_path.is_file() else {}
    row["order_id"] = order_id
    row["label"] = label
    return row


def _timing_means(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    keys = ("packing_loop_seconds", "startup_seconds", "capture_build_seconds", "audit_and_write_seconds", "process_wall_seconds")
    summary = {}
    for key in keys:
        values = [float(row["timings"][key]) for row in rows if isinstance(row.get("timings", {}).get(key), (int, float))]
        summary[key] = (sum(values) / len(values)) if values else None
        summary[f"n_{key}"] = len(values)
    return summary


def _failure_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        kinds = row.get("failure_types") or []
        if not kinds:
            counts["none"] = counts.get("none", 0) + 1
        for kind in kinds:
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def _paired(order_rows: list[dict[str, Any]], label: str, split: str) -> dict[str, Any]:
    deltas = []
    utilities = []
    greedy = []
    packed = []
    by_target: dict[str, list[float]] = {}
    records = []
    wins = ties = losses = 0
    for order in order_rows:
        selected = _read_case(split, order["order_id"], label)
        base = _read_case(split, order["order_id"], "greedy")
        delta = float(selected["effective_u_geom"]) - float(base["effective_u_geom"])
        deltas.append(delta)
        utilities.append(float(selected["effective_u_geom"]))
        greedy.append(float(base["effective_u_geom"]))
        packed.append(int(selected.get("n_packed") or 0))
        by_target.setdefault(order["target"], []).append(delta)
        if delta > TIE_EPS:
            wins += 1
        elif delta < -TIE_EPS:
            losses += 1
        else:
            ties += 1
        records.append(selected)
    ordered = sorted(deltas)
    median = ordered[len(ordered) // 2] if len(ordered) % 2 else (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
    return {
        "n": len(deltas),
        "mean_effective_u_geom": mean_effective(utilities),
        "mean_greedy_u_geom": mean_effective(greedy),
        "mean_delta": mean_effective(deltas),
        "median_delta": median,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "tie_eps": TIE_EPS,
        "by_target": {target: mean_effective(values) for target, values in by_target.items()},
        "failure_counts": _failure_counts(records),
        "n_packed_sum": sum(packed),
        "timings": _timing_means(records),
    }


def _train_table(train: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for a, b, c in grid_configurations():
        label = config_id(a, b, c)
        summary = _paired(train, label, "train")
        rows.append({"a": a, "b": b, "c": c, "config_id": label, "mean_effective_u_geom": summary["mean_effective_u_geom"], "summary": summary})
    return choose_top(rows, len(rows))


def execute() -> int:
    freeze_path = OUTPUT / "freeze.json"
    if not freeze_path.is_file():
        print("no hay congelación", file=sys.stderr)
        return 2
    freeze = _load(freeze_path)
    if freeze.get("status") != "congelado_antes_de_ejecutar":
        print("la congelación no autoriza la ejecución", file=sys.stderr)
        return 2
    code = {relative: sha256_file(REPO_ROOT / relative) for relative in CODE_FILES}
    if code != freeze["code_sha256"] or sha256_file(PROTOCOL_17) != freeze["protocol_sha256"]:
        print("el código o el protocolo cambiaron después de congelar", file=sys.stderr)
        return 2
    if sha256_file(DATASET) != EXPECTED_DATASET_SHA:
        print("el dataset cambió", file=sys.stderr)
        return 2
    protocol = _load(PROTOCOL_17)
    train = protocol["train_orders"]
    development = protocol["development_orders"]
    labels = [("greedy", None)] + [
        (row["config_id"], {"a": row["a"], "b": row["b"], "c": row["c"]}) for row in protocol["grid"]
    ]
    started = time.perf_counter()
    try:
        _execute_jobs(_jobs(train, "train", labels) + _jobs(development, "development", [("greedy", None)]))
        table = _train_table(train)
        recomputed = _train_table(train)
        if [row["config_id"] for row in table] != [row["config_id"] for row in recomputed]:
            raise RuntimeError("la tabla de train no se reproduce")
        if [row["mean_effective_u_geom"] for row in table] != [row["mean_effective_u_geom"] for row in recomputed]:
            raise RuntimeError("las medias de train no se reproducen")
        top = table[:3]
        atomic_write_json(
            OUTPUT / "train_table.json",
            {
                "ranked": table,
                "top3": [{"config_id": row["config_id"], "a": row["a"], "b": row["b"], "c": row["c"], "mean_effective_u_geom": row["mean_effective_u_geom"]} for row in top],
                "selection_reason": "mayor media de U_geom efectivo; empate por (a, b, c) ascendente",
                "n_orders_per_config": 40,
                "failures_kept_in_denominator": True,
            },
        )
        dev_labels = [(row["config_id"], {"a": row["a"], "b": row["b"], "c": row["c"]}) for row in top]
        _execute_jobs(_jobs(development, "development", dev_labels))
        dev_rows = []
        for row in top:
            summary = _paired(development, row["config_id"], "development")
            dev_rows.append({**row, "summary": summary, "mean_effective_u_geom": summary["mean_effective_u_geom"]})
        dev_ranked = choose_top(dev_rows, 3)
        chosen = dev_ranked[0]
        gate = engineering_gate(chosen["summary"]["mean_delta"], chosen["summary"]["by_target"]["euro-pallet"], chosen["summary"]["by_target"]["rollcontainer"])
        decision = (
            "Candidato seleccionado para comparación externa de desarrollo en el paso 18"
            if gate["passed"]
            else "Esta cuadrícula y esta configuración quedan abandonadas según la regla congelada"
        )
        atomic_write_json(
            OUTPUT / "development_table.json",
            {"ranked": dev_ranked, "chosen": chosen, "gate": gate, "decision": decision},
        )
        atomic_write_json(
            OUTPUT / "manifest.json",
            {
                "status": "complete",
                "n_cases_expected": 1520,
                "elapsed_seconds": time.perf_counter() - started,
                "top3": [row["config_id"] for row in top],
                "chosen": chosen["config_id"],
                "gate": gate,
                "decision": decision,
                "physical_stability_verified": None,
                "superiority_claimed": False,
                "statistical_test": False,
                "confirmatory": False,
            },
        )
    except Exception as exc:
        atomic_write_json(
            OUTPUT / "manifest.json",
            {
                "status": "incomplete",
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_seconds": time.perf_counter() - started,
                "physical_stability_verified": None,
                "superiority_claimed": False,
            },
        )
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Congela y ejecuta la calibración compacta.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        return prepare()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
