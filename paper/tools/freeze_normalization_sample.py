"""Selección de la muestra de desarrollo del paso 10. No ejecuta packing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SELECTION_LABEL = "packing-study-normalization-dev-v1|20261002"
QUOTA = {"euro-pallet": 25, "rollcontainer": 25}
ALLOWED_TARGETS = ("euro-pallet", "rollcontainer")


class SelectionStopped(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def selection_hash(target: str, order_id: str) -> str:
    return sha256_text(f"{SELECTION_LABEL}|{target}|{order_id}")


def frozen_list_sha256(order_ids: list[str]) -> str:
    return sha256_text("\n".join(order_ids) + "\n")


def load_id_list(path: Path) -> list[str]:
    if not path.is_file():
        raise SelectionStopped(f"falta la lista de exclusión {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("order_ids")
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise SelectionStopped(f"la lista {path} no es una lista de ids")
    return list(payload)


def exclusion_ids(sources: dict[str, list[str]]) -> dict[str, Any]:
    missing = [name for name, ids in sources.items() if not ids and name.endswith("_required")]
    if missing:
        raise SelectionStopped("hay una exclusión requerida vacía: " + ", ".join(missing))
    merged: set[str] = set()
    for ids in sources.values():
        merged.update(ids)
    return {"by_source_n": {name: len(ids) for name, ids in sources.items()}, "ids": sorted(merged)}


def pools_after_exclusion(
    full_val_by_target: dict[str, list[str]],
    excluded: set[str],
) -> dict[str, list[str]]:
    for target in ALLOWED_TARGETS:
        ids = full_val_by_target.get(target)
        if not ids:
            raise SelectionStopped(f"full.val no tiene pedidos de {target}. No se selecciona.")
        if len(set(ids)) != len(ids):
            raise SelectionStopped(f"full.val repite ids de {target}. No se selecciona.")
    unknown = sorted(set(full_val_by_target) - set(ALLOWED_TARGETS))
    if unknown:
        raise SelectionStopped(f"full.val tiene targets no previstos: {unknown}. No se selecciona.")
    pools = {}
    for target in ALLOWED_TARGETS:
        kept = [order_id for order_id in full_val_by_target[target] if order_id not in excluded]
        if len(kept) < QUOTA[target]:
            raise SelectionStopped(
                f"{target} deja {len(kept)} pedidos tras las exclusiones y la cuota es {QUOTA[target]}. No se sustituye el pool."
            )
        pools[target] = kept
    return pools


def select_development(pools: dict[str, list[str]]) -> dict[str, Any]:
    chosen: list[dict[str, Any]] = []
    by_target: dict[str, list[dict[str, Any]]] = {}
    for target in ALLOWED_TARGETS:
        ranked = [
            {"order_id": order_id, "target": target, "selection_hash": selection_hash(target, order_id)}
            for order_id in pools[target]
        ]
        ranked.sort(key=lambda row: (row["selection_hash"], row["order_id"]))
        for index, row in enumerate(ranked):
            row["selection_rank"] = index
        picked = [dict(row) for row in ranked[: QUOTA[target]]]
        by_target[target] = picked
        chosen.extend(picked)
    ordered = sorted(chosen, key=lambda row: row["order_id"])
    for position, row in enumerate(ordered):
        row["position"] = position
    ids = [row["order_id"] for row in ordered]
    return {
        "selection_label": SELECTION_LABEL,
        "quota": dict(QUOTA),
        "by_target": by_target,
        "execution_items": ordered,
        "frozen_list_sha256": frozen_list_sha256(ids),
        "confirmatory": False,
        "role": "desarrollo",
    }
