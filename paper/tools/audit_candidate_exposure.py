#!/usr/bin/env python3
"""Clasifica full.test en ambos targets. No ejecuta packing ni abre .pkl."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ids(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    found: list[str] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            return None
        found.append(str(item))
    return found


def load_split_file(path: Path) -> dict[str, list[str]] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        ids = _ids(payload)
        return {"ids": ids} if ids is not None else None
    if not isinstance(payload, dict):
        return None
    if "order_ids" in payload:
        ids = _ids(payload["order_ids"])
        return {"ids": ids} if ids is not None else None
    out: dict[str, list[str]] = {}
    for key in ("train", "val", "test"):
        if key in payload:
            ids = _ids(payload[key])
            if ids is None:
                return None
            out[key] = ids
    return out or None


def order_target(order: object) -> str | None:
    if not isinstance(order, dict):
        return None
    properties = order.get("properties")
    if not isinstance(properties, dict) or "target" not in properties:
        return None
    return str(properties.get("target"))


def _available(sources: dict[str, list[str] | None]) -> tuple[dict[str, set[str]], list[str]]:
    available = {name: set(ids) for name, ids in sources.items() if ids is not None}
    missing = sorted(name for name, ids in sources.items() if ids is None)
    return available, missing


def _category(
    order_ids: list[str],
    sources: dict[str, list[str] | None],
) -> dict[str, Any]:
    available, missing = _available(sources)
    by_source: dict[str, list[str]] = {}
    union: set[str] = set()
    for ids in available.values():
        union |= ids
    hits = [order_id for order_id in order_ids if order_id in union]
    for name, ids in available.items():
        shared = [order_id for order_id in order_ids if order_id in ids]
        if shared:
            by_source[name] = shared
    return {
        "n": len(hits),
        "ids": hits,
        "by_source": by_source,
        "sources_missing": missing,
    }


def classify_by_target(
    full_test: list[str] | None,
    targets: dict[str, str | None],
    registered_training: dict[str, list[str] | None],
    registered_selection: dict[str, list[str] | None],
    historical: dict[str, list[str]],
    archived: dict[str, list[str] | None],
) -> dict[str, Any]:
    """Clasifica cada id. Las categorías se conservan aunque se superpongan."""

    if full_test is None:
        return {
            "evidence": "faltante",
            "full_test_n": None,
            "called_clean": False,
            "called_contaminated": False,
            "n_not_selected": None,
            "future_evaluation_limited_to_euro_pallet": False,
            "note": "Sin el manifiesto full.test no hay candidatos.",
        }
    grouped: dict[str, list[str]] = {}
    target_missing: list[str] = []
    for order_id in full_test:
        target = targets.get(order_id)
        if order_id not in targets or target is None:
            target_missing.append(order_id)
            continue
        grouped.setdefault(target, []).append(order_id)
    historical_sources = {name: ids for name, ids in historical.items()}
    by_target: dict[str, Any] = {}
    for target, order_ids in sorted(grouped.items()):
        training = _category(order_ids, registered_training)
        selection = _category(order_ids, registered_selection)
        evaluated = _category(order_ids, historical_sources)
        archived_hits = _category(order_ids, archived)
        positive = set(training["ids"]) | set(selection["ids"]) | set(evaluated["ids"]) | set(archived_hits["ids"])
        without_record = [order_id for order_id in order_ids if order_id not in positive]
        by_target[target] = {
            "n": len(order_ids),
            "registered_training": training,
            "registered_selection": selection,
            "historical_evaluation": evaluated,
            "archived_uncertain_cross": archived_hits,
            "missing_evidence": {
                "n": len(order_ids),
                "applies_to_all_candidates": True,
                "without_registered_cross_n": len(without_record),
                "without_registered_cross_ids": without_record,
                "ids": list(order_ids),
                "reasons": [
                    "transitions_pkl_not_deserialized",
                    "training_report_has_no_transition_file_hash",
                ],
                "note": (
                    "La ausencia de un cruce en los manifiestos e informes leídos "
                    "deja la independencia sin demostrar."
                ),
            },
        }
    counts = {
        target: {
            "n": block["n"],
            "registered_training_n": block["registered_training"]["n"],
            "registered_selection_n": block["registered_selection"]["n"],
            "historical_evaluation_n": block["historical_evaluation"]["n"],
            "archived_uncertain_cross_n": block["archived_uncertain_cross"]["n"],
            "missing_evidence_n": block["missing_evidence"]["n"],
            "without_registered_cross_n": block["missing_evidence"]["without_registered_cross_n"],
        }
        for target, block in by_target.items()
    }
    return {
        "evidence": "presente",
        "full_test_n": len(full_test),
        "target_missing_n": len(target_missing),
        "target_missing_ids": target_missing,
        "by_target_n": {target: len(ids) for target, ids in sorted(grouped.items())},
        "counts": counts,
        "by_target": by_target,
        "called_clean": False,
        "called_contaminated": False,
        "n_not_selected": None,
        "future_evaluation_limited_to_euro_pallet": False,
        "note": (
            "Cada cruce queda en su categoría. Un id puede figurar en varias. "
            "La independencia y la exposición del actor vigente quedan sin cerrar."
        ),
    }


def compare_state_dicts(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Compara claves, formas y valores. No incluye los tensores."""

    if not isinstance(left, dict) or not isinstance(right, dict):
        return {"weights": "not_checkable", "reason": "state_dict ausente"}
    left_keys = set(left)
    right_keys = set(right)
    shared = sorted(left_keys & right_keys)
    rows = []
    equal = left_keys == right_keys
    for key in shared:
        a = left[key]
        b = right[key]
        shape_a = tuple(getattr(a, "shape", ()))
        shape_b = tuple(getattr(b, "shape", ()))
        dtype_a = str(getattr(a, "dtype", ""))
        dtype_b = str(getattr(b, "dtype", ""))
        shape_equal = shape_a == shape_b
        dtype_equal = dtype_a == dtype_b
        values_equal = False
        if shape_equal and dtype_equal:
            import torch

            values_equal = bool(torch.equal(a, b))
        equal = equal and shape_equal and dtype_equal and values_equal
        rows.append(
            {
                "key": key,
                "shape": list(shape_a),
                "dtype": dtype_a,
                "shape_equal": shape_equal,
                "dtype_equal": dtype_equal,
                "values_equal": values_equal,
            }
        )
    return {
        "weights": "equal" if equal else "distinct",
        "keys_equal": left_keys == right_keys,
        "only_left": sorted(left_keys - right_keys),
        "only_right": sorted(right_keys - left_keys),
        "tensors": rows,
    }


