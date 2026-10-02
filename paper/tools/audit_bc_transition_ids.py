#!/usr/bin/env python3
"""Lee los dos pickle BC p=1 s=1 y contrasta sus IDs. No entrena ni infiere."""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


TIMEOUT_SECONDS = 120
ALLOWED_NAME = "transitions_p1s1.pkl"
ALLOWED_SPLITS = frozenset({"train", "val"})

SCALAR_META = (
    "feature_version",
    "feature_dim",
    "teacher",
    "seed",
    "n_transitions",
    "label_rate",
    "seconds",
)


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_file(path),
    }


def is_allowed_transition_path(path: Path) -> bool:
    resolved = path.resolve()
    if "versions" in resolved.parts:
        return False
    return (
        resolved.name == ALLOWED_NAME
        and resolved.parent.name in ALLOWED_SPLITS
        and resolved.parent.parent.name == "data"
        and resolved.parent.parent.parent.name == "online_policy_ml"
    )


def _text_id(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (str, int)):
        return str(value)
    return None


def _duplicates(ids: list[str]) -> list[str]:
    counts = Counter(ids)
    return [item for item, count in counts.items() if count > 1]


def summarize_payload(payload: object) -> dict[str, Any]:
    """Resume un objeto ya cargado. No copia matrices de características."""

    if not isinstance(payload, dict):
        return {
            "object_type": type(payload).__name__,
            "keys": [],
            "schema_usable": False,
            "order_ids": [],
            "note": "El objeto cargado no es un dict. order_ids no se interpreta.",
        }
    declared: list[str] = []
    declared_invalid = 0
    raw_ids = payload.get("order_ids")
    if isinstance(raw_ids, list):
        for item in raw_ids:
            text = _text_id(item)
            if text is None:
                declared_invalid += 1
            else:
                declared.append(text)
    transitions = payload.get("transitions")
    row_ids: list[str | None] = []
    row_keys: list[str] = []
    feature_shape = None
    if isinstance(transitions, list):
        for index, row in enumerate(transitions):
            if isinstance(row, dict):
                if index == 0:
                    row_keys = sorted(str(key) for key in row.keys())
                    features = row.get("features")
                    if isinstance(features, list):
                        width = None
                        if features and isinstance(features[0], list):
                            width = len(features[0])
                        feature_shape = {"n_rows": len(features), "width": width}
                row_ids.append(_text_id(row.get("order_id")) if "order_id" in row else None)
            else:
                row_ids.append(None)
    per_order_ids: list[str] = []
    per_order_counts: list[dict[str, Any]] = []
    per_order = payload.get("per_order")
    if isinstance(per_order, list):
        for item in per_order:
            if not isinstance(item, dict):
                continue
            text = _text_id(item.get("order_id"))
            if text is not None:
                per_order_ids.append(text)
            per_order_counts.append(
                {
                    "order_id": text,
                    "n_transitions": item.get("n_transitions") if isinstance(item.get("n_transitions"), int) else None,
                }
            )
    present_row_ids = [item for item in row_ids if item is not None]
    missing_row_ids = sum(1 for item in row_ids if item is None) if isinstance(transitions, list) else None
    declared_set = set(declared)
    row_set = set(present_row_ids)
    per_set = set(per_order_ids)
    rows_known = isinstance(transitions, list)
    every_row_has_id = rows_known and missing_row_ids == 0 and len(row_ids) > 0
    n_field = payload.get("n_transitions")
    meta = {}
    for key in SCALAR_META:
        value = payload.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            meta[key] = value
    regime = payload.get("regime")
    if isinstance(regime, dict):
        meta["regime"] = {
            key: regime.get(key)
            for key in ("lookahead_p", "select_s")
            if isinstance(regime.get(key), int)
        }
    counts = dict(Counter(present_row_ids))
    coherence = {
        "declared_set_equals_transition_set": rows_known and declared_set == row_set and every_row_has_id,
        "declared_set_equals_per_order_set": bool(per_order_ids) and declared_set == per_set,
        "transition_set_equals_per_order_set": every_row_has_id and row_set == per_set,
        "every_row_has_order_id": every_row_has_id,
        "declared_without_transition": sorted(declared_set - row_set) if rows_known else [],
        "transition_not_declared": sorted(row_set - declared_set) if rows_known else [],
        "n_transitions_field_matches_rows": isinstance(n_field, int) and rows_known and n_field == len(row_ids),
        "declared_invalid_n": declared_invalid,
        "rows_missing_order_id": missing_row_ids,
    }
    schema_usable = rows_known and every_row_has_id and isinstance(raw_ids, list)
    return {
        "object_type": "dict",
        "keys": sorted(str(key) for key in payload.keys()),
        "order_ids": declared,
        "duplicate_order_ids": _duplicates(declared),
        "n_transitions_field": n_field if isinstance(n_field, int) else None,
        "n_transition_rows": len(row_ids) if rows_known else None,
        "transition_order_ids": row_ids if rows_known else None,
        "transitions_per_order_id": counts,
        "per_order_ids": per_order_ids,
        "per_order_transition_counts": per_order_counts,
        "first_transition_keys": row_keys,
        "first_transition_feature_shape": feature_shape,
        "meta": meta,
        "coherence": coherence,
        "schema_usable": schema_usable,
    }


