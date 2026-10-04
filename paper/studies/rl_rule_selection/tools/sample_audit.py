"""Exposición, train y la lista de desarrollo. No empaqueta ni elige el test."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
PAPER_TOOLS = STUDY.parents[1] / "tools"
COUNTERFACTUAL = STUDY.parents[1] / "studies" / "counterfactual_ranking" / "tools"
for entry in (str(PAPER_TOOLS), str(COUNTERFACTUAL)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from compact_study import build_compact_problem  # noqa: E402
from pilot_common import REPO_ROOT, sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from select_sample import (  # noqa: E402
    CASE_TREES,
    ID_LISTS,
    JSON_SOURCES,
    MAX_SOURCE_BYTES,
    NOT_EXCLUSIONS,
    POOL,
    TARGETS,
    UNREAD,
    _case_ids,
    _collect_strings,
    _is_order_id,
    _load_json,
    signature_payload,
)

DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
EXPECTED_DATASET_SHA256 = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
SELECTION_PREFIX = "rl-rules-train-v1|20261004|"
PER_TARGET = 64
STUDY_JSON = (
    "paper/studies/counterfactual_ranking/sample_manifest.json",
    "paper/studies/counterfactual_ranking/learning_protocol_frozen.json",
)
STUDY_PATHS = (
    "paper/studies/counterfactual_ranking/diagnostic_results/orders",
    "paper/studies/counterfactual_ranking/learning_labels/orders",
    "paper/studies/counterfactual_ranking/learning_packing/cases",
)


def selection_hash(order_id: str) -> str:
    return hashlib.sha256(f"{SELECTION_PREFIX}{order_id}".encode("utf-8")).hexdigest()


def _target_of(orders: dict[str, Any], order_id: str) -> str:
    if order_id not in orders:
        return "absent_from_dataset"
    target = str((orders[order_id].get("properties") or {}).get("target") or "")
    if target in TARGETS:
        return target
    return "other"


def _item_count(orders: dict[str, Any], order_id: str) -> int:
    sequence = orders[order_id]["item_sequence"]
    return len(sequence)


def _path_name_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    found = set()
    for child in path.rglob("*"):
        stem = child.stem if child.is_file() else child.name
        if _is_order_id(stem):
            found.add(stem)
    return found


def _source_ids(relative: str, kind: str) -> tuple[set[str], dict[str, Any]]:
    path = REPO_ROOT / relative
    if kind == "json":
        if not path.is_file():
            return set(), {"path": relative, "kind": kind, "missing": True}
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            return set(), {"path": relative, "kind": kind, "skipped_large": True, "bytes": size}
        found: set[str] = set()
        _collect_strings(_load_json(path), found)
        return found, {"path": relative, "kind": kind, "bytes": size, "missing": False}
    if kind == "case_directory":
        if not path.exists():
            return set(), {"path": relative, "kind": kind, "missing": True}
        return _case_ids(path), {"path": relative, "kind": kind, "missing": False}
    if not path.exists():
        return set(), {"path": relative, "kind": kind, "missing": True}
    return _path_name_ids(path), {"path": relative, "kind": kind, "missing": False}


def exposure_audit(orders: dict[str, Any], pool: list[str]) -> dict[str, Any]:
    pool_set = set(pool)
    pool_by_target = {target: 0 for target in TARGETS}
    for order_id in pool:
        target = _target_of(orders, order_id)
        if target in pool_by_target:
            pool_by_target[target] += 1
    catalog = (
        [(relative, "json") for relative in ID_LISTS]
        + [(relative, "json") for relative in JSON_SOURCES]
        + [(relative, "case_directory") for relative in CASE_TREES]
        + [(relative, "json") for relative in STUDY_JSON]
        + [(relative, "path_names") for relative in STUDY_PATHS]
    )
    sources = []
    union: set[str] = set()
    occurrences = 0
    for relative, kind in catalog:
        found, meta = _source_ids(relative, kind)
        new = found - union
        in_pool = found & pool_set
        by_target = {target: 0 for target in (*TARGETS, "other", "absent_from_dataset")}
        for order_id in in_pool:
            by_target[_target_of(orders, order_id)] += 1
        meta.update(
            {
                "n_ids": len(found),
                "n_new": len(new),
                "n_already_excluded": len(found) - len(new),
                "n_in_pool": len(in_pool),
                "in_pool_by_target": by_target,
            }
        )
        sources.append(meta)
        occurrences += len(found)
        union.update(found)
    union_in_pool = union & pool_set
    union_by_target = {target: 0 for target in (*TARGETS, "other", "absent_from_dataset")}
    for order_id in union_in_pool:
        union_by_target[_target_of(orders, order_id)] += 1
    remaining = {target: 0 for target in TARGETS}
    for order_id in pool:
        if order_id in union:
            continue
        target = _target_of(orders, order_id)
        if target in remaining:
            remaining[target] += 1
    return {
        "absolute_independence": False,
        "double_count_avoided_by": "n_new y la unión; n_ids de cada fuente se suma aparte",
        "sum_of_source_id_counts": occurrences,
        "union_unique": len(union),
        "count_excess_from_overlapping_sources": occurrences - len(union),
        "union_in_pool": len(union_in_pool),
        "union_in_pool_by_target": union_by_target,
        "pool_n": len(pool),
        "pool_by_target": pool_by_target,
        "remaining_in_pool_by_target": remaining,
        "pool_not_used_as_exclusion": list(NOT_EXCLUSIONS),
        "sources": sources,
        "limits": [
            *UNREAD,
            "Los directorios del estudio counterfactual aportan identificadores por nombre de archivo o carpeta, sin abrir el contenido ni sus U_geom.",
            "No se eligen ni se consultan resultados de desarrollo o de test de este estudio.",
            "La independencia absoluta no se declara: pickle no leídos, archivos grandes omitidos y firmas ausentes del dataset quedan fuera de la comprobación.",
        ],
        "excluded_ids": sorted(union),
    }


def _extremes(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    shortest = min(rows, key=lambda row: (row["n_items"], row["order_id"]))
    longest = min(rows, key=lambda row: (-row["n_items"], row["order_id"]))
    if shortest["order_id"] == longest["order_id"]:
        longest = max(rows, key=lambda row: (row["n_items"], row["order_id"]))
    return {"shortest": shortest, "longest": longest}


def select_train(orders: dict[str, Any], pool: list[str], audit: dict[str, Any]) -> dict[str, Any]:
    excluded = set(audit["excluded_ids"])
    eligible: dict[str, list[str]] = {target: [] for target in TARGETS}
    for order_id in pool:
        if order_id in excluded or order_id not in orders:
            continue
        target = _target_of(orders, order_id)
        if target in eligible:
            eligible[target].append(order_id)
    signatures: dict[str, str] = {}

    def signature_of(order_id: str) -> str:
        if order_id not in signatures:
            problem = build_compact_problem(orders, order_id)
            signatures[order_id] = signature_payload(problem_snapshot(problem), _target_of(orders, order_id))
        return signatures[order_id]

    blocked: dict[str, str] = {}
    unsigned_absent = []
    unsigned_errors = []
    for order_id in sorted(excluded):
        if order_id not in orders:
            unsigned_absent.append(order_id)
            continue
        try:
            blocked[signature_of(order_id)] = order_id
        except Exception as exc:
            unsigned_errors.append({"order_id": order_id, "error": f"{type(exc).__name__}: {exc}"})
    selected: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
    dropped = []
    seen = dict(blocked)
    for target in TARGETS:
        ranked = sorted(eligible[target], key=selection_hash)
        for order_id in ranked:
            if len(selected[target]) >= PER_TARGET:
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
                    "n_items": _item_count(orders, order_id),
                    "selection_hash": selection_hash(order_id),
                    "signature": signature,
                }
            )
    preflight = {target: _extremes(selected[target]) for target in TARGETS}
    observed = []
    for target in TARGETS:
        for role in ("shortest", "longest"):
            row = dict(preflight[target][role])
            row["role"] = role
            observed.append(row)
    return {
        "status": "train_seleccionado",
        "packing_executed": False,
        "development_selected": False,
        "final_test_selected": False,
        "selection_prefix": SELECTION_PREFIX,
        "per_target": PER_TARGET,
        "selection_rule": "hash sha256 del prefijo y el identificador, ascendente, dentro del pool menos la unión de exclusiones",
        "future_split": "desarrollo y test, si se congelan, continúan por pedido en el mismo orden de hash y no se parten por estado",
        "tie_break_length": "más corto: menor número de ítems y luego menor ID; más largo: mayor número de ítems y luego menor ID",
        "selected": selected,
        "n_train": sum(len(rows) for rows in selected.values()),
        "dropped_clones": dropped,
        "n_blocked_signatures": len(blocked),
        "n_unsigned_excluded_absent_from_dataset": len(unsigned_absent),
        "n_unsigned_errors": len(unsigned_errors),
        "unsigned_errors": unsigned_errors,
        "unsigned_limit": "Un identificador excluido que no está en el dataset no tiene firma de snapshot.",
        "preflight_orders": observed,
        "absolute_independence": False,
    }


def select_development(
    orders: dict[str, Any],
    pool: list[str],
    audit: dict[str, Any],
    train_manifest: dict[str, Any],
    *,
    per_target: int = 20,
) -> dict[str, Any]:
    """Siguientes pedidos aceptados por el mismo hash. No empaqueta."""

    train_rows = [row for rows in train_manifest["selected"].values() for row in rows]
    train_ids = {row["order_id"] for row in train_rows}
    seen = {row["signature"]: row["order_id"] for row in train_rows}
    excluded = set(audit["excluded_ids"])

    def signature_of(order_id: str) -> str:
        problem = build_compact_problem(orders, order_id)
        return signature_payload(problem_snapshot(problem), _target_of(orders, order_id))

    unsigned_errors = []
    for order_id in sorted(excluded):
        if order_id not in orders or order_id in train_ids:
            continue
        try:
            seen.setdefault(signature_of(order_id), order_id)
        except Exception as exc:
            unsigned_errors.append({"order_id": order_id, "error": f"{type(exc).__name__}: {exc}"})
    eligible: dict[str, list[str]] = {target: [] for target in TARGETS}
    for order_id in pool:
        if order_id in excluded or order_id in train_ids or order_id not in orders:
            continue
        target = _target_of(orders, order_id)
        if target in eligible:
            eligible[target].append(order_id)
    selected: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
    dropped = []
    for target in TARGETS:
        for order_id in sorted(eligible[target], key=selection_hash):
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
                    "n_items": _item_count(orders, order_id),
                    "selection_hash": selection_hash(order_id),
                    "signature": signature,
                }
            )
    return {
        "status": "desarrollo_seleccionado_sin_episodios",
        "episodes_executed": False,
        "statistics_built": False,
        "final_test_selected": False,
        "final_test_consulted": False,
        "selection_prefix": SELECTION_PREFIX,
        "per_target": per_target,
        "selection_rule": "continúa el hash de train, por pedido, tras excluir train, clones y la unión histórica",
        "selected": selected,
        "n_development": sum(len(rows) for rows in selected.values()),
        "dropped_clones": dropped,
        "unsigned_errors": unsigned_errors,
        "absolute_independence": False,
    }


def write_audits() -> tuple[dict[str, Any], dict[str, Any]]:
    if sha256_file(DATASET) != EXPECTED_DATASET_SHA256:
        raise SystemExit("bloqueo: el SHA256 del dataset no coincide")
    pool = json.loads((REPO_ROOT / POOL).read_text(encoding="utf-8"))
    orders = json.loads(DATASET.read_text(encoding="utf-8"))
    audit = exposure_audit(orders, pool)
    audit["dataset_sha256"] = EXPECTED_DATASET_SHA256
    audit["pool"] = POOL
    audit["pool_sha256"] = sha256_file(REPO_ROOT / POOL)
    train = select_train(orders, pool, audit)
    train["dataset_sha256"] = EXPECTED_DATASET_SHA256
    train["pool"] = POOL
    train["pool_sha256"] = audit["pool_sha256"]
    return audit, train