def _scalar_meta(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "state_dict"}


def load_checkpoint(path: Path) -> dict[str, Any]:
    """Carga un .pt con weights_only=True. No hay segundo intento."""

    record: dict[str, Any] = {
        "path": str(path),
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_file(path),
        "weights_only": True,
        "loaded": False,
    }
    if not path.is_file():
        record["error"] = "archivo ausente"
        return record
    import torch

    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record
    record["loaded"] = isinstance(payload, dict)
    if not isinstance(payload, dict):
        record["error"] = "el documento no es un dict"
        return record
    record["meta"] = _scalar_meta(payload)
    state = payload.get("state_dict")
    record["state_dict"] = state if isinstance(state, dict) else None
    if not isinstance(state, dict):
        record["error"] = "state_dict ausente"
    return record


def compare_checkpoint_files(bc_path: Path, ppo_path: Path) -> dict[str, Any]:
    bc = load_checkpoint(bc_path)
    ppo = load_checkpoint(ppo_path)
    if not bc.get("loaded") or not ppo.get("loaded"):
        comparison = {"weights": "not_checkable", "reason": "carga weights_only=True fallida o documento inválido"}
    else:
        comparison = compare_state_dicts(bc.get("state_dict"), ppo.get("state_dict"))
        meta_keys = set(bc.get("meta") or {}) | set(ppo.get("meta") or {})
        comparison["meta_equal"] = {
            key: (bc.get("meta") or {}).get(key) == (ppo.get("meta") or {}).get(key) for key in sorted(meta_keys)
        }
        comparison["file_sha256_equal"] = bc.get("sha256") == ppo.get("sha256")
    public_bc = {key: value for key, value in bc.items() if key != "state_dict"}
    public_ppo = {key: value for key, value in ppo.items() if key != "state_dict"}
    return {"bc": public_bc, "ppo": public_ppo, "comparison": comparison}


def collect_order_ids(node: Any, found: list[str] | None = None) -> list[str]:
    ids = found if found is not None else []
    if isinstance(node, dict):
        text = node.get("order_id")
        if isinstance(text, str) and text not in ids:
            ids.append(text)
        listed = node.get("order_ids")
        if isinstance(listed, list):
            for item in listed:
                if isinstance(item, str) and item not in ids:
                    ids.append(item)
        shared = node.get("shared")
        if isinstance(shared, list):
            for item in shared:
                if isinstance(item, str) and item not in ids:
                    ids.append(item)
        for value in node.values():
            collect_order_ids(value, ids)
    elif isinstance(node, list):
        for value in node:
            collect_order_ids(value, ids)
    return ids