def positive_ids(summary: dict[str, Any] | None) -> set[str] | None:
    """IDs citados por el archivo. None si la lectura no llegó a un resumen."""

    if not summary or not summary.get("read_ok"):
        return None
    found = {str(item) for item in summary.get("order_ids") or []}
    rows = summary.get("transition_order_ids")
    if isinstance(rows, list):
        found |= {str(item) for item in rows if item}
    return found


def absence_is_established(summary: dict[str, Any] | None) -> bool:
    if not summary or not summary.get("read_ok") or not summary.get("schema_usable"):
        return False
    coherence = summary.get("coherence") or {}
    return bool(coherence.get("every_row_has_order_id") and coherence.get("declared_set_equals_transition_set"))


def request_ids_match_manifest_prefix(declared: list[str] | None, per_order: list[str] | None, prefix: str = "bed-bpp-") -> bool | None:
    if not isinstance(declared, list) or not isinstance(per_order, list):
        return None
    return per_order == [prefix + item for item in declared]


def contrast_sets(left: list[str] | None, right: list[str] | None) -> dict[str, Any]:
    if left is None or right is None:
        return {"comparable": False, "set_equal": None, "only_left": [], "only_right": []}
    a = set(left)
    b = set(right)
    return {
        "comparable": True,
        "set_equal": a == b,
        "list_equal": left == right,
        "only_left": sorted(a - b),
        "only_right": sorted(b - a),
        "n_left": len(left),
        "n_right": len(right),
        "n_shared": len(a & b),
    }


def cross_with_full_test(
    found: set[str] | None,
    full_test: dict[str, list[str]],
    *,
    absence_established: bool,
) -> dict[str, Any]:
    if found is None:
        return {
            "absence_established": False,
            "by_target": {
                target: {"n": None, "ids": None, "note": "Lectura insuficiente. No se interpreta como ausencia."}
                for target in sorted(full_test)
            },
        }
    by_target = {}
    for target, ids in sorted(full_test.items()):
        hits = [order_id for order_id in ids if order_id in found]
        by_target[target] = {
            "n": len(hits),
            "ids": hits,
            "candidate_n": len(ids),
            "absence_established": absence_established,
        }
    return {"absence_established": absence_established, "by_target": by_target}


