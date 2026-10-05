"""Congela muestra G2 y metadatos (sin packing)."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STUDY = Path(__file__).resolve().parents[1]
DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
EXPECTED_DS = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
POOL_VAL = REPO / "online_policy_ml/data/splits/val_order_ids_full.json"
NAMESPACE = "robust-packing-management-g2|20261005"

sys.path.insert(0, str(REPO / "paper" / "tools"))
sys.path.insert(0, str(REPO / "paper" / "studies" / "counterfactual_ranking" / "tools"))

from compact_study import build_compact_problem  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from select_sample import signature_payload  # noqa: E402


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_exposed_ids() -> set[str]:
    exposed: set[str] = set()
    lo = json.loads((STUDY.parent / "learning_objectives" / "sample_manifest.json").read_text())
    for split in ("train", "development", "test"):
        for rows in lo[split].values():
            exposed.update(r["order_id"] for r in rows)
    cf = json.loads((STUDY.parent / "counterfactual_ranking" / "sample_manifest.json").read_text())
    exposed.update(cf.get("execution_order") or [])
    sel = cf.get("selected")
    if isinstance(sel, dict):
        for v in sel.values():
            if isinstance(v, list):
                for x in v:
                    if isinstance(x, dict) and x.get("order_id"):
                        exposed.add(str(x["order_id"]))
                    elif isinstance(x, str):
                        exposed.add(x)
    elif isinstance(sel, list):
        for x in sel:
            if isinstance(x, dict) and x.get("order_id"):
                exposed.add(str(x["order_id"]))
            elif isinstance(x, str):
                exposed.add(x)
    # train/test full pools as exclusions (not using reserved test)
    for rel in (
        "online_policy_ml/data/splits/train_order_ids_full.json",
        "online_policy_ml/data/splits/test_order_ids_full.json",
    ):
        exposed.update(json.loads((REPO / rel).read_text()))
    return exposed


def main() -> int:
    ds_sha = sha256_file(DATASET)
    if ds_sha != EXPECTED_DS:
        raise SystemExit(f"dataset sha mismatch: {ds_sha}")
    pool = list(json.loads(POOL_VAL.read_text()))
    orders = json.loads(DATASET.read_text())
    exposed = collect_exposed_ids()

    signatures: dict[str, str] = {}

    def signature_of(order_id: str) -> str:
        if order_id not in signatures:
            problem = build_compact_problem(orders, order_id)
            target = str((orders[order_id].get("properties") or {}).get("target") or "")
            signatures[order_id] = signature_payload(problem_snapshot(problem), target)
        return signatures[order_id]

    blocked: dict[str, str] = {}
    unsigned_errors = []
    for oid in sorted(exposed):
        if oid not in orders:
            continue
        try:
            blocked[signature_of(oid)] = oid
        except Exception as exc:  # noqa: BLE001
            unsigned_errors.append({"order_id": oid, "error": f"{type(exc).__name__}: {exc}"})

    eligible: dict[str, list[str]] = defaultdict(list)
    for oid in sorted(pool):
        if oid in exposed or oid not in orders:
            continue
        target = str((orders[oid].get("properties") or {}).get("target") or "")
        if target not in ("euro-pallet", "rollcontainer"):
            continue
        sig = signature_of(oid)
        if sig in blocked:
            continue
        eligible[target].append(oid)

    selected: dict[str, list[dict]] = {"euro-pallet": [], "rollcontainer": []}
    taken_sigs: set[str] = set()
    for target in ("euro-pallet", "rollcontainer"):
        for oid in eligible[target]:
            if len(selected[target]) >= 5:
                break
            sig = signature_of(oid)
            if sig in taken_sigs:
                continue
            taken_sigs.add(sig)
            selected[target].append(
                {
                    "order_id": oid,
                    "target": target,
                    "signature": sig,
                    "selection_chain": f"{NAMESPACE}|development|{target}|{oid}",
                    "selection_hash": sha256_text(f"{NAMESPACE}|development|{target}|{oid}"),
                    "n_items": len(orders[oid].get("item_sequence") or {}),
                }
            )

    # Preflight: first order_id ascending per target in selected (already sorted)
    preflight = [
        selected["euro-pallet"][0]["order_id"],
        selected["rollcontainer"][0]["order_id"],
    ]

    manifest = {
        "status": "frozen_sample",
        "packing_executed": False,
        "namespace": NAMESPACE,
        "dataset": str(DATASET),
        "dataset_sha256": ds_sha,
        "pool_val": str(POOL_VAL.relative_to(REPO)),
        "pool_val_sha256": sha256_file(POOL_VAL),
        "absolute_independence": False,
        "independence_note": (
            "Ausencia de ID en registros de exposición no implica independencia absoluta; "
            "absolute_independence=false."
        ),
        "excluded_sources_note": (
            "Excluye IDs de learning_objectives train/dev/test, counterfactual execution_order/"
            "selected, y pools train/test full. No usa ni abre el test reservado como muestra."
        ),
        "n_exposed_union_approx": len(exposed),
        "n_blocked_signatures": len(blocked),
        "n_unsigned_signature_errors": len(unsigned_errors),
        "unsigned_signature_errors_head": unsigned_errors[:5],
        "eligible_n": {t: len(eligible[t]) for t in selected},
        "development": selected,
        "n_development": sum(len(v) for v in selected.values()),
        "preflight_orders": preflight,
        "preflight_rule": "first_selected_order_id_ascending_per_target",
        "clone_rule": "signature_payload(problem_snapshot, target); one order per signature in sample",
        "test_split_closed": True,
        "learning_objectives_test_not_used": True,
    }
    out = STUDY / "sample_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(out), "preflight": preflight, "n_dev": manifest["n_development"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