def historical_sources(ml_root: Path, extra_files: list[Path] | None = None) -> dict[str, list[str]]:
    relative_files = [
        "artifacts/reports/03_validacion.json",
        "artifacts/reports/04_compuerta_maestro.json",
        "artifacts/reports/04_escala.json",
        "artifacts/reports/05_ppo.json",
        "artifacts/reports/05_receding.json",
        "artifacts/reports/05_rl_ppo.json",
        "artifacts/reports/06_evaluar_holdout.json",
        "artifacts/reports/06_holdout_producto.json",
        "artifacts/reports/07_holdout_p3s2_baseline.json",
        "artifacts/reports/08_holdout_multipallet.json",
        "artifacts/reports/09_homologar_pct.json",
        "artifacts/reports/10_comparar_pct.json",
        "versions/v1/artifacts/reports/03_validacion.json",
        "versions/v1/artifacts/reports/04_compuerta_maestro.json",
        "versions/v1/artifacts/reports/04_escala.json",
        "versions/v1/artifacts/reports/05_ppo.json",
        "versions/v1/artifacts/reports/05_receding.json",
        "versions/v1/artifacts/reports/06_holdout_producto.json",
        "versions/v1/artifacts/reports/07_holdout_p3s2_baseline.json",
        "versions/v1/artifacts/reports/08_holdout_multipallet.json",
        "versions/v2/artifacts/reports/05_ppo.json",
        "versions/v2/artifacts/reports/05_step.json",
    ]
    found: dict[str, list[str]] = {}
    for relative in relative_files:
        path = ml_root / relative
        if not path.is_file():
            found[relative] = []
            continue
        found[relative] = collect_order_ids(json.loads(path.read_text(encoding="utf-8")))
    run_root = ml_root / "artifacts/runs"
    if run_root.is_dir():
        for path in sorted(run_root.glob("eval_*/**/report.json")):
            found[str(path.relative_to(ml_root))] = collect_order_ids(json.loads(path.read_text(encoding="utf-8")))
    for path in extra_files or []:
        key = str(path)
        if not path.is_file():
            found[key] = []
            continue
        found[key] = collect_order_ids(json.loads(path.read_text(encoding="utf-8")))
    return found


def _manifest_ids(path: Path, *keys: str) -> list[str] | None:
    loaded = load_split_file(path)
    if loaded is None:
        return None
    if not keys:
        return loaded.get("ids")
    if len(keys) == 1 and keys[0] in loaded:
        return loaded[keys[0]]
    return None


def transition_record(path: Path, *, role: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path.as_posix(),
        "role": role,
        "present": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256_file(path),
        "deserialized": False,
        "order_ids_demonstrated": False,
        "documented_schema": schema,
    }


DOCUMENTED_TRANSITION_SCHEMA = {
    "source": "online_policy_ml/src_ml/collect.py collect_dataset",
    "evidence_level": "prescrito_por_codigo",
    "keys": [
        "feature_version",
        "feature_dim",
        "feature_names",
        "regime",
        "teacher",
        "seed",
        "order_ids",
        "transitions",
        "per_order",
        "n_transitions",
        "label_rate",
        "seconds",
    ],
    "order_id_on_each_transition": True,
}


