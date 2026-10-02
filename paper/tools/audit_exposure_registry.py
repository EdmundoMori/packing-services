#!/usr/bin/env python3
"""Registra fuentes históricas ya escritas. No abre .pkl ni deserializa checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_id(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value)
    if not text.isdigit():
        return None
    return text


def structured_ids(payload: Any) -> dict[str, list[str]]:
    """Extrae IDs solo de campos estructurados, no de una búsqueda de texto."""

    found: dict[str, list[str]] = {
        "manifiesto_train": [],
        "manifiesto_val": [],
        "manifiesto_test": [],
        "manifiesto_otros": [],
        "evaluacion": [],
    }

    def add(bucket: str, value: object) -> None:
        item = _as_id(value)
        if item and item not in found[bucket]:
            found[bucket].append(item)

    def walk(node: Any, parent_key: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"train", "val", "test"} and isinstance(value, list):
                    bucket = {"train": "manifiesto_train", "val": "manifiesto_val", "test": "manifiesto_test"}[key]
                    for item in value:
                        add(bucket, item)
                elif key in {"order_ids", "blocked_demo_ids", "shared"} and isinstance(value, list):
                    for item in value:
                        add("manifiesto_otros", item)
                elif key == "order_id":
                    add("evaluacion", value)
                elif key in {"working_ids", "scale_ids"} and isinstance(value, dict):
                    walk(value, key)
                else:
                    walk(value, key)
        elif isinstance(node, list):
            for item in node:
                walk(item, parent_key)

    walk(payload)
    return {key: ids for key, ids in found.items() if ids}


def classify_payload(relative: str, payload: Any) -> dict[str, Any]:
    ids = structured_ids(payload) if not _is_order_dataset(payload) else {}
    roles: list[str] = []
    kind = "json_sin_ids_estructurados"
    ambiguities: list[str] = []
    if _is_order_dataset(payload):
        kind = "dataset_pedidos"
        roles.append("pertenencia_al_archivo")
        ambiguities.append("Las claves son pedidos almacenados, no un resultado de evaluación.")
        ids = {"n_pedidos": len(payload) if isinstance(payload, dict) else 0}
    elif any(part in relative for part in ("/splits/", "order_ids.json", "01_splits.json")) or (
        isinstance(payload, dict) and any(key in payload for key in ("working_ids", "scale_ids", "train"))
    ):
        kind = "manifiesto"
        if ids.get("manifiesto_train"):
            roles.append("pertenencia_entrenamiento")
        if ids.get("manifiesto_val"):
            roles.append("pertenencia_validacion_o_seleccion")
        if ids.get("manifiesto_test"):
            roles.append("pertenencia_test_registrada")
        if ids.get("manifiesto_otros"):
            roles.append("pertenencia_otro_manifiesto")
    elif _has_evaluation_rows(payload) or "reports/" in relative or "/runs/eval_" in relative:
        kind = "evaluacion_o_seleccion_guardada"
        roles.append("evaluacion_registrada")
        if "05_rl_ppo" in relative or "05_ppo" in relative or relative.endswith("04_compuerta_maestro.json"):
            roles.append("seleccion_o_comparacion_de_desarrollo")
        if isinstance(payload, dict) and "fit" in payload:
            roles.append("seleccion_de_checkpoint_registrada")
            ambiguities.append("best_epoch en este archivo no se reinterpreta; el paso 02 ya fijó su significado en el código.")
    elif isinstance(payload, dict) and "table" in payload and "teacher" in payload:
        kind = "entrenamiento_agregado"
        roles.append("generacion_de_ejemplos_sin_ids")
        ambiguities.append("El resumen trae conteos por split y no la lista de pedidos.")
    elif isinstance(payload, dict) and "mlp_train" in payload:
        kind = "entrenamiento_agregado"
        roles.append("entrenamiento_bc_registrado")
        if ids.get("evaluacion"):
            roles.append("evaluacion_registrada")
            ambiguities.append("Solo algunos IDs aparecen en secciones de humo o filas; el resto del informe es agregado.")
    if not roles:
        ambiguities.append("Este archivo no demuestra por sí solo entrenamiento, selección ni evaluación de pedidos concretos.")
    return {
        "evidence_type": kind,
        "demonstrates": roles,
        "ids": ids,
        "ambiguities": ambiguities,
    }


def _is_order_dataset(payload: Any) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    sample = next(iter(payload.values()))
    return isinstance(sample, dict) and "item_sequence" in sample and "properties" in sample


def _has_evaluation_rows(payload: Any) -> bool:
    if isinstance(payload, dict):
        if "order_id" in payload and ("engine" in payload or "volume_utilization" in payload):
            return True
        return any(_has_evaluation_rows(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_has_evaluation_rows(value) for value in payload[:20])
    return False


def register_tree(ml_root: Path, extra_roots: list[Path] | None = None) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    uninspectable: list[dict[str, Any]] = []
    roots = [ml_root, *(extra_roots or [])]
    for root in roots:
        if not root.is_dir():
            uninspectable.append({"path": str(root), "reason": "directorio ausente"})
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = str(path.relative_to(root)) if root == ml_root else str(path)
            suffix = path.suffix.lower()
            if suffix == ".pkl":
                uninspectable.append(
                    {
                        "path": str(path),
                        "reason": "transición .pkl excluida; no se abrió",
                        "bytes": path.stat().st_size,
                    }
                )
                continue
            if suffix == ".pt":
                uninspectable.append(
                    {
                        "path": str(path),
                        "reason": "checkpoint excluido; no se deserializó ni se hasheó aquí",
                        "bytes": path.stat().st_size,
                    }
                )
                continue
            if suffix not in {".json", ".ipynb", ".md"}:
                continue
            if suffix == ".md":
                sources.append(
                    {
                        "path": str(path),
                        "sha256": sha256_file(path),
                        "evidence_type": "narracion",
                        "demonstrates": [],
                        "ids": {},
                        "ambiguities": ["Un informe narrativo no se usa como prueba de qué pedidos se evaluaron."],
                    }
                )
                continue
            if suffix == ".ipynb":
                notebook = json.loads(path.read_text(encoding="utf-8"))
                cells = notebook.get("cells") if isinstance(notebook, dict) else []
                has_output = any(isinstance(cell, dict) and cell.get("outputs") for cell in cells)
                sources.append(
                    {
                        "path": str(path),
                        "sha256": sha256_file(path),
                        "evidence_type": "notebook_no_ejecutado",
                        "demonstrates": [],
                        "ids": {},
                        "n_cells": len(cells) if isinstance(cells, list) else 0,
                        "has_saved_outputs": has_output,
                        "ambiguities": [
                            "No se ejecutó. Las salidas textuales no se convierten en un manifiesto ni en una lista de evaluación."
                        ],
                    }
                )
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                uninspectable.append({"path": str(path), "reason": f"JSON ilegible: {exc}"})
                continue
            if _is_order_dataset(payload) and path.stat().st_size > 5_000_000:
                sources.append(
                    {
                        "path": str(path),
                        "sha256": sha256_file(path),
                        "evidence_type": "dataset_pedidos",
                        "demonstrates": ["pertenencia_al_archivo"],
                        "ids": {"n_pedidos": len(payload)},
                        "ambiguities": ["Dataset grande. Las claves no se copian al registro."],
                    }
                )
                continue
            classified = classify_payload(relative, payload)
            classified["path"] = str(path)
            classified["sha256"] = sha256_file(path)
            sources.append(classified)
    return {
        "ml_root": str(ml_root),
        "n_sources": len(sources),
        "n_uninspectable": len(uninspectable),
        "sources": sources,
        "uninspectable": uninspectable,
        "note": (
            "Este registro no demuestra ausencia de exposición. "
            "Los .pkl no se abrieron y los checkpoints no se deserializaron."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Registra exposición histórica sin abrir transiciones.")
    parser.add_argument("--ml-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = register_tree(args.ml_root.expanduser().resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"n_sources": payload["n_sources"], "n_uninspectable": payload["n_uninspectable"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
