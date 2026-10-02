"""Congela estadísticas y muestra del paso 10. No entrena ni empaqueta."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from freeze_normalization_sample import (
    SelectionStopped,
    exclusion_ids,
    load_id_list,
    pools_after_exclusion,
    select_development,
)
from normalization_features import (
    FEATURE_NAMES,
    candidate_matrix,
    constant_names,
    fit_standardizer,
    stats_sha256,
)

REPO = Path(__file__).resolve().parents[2]
ML = REPO / "online_policy_ml"
TRAIN_PKL = ML / "data/train/transitions_p1s1.pkl"
VAL_PKL = ML / "data/val/transitions_p1s1.pkl"
AUDIT_06A = REPO / "paper/results/06a_bc_transition_ids.json"
EXPOSURE_06A = REPO / "paper/results/06a_candidate_exposure_by_target.json"
EXPOSED_09 = REPO / "paper/results/09_exposed_evaluation_ids.json"
FULL_SPLIT = ML / "data/splits/full_split.json"
DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
OUT = REPO / "paper/results/10_normalization_freeze.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_hashes() -> dict[str, str]:
    document = json.loads(AUDIT_06A.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {"train": [], "val": []}
    for key, split in (("bc_working_train", "train"), ("bc_working_val", "val")):
        block = document["inspections"][key]
        for moment in ("before", "after"):
            found[split].append(block[moment]["sha256"])
    if len(set(found["train"])) != 1 or len(set(found["val"])) != 1:
        raise RuntimeError("el resultado 06A no tiene un hash estable")
    return {"train": found["train"][0], "val": found["val"][0]}


def read_transitions() -> dict[str, Any]:
    expected = audit_hashes()
    before = {"train": sha256_file(TRAIN_PKL), "val": sha256_file(VAL_PKL)}
    if before != expected:
        raise RuntimeError("el hash actual no coincide con 06A; no se leen los pickle")
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--read-transitions"],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    after = {"train": sha256_file(TRAIN_PKL), "val": sha256_file(VAL_PKL)}
    if after != expected:
        raise RuntimeError("el hash cambió durante la lectura")
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "falló la lectura")
    payload = json.loads(completed.stdout)
    payload["sha256_before"] = before
    payload["sha256_after"] = after
    return payload


def _read_child() -> None:
    import pickle

    loaded = {}
    for split, path in (("train", TRAIN_PKL), ("val", VAL_PKL)):
        with path.open("rb") as handle:
            loaded[split] = pickle.load(handle)
    document = {
        split: {
            "transitions": payload["transitions"],
            "order_ids": payload.get("order_ids"),
            "teacher": payload.get("teacher"),
            "regime": payload.get("regime"),
            "feature_names": payload.get("feature_names"),
            "n_transitions": payload.get("n_transitions"),
        }
        for split, payload in loaded.items()
    }
    json.dump(document, sys.stdout)
    sys.stdout.write("\n")


def _exposure_ids() -> dict[str, list[str]]:
    document = json.loads(EXPOSURE_06A.read_text(encoding="utf-8"))
    found: dict[str, list[str]] = {}
    for target, block in document["by_target"].items():
        for key in ("positive_exclusion", "archived_uncertain_cross"):
            ids = list((block.get(key) or {}).get("ids") or [])
            found[f"06a_{target}_{key}"] = ids
    return found


def _exposed_ids() -> dict[str, list[str]]:
    document = json.loads(EXPOSED_09.read_text(encoding="utf-8"))
    return {f"observed_{row['name']}": list(row["order_ids"]) for row in document["sources"]}


def collect_sources() -> dict[str, list[str]]:
    files = {
        "live_working_train": ML / "data/train/order_ids.json",
        "live_working_val": ML / "data/val/order_ids.json",
        "live_working_test": ML / "data/test/order_ids.json",
        "live_scale_train": ML / "data/scale/train/order_ids.json",
        "live_scale_val": ML / "data/scale/val/order_ids.json",
        "v1_working_train": ML / "versions/v1/data/train/order_ids.json",
        "v1_working_val": ML / "versions/v1/data/val/order_ids.json",
        "v1_working_test": ML / "versions/v1/data/test/order_ids.json",
        "v1_scale_train": ML / "versions/v1/data/scale/train/order_ids.json",
        "v1_scale_val": ML / "versions/v1/data/scale/val/order_ids.json",
        "holdout_producto": ML / "data/holdout_producto/order_ids.json",
    }
    sources = {name: load_id_list(path) for name, path in files.items()}
    sources.update(_exposure_ids())
    sources.update(_exposed_ids())
    return sources


def full_val_targets() -> dict[str, list[str]]:
    split = json.loads(FULL_SPLIT.read_text(encoding="utf-8"))
    wanted = set(split["val"])
    if len(wanted) != len(split["val"]):
        raise SelectionStopped("full.val tiene ids repetidos")
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    missing = sorted(wanted - set(dataset))
    if missing:
        raise SelectionStopped(f"faltan {len(missing)} ids de full.val en el dataset. No se selecciona.")
    by_target: dict[str, list[str]] = {}
    unknown: list[str] = []
    for order_id in split["val"]:
        target = str((dataset[order_id].get("properties") or {}).get("target") or "")
        if target not in ("euro-pallet", "rollcontainer"):
            unknown.append(f"{order_id}:{target or 'ausente'}")
            continue
        by_target.setdefault(target, []).append(order_id)
    if unknown:
        raise SelectionStopped("hay targets no comprobados en full.val: " + ", ".join(unknown[:8]))
    return by_target


def build_freeze() -> dict[str, Any]:
    loaded = read_transitions()
    train = loaded["train"]["transitions"]
    val = loaded["val"]["transitions"]
    for split in ("train", "val"):
        if loaded[split].get("feature_names") != list(FEATURE_NAMES):
            raise RuntimeError("el orden de características del pickle no es el de features.py")
    train_matrix = candidate_matrix(train)
    both_matrix = candidate_matrix([*train, *val])
    stats = fit_standardizer(train_matrix)
    stats["source_sha256"] = loaded["sha256_before"]
    stats["n_train_transitions"] = len(train)
    stats["n_val_transitions"] = len(val)
    stats["n_single_candidate_kept"] = {
        "train": sum(1 for row in train if int(row["n_options"]) <= 1),
        "val": sum(1 for row in val if int(row["n_options"]) <= 1),
    }
    constants_train = constant_names(train_matrix)
    constants_both = constant_names(both_matrix)
    sources = collect_sources()
    excluded = exclusion_ids(sources)
    by_target = full_val_targets()
    full_val_ids = {order_id for ids in by_target.values() for order_id in ids}
    selected = select_development(pools_after_exclusion(by_target, set(excluded["ids"])))
    chosen = {row["order_id"] for row in selected["execution_items"]}
    if chosen & set(excluded["ids"]):
        raise SelectionStopped("la muestra contiene un id excluido. No se entrega.")
    removed = {
        target: sorted(set(by_target[target]) & set(excluded["ids"]))
        for target in by_target
    }
    removed_by_source = {
        name: sorted(set(ids) & full_val_ids) for name, ids in sources.items()
    }
    scale_test = load_id_list(ML / "data/scale/test/order_ids.json")
    scale_test_in_sample = sorted(set(scale_test) & chosen)
    return {
        "schema_version": 1,
        "training_executed": False,
        "packing_executed": False,
        "confirmatory": False,
        "step_08_interpretation": "no_concluyente",
        "transitions": {
            "sha256_before": loaded["sha256_before"],
            "sha256_after": loaded["sha256_after"],
            "sha256_matches_06a": True,
            "teacher": loaded["train"].get("teacher"),
            "regime": loaded["train"].get("regime"),
            "order_ids": {"train": loaded["train"].get("order_ids"), "val": loaded["val"].get("order_ids")},
            "labels_preserved": True,
            "single_candidate_rows_removed": False,
        },
        "standardizer": stats,
        "standardizer_sha256": stats_sha256(stats),
        "constant_columns": {
            "rule": "desviación poblacional <= 1e-12",
            "train": constants_train,
            "train_plus_val": constants_both,
            "only_in_train": sorted(set(constants_train) - set(constants_both)),
            "only_in_train_plus_val": sorted(set(constants_both) - set(constants_train)),
        },
        "full_val_pool_n": {target: len(ids) for target, ids in by_target.items()},
        "exclusion_source_n": excluded["by_source_n"],
        "exclusion_ids_n": len(excluded["ids"]),
        "removed_from_full_val_n": {target: len(ids) for target, ids in removed.items()},
        "eligible_after_exclusion_n": {
            target: len(by_target[target]) - len(removed[target]) for target in by_target
        },
        "removed_from_full_val_by_source_n": {
            name: len(ids) for name, ids in removed_by_source.items()
        },
        "scale_test_not_excluded": {
            "n": len(scale_test),
            "in_full_val_n": len(set(scale_test) & full_val_ids),
            "in_development_sample": scale_test_in_sample,
            "reason": "no hay una lista de evaluación histórica que identifique estos ids; no se sustituye el pool excluyéndolos",
        },
        "development_sample": selected,
    }


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--read-transitions":
        _read_child()
        return
    try:
        document = build_freeze()
    except (SelectionStopped, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
