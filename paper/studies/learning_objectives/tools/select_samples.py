"""Selección determinista de train/desarrollo/test. No empaqueta episodios."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
PAPER = STUDY.parents[1]
REPO = PAPER.parent
PAPER_TOOLS = PAPER / "tools"
COUNTERFACTUAL_TOOLS = PAPER / "studies" / "counterfactual_ranking" / "tools"
for entry in (str(HERE), str(PAPER_TOOLS), str(COUNTERFACTUAL_TOOLS)):
    if entry in sys.path:
        sys.path.remove(entry)
    sys.path.insert(0, entry)

from compact_study import build_compact_problem  # noqa: E402
from pilot_common import sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from select_sample import (  # noqa: E402
    CASE_TREES as CF_CASE_TREES,
    ID_LISTS,
    JSON_SOURCES,
    MAX_SOURCE_BYTES,
    NOT_EXCLUSIONS,
    TARGETS,
    UNREAD,
    _case_ids,
    _is_order_id,
    _load_json,
    signature_payload,
)

DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
EXPECTED_DATASET_SHA256 = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
POOL_VAL = "online_policy_ml/data/splits/val_order_ids_full.json"
POOL_TEST = "online_policy_ml/data/splits/test_order_ids_full.json"
NAMESPACE = "learning-objectives-v1|20261005"
SELECTION_CHAIN_TEMPLATE = "{namespace}|{split}|{order_id}"

PER_TARGET = {"train": 24, "development": 12, "test": 50}

EXTRA_JSON = (
    "paper/studies/counterfactual_ranking/sample_manifest.json",
    "paper/studies/counterfactual_ranking/learning_protocol_frozen.json",
    "paper/studies/rl_rule_selection/train_manifest.json",
    "paper/studies/rl_rule_selection/development_manifest.json",
)
EXTRA_PATHS = (
    "paper/studies/counterfactual_ranking/diagnostic_results/orders",
    "paper/studies/counterfactual_ranking/learning_labels/orders",
    "paper/studies/counterfactual_ranking/learning_packing/cases",
    "paper/studies/counterfactual_ranking/preflight_results",
    "paper/studies/rl_rule_selection/development/cases",
    "paper/studies/rl_rule_selection/preflight_real/cases",
    "paper/studies/rl_rule_selection/training",
)


def selection_hash(order_id: str, *, split: str) -> str:
    chain = SELECTION_CHAIN_TEMPLATE.format(namespace=NAMESPACE, split=split, order_id=order_id)
    return hashlib.sha256(chain.encode("utf-8")).hexdigest()


def selection_chain(order_id: str, *, split: str) -> str:
    return SELECTION_CHAIN_TEMPLATE.format(namespace=NAMESPACE, split=split, order_id=order_id)


def _target_of(orders: dict[str, Any], order_id: str) -> str:
    if order_id not in orders:
        return "absent_from_dataset"
    target = str((orders[order_id].get("properties") or {}).get("target") or "")
    return target if target in TARGETS else "other"


def _path_name_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    found = set()
    for child in path.rglob("*"):
        stem = child.stem if child.is_file() else child.name
        if _is_order_id(stem):
            found.add(stem)
    return found


# El pool de test no puede autoexcluirse: históricamente full.test era exclusión
# al muestrear desde val. Aquí full.test es el pool de evaluación independiente.
TEST_POOL_NOT_EXCLUSIONS = (
    POOL_TEST,
    "online_policy_ml/versions/v1/data/splits/test_order_ids_full.json",
)

# Claves de auditoría histórica que listan candidatos ausentes / no observados.
# No son exposición positiva; incluirlas vaciaría full.test de forma espuria.
NON_POSITIVE_EXPOSURE_KEYS = frozenset(
    {
        "uncertain_exposure",
        "missing_evidence",
        "absent_from_inspected_sources",
        "open_with_historical_identity_unproven",
        "candidates",
        "full_test_manifest",
        "n_not_selected",
        "target_missing_ids",
        "non_euro",
    }
)

# Claves (y sus .ids anidados) que sí registran exposición positiva o exclusión.
POSITIVE_EXPOSURE_KEYS = frozenset(
    {
        "order_id",
        "order_ids",
        "execution_ids",
        "execution_items",
        "positive_exclusion",
        "positive_exclusions",
        "positive_exclusion_ids",
        "registered_training",
        "registered_selection",
        "historical_evaluation",
        "archived_uncertain_cross",
        "current_bc_transition_cross",
        "crosses_with_train_or_val",
        "excluded_from_future_because_in_current_transitions",
        "called_contaminated",
        "ids",
    }
)


def _collect_positive_exposure_ids(node: Any, found: set[str], *, under_positive: bool = False) -> None:
    """Recolecta IDs de exposición positiva; omite catálogos de ausencia."""

    if isinstance(node, dict):
        for key, value in node.items():
            if key in NON_POSITIVE_EXPOSURE_KEYS:
                continue
            if key == "order_id" and isinstance(value, str) and _is_order_id(value):
                found.add(value)
                continue
            if key == "order_ids" and isinstance(value, list):
                found.update(item for item in value if isinstance(item, str) and _is_order_id(item))
                continue
            child_positive = under_positive or key in POSITIVE_EXPOSURE_KEYS
            _collect_positive_exposure_ids(value, found, under_positive=child_positive)
        return
    if isinstance(node, list):
        if under_positive and node and all(isinstance(item, str) for item in node):
            found.update(item for item in node if _is_order_id(item))
            return
        if (not under_positive) and node and all(isinstance(item, str) for item in node):
            # Listas planas de IDs (splits, manifiestos): exposición positiva por procedencia.
            found.update(item for item in node if _is_order_id(item))
            return
        for item in node:
            _collect_positive_exposure_ids(item, found, under_positive=under_positive)


def _source_ids(relative: str, kind: str) -> tuple[set[str], dict[str, Any]]:
    path = REPO / relative
    if kind == "json":
        if not path.is_file():
            return set(), {"path": relative, "kind": kind, "missing": True}
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            return set(), {"path": relative, "kind": kind, "skipped_large": True, "bytes": size}
        found: set[str] = set()
        _collect_positive_exposure_ids(_load_json(path), found)
        return found, {
            "path": relative,
            "kind": kind,
            "bytes": size,
            "n_ids": len(found),
            "missing": False,
            "collector": "positive_exposure_v1",
        }
    if kind == "case_directory":
        if not path.exists():
            return set(), {"path": relative, "kind": kind, "missing": True}
        found = _case_ids(path)
        return found, {"path": relative, "kind": kind, "n_ids": len(found), "missing": False}
    if not path.exists():
        return set(), {"path": relative, "kind": kind, "missing": True}
    found = _path_name_ids(path)
    return found, {"path": relative, "kind": kind, "n_ids": len(found), "missing": False}


def exposure_audit(
    orders: dict[str, Any],
    pool: list[str],
    *,
    skip_sources: tuple[str, ...] = (),
) -> dict[str, Any]:
    catalog = (
        [(relative, "json") for relative in ID_LISTS]
        + [(relative, "json") for relative in JSON_SOURCES]
        + [(relative, "case_directory") for relative in CF_CASE_TREES]
        + [(relative, "json") for relative in EXTRA_JSON]
        + [(relative, "path_names") for relative in EXTRA_PATHS]
    )
    sources = []
    union: set[str] = set()
    skipped = []
    for relative, kind in catalog:
        if relative in skip_sources or relative in NOT_EXCLUSIONS:
            skipped.append(relative)
            continue
        found, meta = _source_ids(relative, kind)
        meta["n_in_pool"] = len(found & set(pool))
        sources.append(meta)
        union.update(found)
    remaining = {target: 0 for target in TARGETS}
    for order_id in pool:
        if order_id in union:
            continue
        target = _target_of(orders, order_id)
        if target in remaining:
            remaining[target] += 1
    return {
        "absolute_independence": False,
        "excluded_ids": sorted(union),
        "n_excluded": len(union),
        "remaining_in_pool_by_target": remaining,
        "pool_not_used_as_exclusion": list(NOT_EXCLUSIONS) + list(skip_sources),
        "sources_skipped": skipped,
        "sources": sources,
        "limits": list(UNREAD)
        + [
            "Se excluyen IDs de campañas anteriores y de estudios counterfactual/rl_rule_selection por manifiestos y nombres de carpeta.",
            "Ausencia de exposición registrada no implica independencia absoluta.",
            "full.test no se usa como exclusión al muestrear el split test de este estudio.",
            "Los catálogos de ausencia (uncertain/missing/absent/candidates) no cuentan como exposición positiva.",
        ],
    }


def _choose(
    *,
    split: str,
    pool: list[str],
    orders: dict[str, Any],
    excluded: set[str],
    blocked: dict[str, str],
    per_target: int,
    signature_of: Callable[[str], str],
    already_taken: set[str],
) -> dict[str, Any]:
    eligible: dict[str, list[str]] = {target: [] for target in TARGETS}
    for order_id in pool:
        if order_id in excluded or order_id in already_taken or order_id not in orders:
            continue
        target = _target_of(orders, order_id)
        if target in eligible:
            eligible[target].append(order_id)
    selected: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
    dropped = []
    seen = dict(blocked)
    for target in TARGETS:
        ranked = sorted(eligible[target], key=lambda oid: (selection_hash(oid, split=split), oid))
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
                    "selection_hash": selection_hash(order_id, split=split),
                    "selection_chain": selection_chain(order_id, split=split),
                    "signature": signature,
                }
            )
    incomplete = any(len(selected[target]) < per_target for target in TARGETS)
    return {
        "selected": selected,
        "dropped_clones": dropped,
        "seen_signatures": seen,
        "incomplete": incomplete,
    }


def select_all(orders: dict[str, Any]) -> dict[str, Any]:
    dataset_sha = sha256_file(DATASET)
    if dataset_sha != EXPECTED_DATASET_SHA256:
        raise RuntimeError("dataset SHA256 distinto del esperado")
    pool_val = list(_load_json(REPO / POOL_VAL))
    pool_test = list(_load_json(REPO / POOL_TEST))
    audit_val = exposure_audit(orders, pool_val)
    audit_test = exposure_audit(orders, pool_test, skip_sources=TEST_POOL_NOT_EXCLUSIONS)
    # Train/dev: exclusiones históricas (incluye full.test como protección).
    # Test: mismas exposiciones positivas, sin autoexcluir el pool full.test.
    excluded_val = set(audit_val["excluded_ids"])
    excluded_test = set(audit_test["excluded_ids"])

    signatures: dict[str, str] = {}

    def signature_of(order_id: str) -> str:
        if order_id not in signatures:
            problem = build_compact_problem(orders, order_id)
            signatures[order_id] = signature_payload(problem_snapshot(problem), _target_of(orders, order_id))
        return signatures[order_id]

    blocked_val: dict[str, str] = {}
    blocked_test: dict[str, str] = {}
    unsigned_errors = []
    unsigned_absent = []
    for order_id in sorted(excluded_val | excluded_test):
        if order_id not in orders:
            unsigned_absent.append(order_id)
            continue
        try:
            signature = signature_of(order_id)
        except Exception as exc:  # noqa: BLE001
            unsigned_errors.append({"order_id": order_id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if order_id in excluded_val:
            blocked_val[signature] = order_id
        if order_id in excluded_test:
            blocked_test[signature] = order_id
    if unsigned_errors:
        raise RuntimeError(f"firmas de exclusión no verificables: {unsigned_errors[:5]}")

    train = _choose(
        split="train",
        pool=pool_val,
        orders=orders,
        excluded=excluded_val,
        blocked=blocked_val,
        per_target=PER_TARGET["train"],
        signature_of=signature_of,
        already_taken=set(),
    )
    if train["incomplete"]:
        raise RuntimeError("train incompleto tras exclusiones")
    train_ids = {row["order_id"] for rows in train["selected"].values() for row in rows}

    development = _choose(
        split="development",
        pool=pool_val,
        orders=orders,
        excluded=excluded_val,
        blocked=train["seen_signatures"],
        per_target=PER_TARGET["development"],
        signature_of=signature_of,
        already_taken=train_ids,
    )
    if development["incomplete"]:
        raise RuntimeError("development incompleto tras exclusiones")
    taken = train_ids | {row["order_id"] for rows in development["selected"].values() for row in rows}

    # Firmas de train/dev seleccionados (no el blocked_val completo: éste incluye
    # firmas de full.test por ID_LISTS y autoanularía el pool de test).
    selected_train_dev_signatures: dict[str, str] = {}
    for split_selected in (train["selected"], development["selected"]):
        for rows in split_selected.values():
            for row in rows:
                selected_train_dev_signatures[row["signature"]] = row["order_id"]

    # Bloqueo de test: exposición positiva (sin autoexclusión del pool) + train/dev.
    test_blocked = dict(blocked_test)
    test_blocked.update(selected_train_dev_signatures)
    test = _choose(
        split="test",
        pool=pool_test,
        orders=orders,
        excluded=excluded_test,
        blocked=test_blocked,
        per_target=PER_TARGET["test"],
        signature_of=signature_of,
        already_taken=taken,
    )
    if test["incomplete"]:
        raise RuntimeError("test incompleto tras exclusiones")

    # Preflight: primer pedido train por target según el manifiesto (orden de selección).
    preflight_orders = []
    for target in TARGETS:
        row = train["selected"][target][0]
        preflight_orders.append({"order_id": row["order_id"], "target": target, "role": "first_train_by_target"})

    return {
        "status": "samples_selected",
        "packing_executed": False,
        "labels_executed": False,
        "training_executed": False,
        "namespace": NAMESPACE,
        "selection_chain_template": SELECTION_CHAIN_TEMPLATE,
        "dataset": str(DATASET),
        "dataset_sha256": dataset_sha,
        "pool_val": POOL_VAL,
        "pool_val_sha256": sha256_file(REPO / POOL_VAL),
        "pool_test": POOL_TEST,
        "pool_test_sha256": sha256_file(REPO / POOL_TEST),
        "per_target": PER_TARGET,
        "n_train": sum(len(v) for v in train["selected"].values()),
        "n_development": sum(len(v) for v in development["selected"].values()),
        "n_test": sum(len(v) for v in test["selected"].values()),
        "train": train["selected"],
        "development": development["selected"],
        "test": test["selected"],
        "dropped_clones": {
            "train": train["dropped_clones"],
            "development": development["dropped_clones"],
            "test": test["dropped_clones"],
        },
        "preflight_orders": preflight_orders,
        "n_blocked_signatures": len(set(blocked_val) | set(blocked_test)),
        "n_blocked_signatures_val": len(blocked_val),
        "n_blocked_signatures_test": len(blocked_test),
        "n_unsigned_absent": len(unsigned_absent),
        "absolute_independence": False,
        "exposure_audit_val_remaining": audit_val["remaining_in_pool_by_target"],
        "exposure_audit_test_remaining": audit_test["remaining_in_pool_by_target"],
        "note_test": "Las firmas de test se calcularon solo para elegibilidad/disyunción/clon; no se analizó packing ni retornos. full.test no se autoexcluye.",
    }
