"""Selección determinista de 20 pedidos. No empaqueta."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

SELECTION_PREFIX = "counterfactual-v1|20261003|"
MAX_SOURCE_BYTES = 25 * 1024 * 1024
PER_TARGET = 10
TARGETS = ("euro-pallet", "rollcontainer")

POOL = "online_policy_ml/data/splits/val_order_ids_full.json"
ID_LISTS = (
    "online_policy_ml/data/splits/train_order_ids_full.json",
    "online_policy_ml/data/splits/test_order_ids_full.json",
    "online_policy_ml/data/train/order_ids.json",
    "online_policy_ml/data/val/order_ids.json",
    "online_policy_ml/data/test/order_ids.json",
    "online_policy_ml/data/scale/train/order_ids.json",
    "online_policy_ml/data/scale/val/order_ids.json",
    "online_policy_ml/data/scale/test/order_ids.json",
    "online_policy_ml/data/holdout_producto/order_ids.json",
    "online_policy_ml/versions/v1/data/train/order_ids.json",
    "online_policy_ml/versions/v1/data/val/order_ids.json",
    "online_policy_ml/versions/v1/data/test/order_ids.json",
    "online_policy_ml/versions/v1/data/scale/train/order_ids.json",
    "online_policy_ml/versions/v1/data/scale/val/order_ids.json",
    "online_policy_ml/versions/v1/data/scale/test/order_ids.json",
    "online_policy_ml/versions/v1/data/splits/train_order_ids_full.json",
    "online_policy_ml/versions/v1/data/splits/test_order_ids_full.json",
    "online_policy_ml/versions/v1/data/holdout_producto/order_ids.json",
)
JSON_SOURCES = (
    "paper/protocols/07_independent_evaluation.json",
    "paper/protocols/10_normalization_ablation.json",
    "paper/protocols/14_teacher_probe.json",
    "paper/protocols/16_compact_selector_study.json",
    "paper/protocols/17_compact_calibration.json",
    "paper/results/09_exposed_evaluation_ids.json",
    "paper/results/03_confirmatory_candidates.json",
    "paper/results/03_split_cross_audit.json",
    "paper/results/06a_bc_transition_ids.json",
    "paper/results/06a_candidate_exposure_by_target.json",
    "paper/results/06_candidate_exposure_by_target.json",
    "paper/results/07_sample_freeze.json",
    "paper/results/10_normalization_freeze.json",
    "paper/results/11_normalization_ablation/packing/verification.json",
    "paper/results/11_normalization_ablation/packing/manifest.json",
)
CASE_TREES = (
    "paper/results/04_internal_pilot/cases",
    "paper/results/07_independent_evaluation/cases",
    "paper/results/14_teacher_probe/cases",
    "paper/results/16_baseline_smoke/cases",
    "paper/results/16a_onlinebph_capture_smoke/cases",
    "paper/results/17_compact_calibration/cases/train",
    "paper/results/17_compact_calibration/cases/development",
    "paper/results/11_normalization_ablation/packing",
)
NOT_EXCLUSIONS = (
    "online_policy_ml/data/splits/val_order_ids_full.json",
    "online_policy_ml/versions/v1/data/splits/val_order_ids_full.json",
)
UNREAD = (
    "Los 17 pickle históricos no se abrieron.",
    "No se abrieron checkpoints ni pesos.",
    "No se recorrieron auditorías JSON grandes; solo listas de ids, protocolos, manifiestos pequeños y nombres de carpeta.",
    "El protocolo 10 dejó fuera de su exclusión el scale test por falta de una lista histórica. Esta selección sí lee esos order_ids.json si existen.",
)


def selection_hash(order_id: str) -> str:
    return hashlib.sha256(f"{SELECTION_PREFIX}{order_id}".encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_order_id(value: str) -> bool:
    return len(value) == 8 and value.isdigit()


def _collect_strings(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        order_id = node.get("order_id")
        if isinstance(order_id, str) and _is_order_id(order_id):
            found.add(order_id)
        order_ids = node.get("order_ids")
        if isinstance(order_ids, list):
            found.update(item for item in order_ids if isinstance(item, str) and _is_order_id(item))
        for value in node.values():
            _collect_strings(value, found)
    elif isinstance(node, list):
        if node and all(isinstance(item, str) for item in node):
            found.update(item for item in node if _is_order_id(item))
        else:
            for item in node:
                _collect_strings(item, found)


def _case_ids(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    found = set()
    for child in path.rglob("*"):
        if child.is_dir() and len(child.name) == 8 and child.name.isdigit():
            found.add(child.name)
    return found


def exclusion_report(repo: Path) -> dict[str, Any]:
    sources = []
    excluded: set[str] = set()
    missing = []
    skipped_large = []
    for relative in ID_LISTS + JSON_SOURCES:
        path = repo / relative
        if not path.is_file():
            missing.append(relative)
            continue
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            skipped_large.append({"path": relative, "bytes": size})
            continue
        payload = _load_json(path)
        found: set[str] = set()
        _collect_strings(payload, found)
        sources.append({"path": relative, "n": len(found), "bytes": size, "kind": "json"})
        excluded.update(found)
    for relative in CASE_TREES:
        path = repo / relative
        if not path.exists():
            missing.append(relative)
            continue
        found = _case_ids(path)
        sources.append({"path": relative, "n": len(found), "kind": "case_directory"})
        excluded.update(found)
    return {
        "sources": sources,
        "missing": missing,
        "skipped_large": skipped_large,
        "excluded_ids": sorted(excluded),
        "n_excluded": len(excluded),
        "pool_not_used_as_exclusion": list(NOT_EXCLUSIONS),
        "not_inspected": list(UNREAD),
        "absolute_independence": False,
    }


def choose_orders(
    eligible_by_target: dict[str, list[str]],
    signature_of: Callable[[str], str],
    blocked_signatures: dict[str, str],
    *,
    per_target: int = PER_TARGET,
) -> dict[str, Any]:
    """Recorre cada target por hash ascendente y descarta firmas ya usadas."""

    selected: dict[str, list[dict[str, str]]] = {target: [] for target in TARGETS}
    dropped = []
    seen: dict[str, str] = dict(blocked_signatures)
    for target in TARGETS:
        ranked = sorted(eligible_by_target.get(target, []), key=selection_hash)
        for order_id in ranked:
            if len(selected[target]) >= per_target:
                break
            signature = signature_of(order_id)
            if signature in seen:
                dropped.append(
                    {
                        "order_id": order_id,
                        "target": target,
                        "signature": signature,
                        "collides_with": seen[signature],
                    }
                )
                continue
            seen[signature] = order_id
            selected[target].append(
                {
                    "order_id": order_id,
                    "target": target,
                    "selection_hash": selection_hash(order_id),
                    "signature": signature,
                }
            )
    return {"selected": selected, "dropped_clones": dropped}


def signature_payload(snapshot: dict[str, Any], target: str) -> str:
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