def build_real(ml_root: Path, dataset_path: Path, paper_root: Path | None = None) -> dict[str, Any]:
    full_path = ml_root / "data/splits/full_split.json"
    full = load_split_file(full_path) or {}
    full_test = full.get("test")
    training_paths = {
        "bc_working_train_manifest": ml_root / "data/train/order_ids.json",
        "ppo_scale_train_manifest": ml_root / "data/scale/train/order_ids.json",
    }
    selection_paths = {
        "bc_working_val_manifest": ml_root / "data/val/order_ids.json",
        "ppo_scale_val_manifest": ml_root / "data/scale/val/order_ids.json",
    }
    archived_paths = {
        "v1_working_train_manifest": ml_root / "versions/v1/data/train/order_ids.json",
        "v1_working_val_manifest": ml_root / "versions/v1/data/val/order_ids.json",
        "v1_scale_train_manifest": ml_root / "versions/v1/data/scale/train/order_ids.json",
        "v1_scale_val_manifest": ml_root / "versions/v1/data/scale/val/order_ids.json",
        "v1_full_split_train": (ml_root / "versions/v1/data/splits/full_split.json", "train"),
        "v1_full_split_val": (ml_root / "versions/v1/data/splits/full_split.json", "val"),
        "v1_working_split_train": (ml_root / "versions/v1/data/splits/working_split.json", "train"),
        "v1_working_split_val": (ml_root / "versions/v1/data/splits/working_split.json", "val"),
        "v1_scale_split_train": (ml_root / "versions/v1/data/splits/scale_split.json", "train"),
        "v1_scale_split_val": (ml_root / "versions/v1/data/splits/scale_split.json", "val"),
    }
    registered_training = {name: _manifest_ids(path) for name, path in training_paths.items()}
    registered_selection = {name: _manifest_ids(path) for name, path in selection_paths.items()}
    archived: dict[str, list[str] | None] = {}
    for name, spec in archived_paths.items():
        if isinstance(spec, tuple):
            archived[name] = _manifest_ids(spec[0], spec[1])
        else:
            archived[name] = _manifest_ids(spec)
    pilot_manifest = None
    if paper_root is not None:
        pilot_manifest = paper_root / "results/04_internal_pilot/manifest.json"
    evaluated = historical_sources(ml_root, [pilot_manifest] if pilot_manifest is not None else None)
    if not dataset_path.is_file() or full_test is None:
        return {
            "step": "06",
            "evidence": "faltante",
            "full_test_n": len(full_test) if full_test is not None else None,
            "dataset_present": dataset_path.is_file(),
            "called_clean": False,
            "called_contaminated": False,
            "n_not_selected": None,
            "future_evaluation_limited_to_euro_pallet": False,
            "note": "Sin dataset o sin full.test no se clasifican los candidatos.",
        }
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    targets = {}
    if isinstance(dataset, dict):
        for order_id in full_test:
            if order_id in dataset:
                targets[order_id] = order_target(dataset[order_id])
    classified = classify_by_target(
        full_test,
        targets,
        registered_training,
        registered_selection,
        evaluated,
        archived,
    )
    bc_train = ml_root / "data/train/transitions_p1s1.pkl"
    bc_val = ml_root / "data/val/transitions_p1s1.pkl"
    v1_train = ml_root / "versions/v1/data/train/transitions_p1s1.pkl"
    v1_val = ml_root / "versions/v1/data/val/transitions_p1s1.pkl"
    live_train = transition_record(bc_train, role="bc_fit_train_p1s1", schema=DOCUMENTED_TRANSITION_SCHEMA)
    live_val = transition_record(bc_val, role="bc_early_stopping_val_p1s1", schema=DOCUMENTED_TRANSITION_SCHEMA)
    arch_train = transition_record(v1_train, role="archived_working_train_p1s1", schema=DOCUMENTED_TRANSITION_SCHEMA)
    arch_val = transition_record(v1_val, role="archived_working_val_p1s1", schema=DOCUMENTED_TRANSITION_SCHEMA)
    classified["step"] = "06"
    classified["dataset"] = {
        "path": str(dataset_path),
        "sha256": sha256_file(dataset_path),
    }
    classified["full_test_manifest"] = {"path": str(full_path), "sha256": sha256_file(full_path)}
    classified["checkpoint"] = compare_checkpoint_files(
        ml_root / "artifacts/models/mlp_v1_p1s1.pt",
        ml_root / "artifacts/models/mlp_v1_p1s1_ppo.pt",
    )
    classified["transitions_for_evaluated_actor"] = {
        "bc_consumes": [live_train, live_val],
        "archived_counterparts": [arch_train, arch_val],
        "live_equals_archived_bytes": {
            "train_p1s1": live_train["sha256"] is not None and live_train["sha256"] == arch_train["sha256"],
            "val_p1s1": live_val["sha256"] is not None and live_val["sha256"] == arch_val["sha256"],
        },
        "pkl_deserialized": False,
        "note": (
            "El notebook 03 carga transitions_path('train'|'val', 1, 1). "
            "Esas rutas son data/train y data/val. El archivo archivado de igual nombre "
            "queda como cruce incierto mientras los bytes difieran o el informe no guarde el hash."
        ),
    }
    classified["source_roles"] = {
        "registered_training": {
            "bc_working_train_manifest": "Notebook 02 lee data/train/order_ids.json y el 03 ajusta fit_mlp con el pickle escrito desde ese corte.",
            "ppo_scale_train_manifest": "Notebook 05 pasa data/scale/train/order_ids.json como train_ids de fit_ppo.",
        },
        "registered_selection": {
            "bc_working_val_manifest": "fit_mlp elige el estado por val_loss sobre data/val.",
            "ppo_scale_val_manifest": "fit_ppo elige el actor por utilización media de data/scale/val. El informe 05_rl_ppo.json registra best_epoch 0.",
        },
        "archived_uncertain_cross": "Manifiestos v1. No demuestran por sí solos el entrenamiento del archivo evaluado.",
        "historical_evaluation": "order_id presentes en informes de evaluación ya escritos y en el manifiesto del piloto 05.",
    }
    return classified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clasifica full.test por target sin packing.")
    parser.add_argument("--ml-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--paper-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = build_real(
        args.ml_root.expanduser().resolve(),
        args.dataset.expanduser().resolve(),
        args.paper_root.expanduser().resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "full_test_n": payload.get("full_test_n"),
        "counts": payload.get("counts"),
        "weights": (payload.get("checkpoint") or {}).get("comparison", {}).get("weights"),
        "called_clean": payload.get("called_clean"),
        "called_contaminated": payload.get("called_contaminated"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
