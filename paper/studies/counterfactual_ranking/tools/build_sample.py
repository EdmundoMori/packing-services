"""Construye la muestra de desarrollo. Lee metadatos y no empaqueta."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_TOOLS = HERE.parents[2] / "tools"
if str(PAPER_TOOLS) not in sys.path:
    sys.path.insert(0, str(PAPER_TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pilot_common import REPO_ROOT, sha256_file  # noqa: E402
from pilot_problems import problem_snapshot  # noqa: E402
from compact_study import build_compact_problem  # noqa: E402
from select_sample import (  # noqa: E402
    POOL,
    TARGETS,
    choose_orders,
    exclusion_report,
    selection_hash,
    signature_payload,
)

DATASET = Path("/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json")
EXPECTED_DATASET_SHA256 = "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc"
OUTPUT = HERE.parent / "sample_manifest.json"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build() -> dict:
    if not DATASET.is_file():
        raise SystemExit(f"bloqueo: no está el dataset {DATASET}")
    dataset_sha = sha256_file(DATASET)
    if dataset_sha != EXPECTED_DATASET_SHA256:
        raise SystemExit("bloqueo: el SHA256 del dataset no es el de los protocolos 16 y 17")
    pool_path = REPO_ROOT / POOL
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    if not isinstance(pool, list) or not all(isinstance(item, str) for item in pool):
        raise SystemExit("bloqueo: el pool full.val no es una lista de identificadores")
    report = exclusion_report(REPO_ROOT)
    excluded = set(report["excluded_ids"])
    orders = json.loads(DATASET.read_text(encoding="utf-8"))
    missing_from_dataset = sorted(order_id for order_id in pool if order_id not in orders)
    eligible: dict[str, list[str]] = {target: [] for target in TARGETS}
    unknown_target = []
    for order_id in pool:
        if order_id in excluded or order_id not in orders:
            continue
        target = str((orders[order_id].get("properties") or {}).get("target") or "")
        if target not in eligible:
            unknown_target.append({"order_id": order_id, "target": target})
            continue
        eligible[target].append(order_id)
    signatures: dict[str, str] = {}

    def signature_of(order_id: str) -> str:
        if order_id not in signatures:
            problem = build_compact_problem(orders, order_id)
            target = str((orders[order_id].get("properties") or {}).get("target") or "")
            signatures[order_id] = signature_payload(problem_snapshot(problem), target)
        return signatures[order_id]

    blocked = {}
    unsigned_excluded = []
    unsigned_errors = []
    for order_id in sorted(excluded):
        if order_id not in orders:
            unsigned_excluded.append(order_id)
            continue
        try:
            blocked[signature_of(order_id)] = order_id
        except Exception as exc:
            unsigned_errors.append({"order_id": order_id, "error": f"{type(exc).__name__}: {exc}"})
    chosen = choose_orders(eligible, signature_of, blocked)
    ready = all(len(chosen["selected"][target]) == 10 for target in TARGETS)
    payload = {
        "status": "lista_preparada" if ready else "bloqueada",
        "packing_executed": False,
        "dataset": str(DATASET),
        "dataset_sha256": dataset_sha,
        "pool": POOL,
        "pool_sha256": sha256_file(pool_path),
        "pool_n": len(pool),
        "eligible_n": {target: len(eligible[target]) for target in TARGETS},
        "missing_from_dataset": missing_from_dataset,
        "unknown_target": unknown_target,
        "unsigned_excluded_not_in_dataset_n": len(unsigned_excluded),
        "unsigned_excluded_errors": unsigned_errors,
        "exclusion": {
            "n_excluded": report["n_excluded"],
            "sources": report["sources"],
            "missing": report["missing"],
            "skipped_large": report["skipped_large"],
            "pool_not_used_as_exclusion": report["pool_not_used_as_exclusion"],
            "not_inspected": report["not_inspected"],
            "absolute_independence": False,
            "excluded_ids_sha256": _sha256_text("\n".join(report["excluded_ids"])),
        },
        "clone_rule": (
            "Tras ordenar los elegibles de cada target por SHA256 de "
            "'counterfactual-v1|20261003|' + order_id, se omite un id cuya firma "
            "compacta coincide con un pedido ya aceptado o con un pedido excluido firmado. "
            "La firma es el SHA256 del JSON canónico {target, items:[[l,w,h,peso,orientaciones],...]} "
            "del snapshot compacto, antes de colocar."
        ),
        "selected": chosen["selected"],
        "dropped_clones": chosen["dropped_clones"],
        "execution_order": [row["order_id"] for target in TARGETS for row in chosen["selected"][target]],
        "preflight_orders": {
            "euro-pallet": chosen["selected"]["euro-pallet"][0]["order_id"] if chosen["selected"]["euro-pallet"] else None,
            "rollcontainer": chosen["selected"]["rollcontainer"][0]["order_id"] if chosen["selected"]["rollcontainer"] else None,
            "max_states_per_order": 1,
            "max_alternatives": 2,
            "counts_toward_sample": True,
            "counts_toward_budget": True,
            "may_reselect_sample": False,
        },
    }
    if not ready:
        payload["block"] = "no hay 10 pedidos firmados por target tras las exclusiones y los clones"
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    print(result["status"], result["eligible_n"])
    for target in TARGETS:
        print(target, [row["order_id"] for row in result["selected"][target]])