def overlay_exposure(
    by_target: dict[str, Any],
    demonstrated: set[str] | None,
    *,
    absence_established: bool,
    historical_identity: str,
) -> dict[str, Any]:
    """Añade el cruce con los pickle sin borrar exclusiones previas."""

    updated: dict[str, Any] = {}
    counts: dict[str, Any] = {}
    for target, block in sorted(by_target.items()):
        universe = list((block.get("missing_evidence") or {}).get("ids") or [])
        training = list((block.get("registered_training") or {}).get("ids") or [])
        selection = list((block.get("registered_selection") or {}).get("ids") or [])
        historical = list((block.get("historical_evaluation") or {}).get("ids") or [])
        archived = list((block.get("archived_uncertain_cross") or {}).get("ids") or [])
        if demonstrated is None:
            transition_hits = None
            absent = None
            excluded = None
            open_ids = None
        else:
            transition_hits = [order_id for order_id in universe if order_id in demonstrated]
            positive = set(training) | set(selection) | set(historical) | set(archived) | set(transition_hits)
            excluded = [order_id for order_id in universe if order_id in positive]
            if absence_established:
                absent = [order_id for order_id in universe if order_id not in positive]
                open_ids = list(absent)
            else:
                absent = None
                open_ids = None
        updated[target] = {
            "n": block.get("n", len(universe)),
            "registered_training": block.get("registered_training"),
            "registered_selection": block.get("registered_selection"),
            "historical_evaluation": block.get("historical_evaluation"),
            "archived_uncertain_cross": block.get("archived_uncertain_cross"),
            "current_bc_transition_cross": {
                "n": None if transition_hits is None else len(transition_hits),
                "ids": transition_hits,
                "absence_established": absence_established and demonstrated is not None,
            },
            "absent_from_inspected_sources": {
                "n": None if absent is None else len(absent),
                "ids": absent,
                "note": "Ausencia en las fuentes ya inspeccionadas. La identidad histórica del archivo sigue aparte.",
            },
            "positive_exclusion": {
                "n": None if excluded is None else len(excluded),
                "ids": excluded,
            },
            "open_with_historical_identity_unproven": {
                "n": None if open_ids is None else len(open_ids),
                "ids": open_ids,
            },
            "historical_file_identity": historical_identity,
            "absolute_independence": False,
        }
        counts[target] = {
            "n": updated[target]["n"],
            "registered_training_n": len(training),
            "registered_selection_n": len(selection),
            "historical_evaluation_n": len(historical),
            "archived_uncertain_cross_n": len(archived),
            "current_bc_transition_cross_n": None if transition_hits is None else len(transition_hits),
            "absent_from_inspected_sources_n": None if absent is None else len(absent),
            "positive_exclusion_n": None if excluded is None else len(excluded),
            "open_with_historical_identity_unproven_n": None if open_ids is None else len(open_ids),
        }
    return {
        "by_target": updated,
        "counts": counts,
        "absolute_independence": False,
        "historical_file_identity": historical_identity,
        "called_clean": False,
        "called_contaminated": False,
        "n_not_selected": None,
        "future_evaluation_limited_to_euro_pallet": False,
    }


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_ids(path: Path) -> list[str] | None:
    payload = _load_json(path)
    if isinstance(payload, list) and all(isinstance(item, str) for item in payload):
        return list(payload)
    if isinstance(payload, dict) and isinstance(payload.get("order_ids"), list):
        ids = payload["order_ids"]
        if all(isinstance(item, str) for item in ids):
            return list(ids)
    return None


