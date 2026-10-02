#!/usr/bin/env python3
"""Clasifica full.test para una reserva futura. No ejecuta packing."""

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
    if "blocked_demo_ids" in payload:
        ids = _ids(payload["blocked_demo_ids"])
        return {"ids": ids} if ids is not None else None
    out: dict[str, list[str]] = {}
    for key in ("train", "val", "test"):
        if key in payload:
            ids = _ids(payload[key])
            if ids is None:
                return None
            out[key] = ids
    for key in ("working_ids", "scale_ids"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            for cut in ("train", "val", "test"):
                if cut in nested:
                    ids = _ids(nested[cut])
                    if ids is None:
                        return None
                    out[f"{key}.{cut}"] = ids
    return out or None


def order_target(order: object) -> str | None:
    if not isinstance(order, dict):
        return None
    properties = order.get("properties")
    if not isinstance(properties, dict) or "target" not in properties:
        return None
    return str(properties.get("target"))


def classify_reserve(
    full_test: list[str] | None,
    targets: dict[str, str | None],
    train_val: dict[str, list[str] | None],
    evaluated: dict[str, list[str]],
) -> dict[str, Any]:
    """Clasifica la reserva. No llama limpio a un conjunto con exposición abierta."""

    if full_test is None:
        return {
            "evidence": "faltante",
            "full_test_n": None,
            "note": "Sin el manifiesto full.test no hay candidatos. No se interpreta como conjunto vacío.",
        }
    crosses: dict[str, list[str]] = {}
    available_train_val = {name: ids for name, ids in train_val.items() if ids is not None}
    missing_train_val = sorted(name for name, ids in train_val.items() if ids is None)
    euro: list[str] = []
    other_targets: dict[str, list[str]] = {}
    target_missing: list[str] = []
    for order_id in full_test:
        target = targets.get(order_id, None)
        if order_id not in targets or target is None:
            target_missing.append(order_id)
            continue
        if target == "euro-pallet":
            euro.append(order_id)
        else:
            other_targets.setdefault(target, []).append(order_id)
    train_val_ids = {item for ids in available_train_val.values() for item in ids}
    crossed = [order_id for order_id in euro if order_id in train_val_ids]
    for name, ids in available_train_val.items():
        shared = sorted(set(euro) & set(ids))
        if shared:
            crosses[name] = shared
    eval_hits: dict[str, list[str]] = {}
    evaluated_ids: set[str] = set()
    for name, ids in evaluated.items():
        shared = sorted(set(euro) & set(ids))
        if shared:
            eval_hits[name] = shared
            evaluated_ids.update(shared)
    historical = [order_id for order_id in euro if order_id in evaluated_ids and order_id not in train_val_ids]
    uncertain = [order_id for order_id in euro if order_id not in evaluated_ids and order_id not in train_val_ids]
    return {
        "evidence": "presente",
        "full_test_n": len(full_test),
        "target_missing_n": len(target_missing),
        "target_missing_ids": target_missing,
        "by_target_n": {"euro-pallet": len(euro), **{key: len(value) for key, value in sorted(other_targets.items())}},
        "non_euro": {key: value for key, value in sorted(other_targets.items())},
        "euro_pallet_n": len(euro),
        "train_val_manifests_checked": sorted(available_train_val),
        "train_val_manifests_missing": missing_train_val,
        "crosses_with_train_or_val": {"n": len(crossed), "by_manifest": crosses, "ids": crossed},
        "historical_evaluation": {"n": len(historical), "by_source": eval_hits, "ids": historical},
        "uncertain_exposure": {
            "n": len(uncertain),
            "ids": uncertain,
            "reason": "No aparecen en las evaluaciones estructuradas leídas. Los .pkl y otros checkpoints siguen sin abrir.",
        },
        "called_clean": False,
        "n_not_selected": None,
        "note": "No se elige N ni se ejecuta packing. Ninguna categoría queda declarada limpia.",
    }


def target_map(dataset: dict[str, Any], wanted: list[str] | None = None) -> dict[str, str | None]:
    if wanted is None:
        wanted = list(dataset)
    out: dict[str, str | None] = {}
    for order_id in wanted:
        if order_id not in dataset:
            continue
        out[order_id] = order_target(dataset[order_id])
    return out


def build_real(ml_root: Path, dataset_path: Path) -> dict[str, Any]:
    split_paths = {
        "live_full": ml_root / "data/splits/full_split.json",
        "live_working": ml_root / "data/splits/working_split.json",
        "live_scale": ml_root / "data/splits/scale_split.json",
        "live_report_01": ml_root / "artifacts/reports/01_splits.json",
        "v1_full": ml_root / "versions/v1/data/splits/full_split.json",
        "v1_working": ml_root / "versions/v1/data/splits/working_split.json",
        "v1_scale": ml_root / "versions/v1/data/splits/scale_split.json",
        "v1_report_01": ml_root / "versions/v1/artifacts/reports/01_splits.json",
        "dir_working_train": ml_root / "data/train/order_ids.json",
        "dir_working_val": ml_root / "data/val/order_ids.json",
        "dir_scale_train": ml_root / "data/scale/train/order_ids.json",
        "dir_scale_val": ml_root / "data/scale/val/order_ids.json",
        "v1_dir_working_train": ml_root / "versions/v1/data/train/order_ids.json",
        "v1_dir_working_val": ml_root / "versions/v1/data/val/order_ids.json",
        "v1_dir_scale_train": ml_root / "versions/v1/data/scale/train/order_ids.json",
        "v1_dir_scale_val": ml_root / "versions/v1/data/scale/val/order_ids.json",
    }
    loaded = {name: load_split_file(path) for name, path in split_paths.items()}
    full = loaded.get("live_full") or {}
    full_test = full.get("test") if isinstance(full, dict) else None
    train_val: dict[str, list[str] | None] = {}
    for name, payload in loaded.items():
        if payload is None:
            train_val[name] = None
            continue
        if "train" in payload:
            train_val[f"{name}.train"] = payload["train"]
        if "val" in payload:
            train_val[f"{name}.val"] = payload["val"]
        if "working_ids.train" in payload:
            train_val[f"{name}.working.train"] = payload["working_ids.train"]
        if "working_ids.val" in payload:
            train_val[f"{name}.working.val"] = payload["working_ids.val"]
        if "scale_ids.train" in payload:
            train_val[f"{name}.scale.train"] = payload["scale_ids.train"]
        if "scale_ids.val" in payload:
            train_val[f"{name}.scale.val"] = payload["scale_ids.val"]
        if "ids" in payload and ("train" in name or name.endswith("_train")):
            train_val[name] = payload["ids"]
        if "ids" in payload and ("val" in name or name.endswith("_val")):
            train_val[name] = payload["ids"]
    if not dataset_path.is_file():
        return {
            "evidence": "faltante",
            "full_test_n": len(full_test) if full_test is not None else None,
            "dataset": {"path": str(dataset_path), "sha256": None, "present": False},
            "note": "Sin el dataset no se clasifican targets. No se trata la reserva como vacía ni como limpia.",
            "called_clean": False,
        }
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    targets = target_map(dataset, full_test) if isinstance(dataset, dict) and full_test is not None else {}
    evaluated = _evaluation_ids(ml_root)
    reserve = classify_reserve(full_test, targets, train_val, evaluated)
    reserve["dataset"] = {
        "path": str(dataset_path),
        "sha256": sha256_file(dataset_path),
        "present": dataset_path.is_file(),
    }
    reserve["full_test_manifest"] = {
        "path": str(split_paths["live_full"]),
        "sha256": sha256_file(split_paths["live_full"]),
    }
    return reserve


def _evaluation_ids(ml_root: Path) -> dict[str, list[str]]:
    """IDs de informes de evaluación. No copia métricas."""

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
        payload = json.loads(path.read_text(encoding="utf-8"))
        ids: list[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if "order_id" in node:
                    text = node["order_id"]
                    if isinstance(text, str) and text not in ids:
                        ids.append(text)
                if "order_ids" in node and isinstance(node["order_ids"], list):
                    for item in node["order_ids"]:
                        if isinstance(item, str) and item not in ids:
                            ids.append(item)
                if "shared" in node and isinstance(node["shared"], list):
                    for item in node["shared"]:
                        if isinstance(item, str) and item not in ids:
                            ids.append(item)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(payload)
        found[relative] = ids
    run_root = ml_root / "artifacts/runs"
    if run_root.is_dir():
        for path in sorted(run_root.glob("eval_*/**/report.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            ids = []

            def walk_run(node: Any) -> None:
                if isinstance(node, dict):
                    if isinstance(node.get("order_id"), str) and node["order_id"] not in ids:
                        ids.append(node["order_id"])
                    if isinstance(node.get("order_ids"), list):
                        for item in node["order_ids"]:
                            if isinstance(item, str) and item not in ids:
                                ids.append(item)
                    for value in node.values():
                        walk_run(value)
                elif isinstance(node, list):
                    for value in node:
                        walk_run(value)

            walk_run(payload)
            found[str(path.relative_to(ml_root))] = ids
    return found


def pilot_orders(subset_path: Path, manifest_path: Path, dataset_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    subset = json.loads(subset_path.read_text(encoding="utf-8")) if subset_path.is_file() else None
    dataset = json.loads(dataset_path.read_text(encoding="utf-8")) if dataset_path.is_file() else None
    orders = []
    blocked = False
    if not isinstance(manifest, list) or not isinstance(subset, dict) or not isinstance(dataset, dict):
        return {"evidence": "faltante", "blocked": True, "orders": []}
    for index, order_id in enumerate(manifest):
        text = str(order_id)
        subset_target = order_target(subset.get(text))
        source_target = order_target(dataset.get(text)) if text in dataset else None
        conflict = subset_target != "euro-pallet" or source_target != "euro-pallet" or subset_target != source_target
        if conflict:
            blocked = True
        orders.append(
            {
                "position": index,
                "order_id": text,
                "target_subset": subset_target,
                "target_source": source_target,
                "conflict_with_euro_pallet": conflict,
            }
        )
    return {
        "evidence": "presente",
        "n": len(orders),
        "blocked": blocked,
        "n_euro_pallet": sum(1 for row in orders if row["target_source"] == "euro-pallet" and not row["conflict_with_euro_pallet"]),
        "n_conflict": sum(1 for row in orders if row["conflict_with_euro_pallet"]),
        "orders": orders,
        "hashes": {
            "scale_val_manifest": sha256_file(manifest_path),
            "scale_val_orders": sha256_file(subset_path),
            "source_dataset": sha256_file(dataset_path),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clasifica la reserva full.test sin ejecutar packing.")
    parser.add_argument("--ml-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot-orders-output", type=Path, default=None)
    args = parser.parse_args(argv)
    root = args.ml_root.expanduser().resolve()
    payload = build_real(root, args.dataset.expanduser().resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.pilot_orders_output is not None:
        pilot = pilot_orders(
            root / "data/scale/val/bed_bpp_orders.json",
            root / "data/scale/val/order_ids.json",
            args.dataset.expanduser().resolve(),
        )
        args.pilot_orders_output.parent.mkdir(parents=True, exist_ok=True)
        args.pilot_orders_output.write_text(json.dumps(pilot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "full_test_n": payload.get("full_test_n"),
        "euro_pallet_n": payload.get("euro_pallet_n"),
        "crosses_n": (payload.get("crosses_with_train_or_val") or {}).get("n"),
        "historical_n": (payload.get("historical_evaluation") or {}).get("n"),
        "uncertain_n": (payload.get("uncertain_exposure") or {}).get("n"),
        "by_target_n": payload.get("by_target_n"),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