def historical_transition_record(ml_root: Path, paper_root: Path) -> dict[str, Any]:
    report = _load_json(ml_root / "artifacts/reports/02_transitions.json")
    recorded = {}
    if isinstance(report, dict) and isinstance(report.get("table"), list):
        for row in report["table"]:
            if isinstance(row, dict) and row.get("p") == 1 and row.get("s") == 1 and row.get("split") in ALLOWED_SPLITS:
                recorded[str(row["split"])] = {
                    "n_orders": row.get("n_orders"),
                    "n_transitions": row.get("n_transitions"),
                }
    notebook = ml_root / "notebooks/03_imitacion.ipynb"
    notebook_text = notebook.read_text(encoding="utf-8") if notebook.is_file() else ""
    report_03 = _load_json(ml_root / "artifacts/reports/03_validacion.json")
    texts = {
        "02_transitions.json": json.dumps(report) if report is not None else "",
        "03_validacion.json": json.dumps(report_03) if report_03 is not None else "",
        "03_imitacion.ipynb": notebook_text,
        "02_etiquetas_maestro.ipynb": (ml_root / "notebooks/02_etiquetas_maestro.ipynb").read_text(encoding="utf-8")
        if (ml_root / "notebooks/02_etiquetas_maestro.ipynb").is_file()
        else "",
        "06_actor_provenance.md": (paper_root / "reviews/06_actor_provenance.md").read_text(encoding="utf-8")
        if (paper_root / "reviews/06_actor_provenance.md").is_file()
        else "",
    }
    training_names = (
        "02_transitions.json",
        "03_validacion.json",
        "03_imitacion.ipynb",
        "02_etiquetas_maestro.ipynb",
    )
    training_hash_hits = sorted(name for name in training_names if "sha256" in texts.get(name, "").lower())
    return {
        "hash_recorded_at_bc_fit": bool(training_hash_hits),
        "training_files_with_sha256_string": training_hash_hits,
        "step06_review_mentions_sha256": "sha256" in texts.get("06_actor_provenance.md", "").lower(),
        "recorded_counts_p1s1": recorded,
        "notebook_03_printed_1006_356": "train p1s1 1006 | val 356" in notebook_text,
        "file_identity": "no_comprobada",
        "note": (
            "Los informes y notebooks del ajuste BC no guardan un SHA256 de estos pickle. "
            "El hash citado en la revisión 06 se calculó en esta campaña sobre el archivo vigente. "
            "La coincidencia de conteos no identifica el archivo histórico."
        ),
    }


def selection_criterion(ml_root: Path, paper_root: Path) -> dict[str, Any]:
    train_text = (ml_root / "src_ml/train_mlp.py").read_text(encoding="utf-8")
    default_val_loss = 'select_best: SelectBest = "val_loss"' in train_text
    notebook_text = (ml_root / "notebooks/03_imitacion.ipynb").read_text(encoding="utf-8")
    call_passes_select_best = "select_best=" in notebook_text
    report = _load_json(ml_root / "artifacts/reports/03_validacion.json") or {}
    saved = ((report.get("mlp_train") or {}).get("p1s1") or {}).get("select_best")
    review = paper_root / "reviews/02_effective_protocol.md"
    review_text = review.read_text(encoding="utf-8") if review.is_file() else ""
    review_mentions_val_acc_branch = 'select_best` es `"val_acc"`' in review_text or "select_best` es `\"val_acc\"`" in review_text
    if not review_mentions_val_acc_branch:
        review_mentions_val_acc_branch = "val_acc" in review_text and "select_best" in review_text
    if default_val_loss and not call_passes_select_best and saved == "val_loss":
        status = "llamada e informe usan val_loss"
        detail = (
            "fit_mlp omite select_best en el notebook 03. El default de train_mlp.py es val_loss. "
            "03_validacion.json guarda select_best=val_loss para p1s1. "
            "El informe 02 nombra la rama val_acc del mismo código, que esta llamada no activa. "
            "No hay una segunda configuración registrada para esta corrida."
        )
    else:
        status = "no_comprobado"
        detail = "El argumento efectivo y el informe guardado no cierran la misma lectura."
    return {
        "torch_default_is_val_loss": default_val_loss,
        "notebook_03_passes_select_best": call_passes_select_best,
        "report_03_p1s1_select_best": saved,
        "review_02_mentions_val_acc_branch": review_mentions_val_acc_branch,
        "numpy_fallback_selects_by_val_acc": True,
        "status": status,
        "detail": detail,
    }


def worker_main(path: Path) -> int:
    if not is_allowed_transition_path(path):
        print(json.dumps({"read_ok": False, "error": "ruta no autorizada"}, ensure_ascii=False))
        return 2
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        summary = summarize_payload(payload)
        summary["read_ok"] = True
    except Exception as exc:
        summary = {"read_ok": False, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(summary, ensure_ascii=False))
        return 1
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def inspect_file(path: Path, timeout: float) -> dict[str, Any]:
    before = fingerprint(path)
    if not is_allowed_transition_path(path):
        return {
            "read_ok": False,
            "error": "ruta no autorizada",
            "before": before,
            "after": fingerprint(path),
            "absence_established": False,
        }
    command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(path)]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        completed = exc
        timed_out = True
    after = fingerprint(path)
    record: dict[str, Any] = {
        "before": before,
        "after": after,
        "bytes_unchanged": before["sha256"] is not None and before["sha256"] == after["sha256"],
        "read_ok": False,
        "absence_established": False,
    }
    if timed_out:
        record["error"] = f"timeout después de {timeout}s"
        return record
    stdout = (completed.stdout or "").strip()
    record["returncode"] = completed.returncode
    if completed.stderr:
        record["stderr_excerpt"] = completed.stderr[:500]
    try:
        payload = json.loads(stdout) if stdout else {"read_ok": False, "error": "salida vacía"}
    except json.JSONDecodeError:
        record["error"] = "la salida del proceso no es JSON"
        return record
    if not isinstance(payload, dict):
        record["error"] = "el resumen no es un objeto"
        return record
    record.update(payload)
    record["read_ok"] = bool(payload.get("read_ok")) and completed.returncode == 0
    record["absence_established"] = bool(record["read_ok"] and payload.get("schema_usable"))
    if not record["read_ok"]:
        record["absence_established"] = False
    return record


def _full_test_by_target(ml_root: Path, dataset_path: Path) -> tuple[list[str] | None, dict[str, list[str]]]:
    split = _load_json(ml_root / "data/splits/full_split.json")
    full_test = split.get("test") if isinstance(split, dict) else None
    if not isinstance(full_test, list) or not dataset_path.is_file():
        return None, {}
    dataset = _load_json(dataset_path)
    grouped: dict[str, list[str]] = {}
    if not isinstance(dataset, dict):
        return [str(item) for item in full_test], {}
    for order_id in full_test:
        text = str(order_id)
        order = dataset.get(text)
        properties = order.get("properties") if isinstance(order, dict) else None
        target = properties.get("target") if isinstance(properties, dict) else None
        if target is None:
            continue
        grouped.setdefault(str(target), []).append(text)
    return [str(item) for item in full_test], grouped


def build_real(ml_root: Path, dataset_path: Path, paper_root: Path, timeout: float) -> tuple[dict[str, Any], dict[str, Any]]:
    roles = {
        "bc_working_train": ml_root / "data/train/transitions_p1s1.pkl",
        "bc_working_val": ml_root / "data/val/transitions_p1s1.pkl",
    }
    inspections = {role: inspect_file(path, timeout) for role, path in roles.items()}
    for record in inspections.values():
        record["per_order_matches_manifest_id_with_bed_bpp_prefix"] = request_ids_match_manifest_prefix(
            record.get("order_ids") if record.get("read_ok") else None,
            record.get("per_order_ids") if record.get("read_ok") else None,
        )
    demonstrated: set[str] | None = set()
    absence_ok = True
    for record in inspections.values():
        found = positive_ids(record if record.get("read_ok") else None)
        if found is None:
            demonstrated = None
            absence_ok = False
            break
        demonstrated |= found
        if not absence_is_established(record):
            absence_ok = False
    manifests = {
        "bc_working_train": _manifest_ids(ml_root / "data/train/order_ids.json"),
        "bc_working_val": _manifest_ids(ml_root / "data/val/order_ids.json"),
        "ppo_scale_val": _manifest_ids(ml_root / "data/scale/val/order_ids.json"),
    }
    manifest_contrast = {}
    for role, key in (("bc_working_train", "bc_working_train"), ("bc_working_val", "bc_working_val")):
        summary_ids = inspections[role].get("order_ids") if inspections[role].get("read_ok") else None
        row_ids = inspections[role].get("transition_order_ids") if inspections[role].get("schema_usable") else None
        unique_rows = sorted({item for item in row_ids if item}) if isinstance(row_ids, list) else None
        manifest_contrast[role] = {
            "declared_vs_manifest": contrast_sets(summary_ids, manifests[key]),
            "transition_ids_vs_manifest": contrast_sets(unique_rows, manifests[key]),
        }
    _full, by_target = _full_test_by_target(ml_root, dataset_path)
    full_contrast = cross_with_full_test(demonstrated, by_target, absence_established=absence_ok)
    if demonstrated is None:
        selection_contrast = {
            "bc_working_val_intersection": None,
            "ppo_scale_val_intersection": None,
            "comparable": False,
        }
    else:
        selection_contrast = {
            "comparable": True,
            "bc_working_val_intersection": sorted(demonstrated & set(manifests["bc_working_val"] or [])),
            "ppo_scale_val_intersection": sorted(demonstrated & set(manifests["ppo_scale_val"] or [])),
        }
    history = historical_transition_record(ml_root, paper_root)
    criterion = selection_criterion(ml_root, paper_root)
    identity = history["file_identity"]
    baseline_path = paper_root / "results/06_candidate_exposure_by_target.json"
    baseline = _load_json(baseline_path) or {}
    exposure = overlay_exposure(
        baseline.get("by_target") or {},
        demonstrated,
        absence_established=absence_ok and demonstrated is not None,
        historical_identity=identity,
    )
    exposure["step"] = "06a"
    exposure["baseline"] = str(baseline_path)
    exposure["baseline_present"] = baseline_path.is_file()
    future_exclusions: list[str] = []
    for block in (full_contrast.get("by_target") or {}).values():
        ids = block.get("ids")
        if isinstance(ids, list):
            future_exclusions.extend(ids)
    exposure["excluded_from_future_because_in_current_transitions"] = future_exclusions
    document = {
        "step": "06a",
        "timeout_seconds": timeout,
        "inspections": inspections,
        "manifest_contrast": manifest_contrast,
        "full_test_contrast": full_contrast,
        "selection_contrast": selection_contrast,
        "historical": history,
        "selection_criterion": criterion,
        "levels": {
            "A_ids_in_current_files": "demostrados" if demonstrated is not None else "lectura_insuficiente",
            "B_ids_in_historical_execution": "conteos_registrados_sin_lista_de_ids",
            "C_file_identity": identity,
        },
        "demonstrated_id_count": None if demonstrated is None else len(demonstrated),
    }
    return document, exposure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspecciona los dos pickle BC p=1 s=1.")
    parser.add_argument("--worker", type=Path, default=None)
    parser.add_argument("--ml-root", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--paper-root", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--exposure-output", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    if args.worker is not None:
        return worker_main(args.worker)
    if not args.ml_root or not args.dataset or not args.paper_root or not args.output or not args.exposure_output:
        parser.error("faltan rutas de salida")
    document, exposure = build_real(
        args.ml_root.expanduser().resolve(),
        args.dataset.expanduser().resolve(),
        args.paper_root.expanduser().resolve(),
        args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.exposure_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.exposure_output.write_text(json.dumps(exposure, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "read_ok": {role: record.get("read_ok") for role, record in document["inspections"].items()},
        "n_transitions": {
            role: record.get("n_transition_rows") for role, record in document["inspections"].items()
        },
        "full_test": document["full_test_contrast"],
        "identity": document["levels"]["C_file_identity"],
        "criterion": document["selection_criterion"]["status"],
        "counts": exposure.get("counts"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
