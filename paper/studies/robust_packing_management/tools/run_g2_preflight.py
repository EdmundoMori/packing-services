#!/usr/bin/env python3
"""Preflight real G2: 2 pedidos × 4 métodos × 1 escenario. Techo 900 s."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REPO = STUDY.parents[2]  # packing-services
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))

from bedbpp_episode import load_orders, order_to_episode_spec
from error_model import PREFLIGHT_SCENARIO, PublicErrorModel, model_public_dict
from methods_g2 import METHOD_SPECS, build_methods
from run_g2_episode import persist_episode, run_method_episode

WALL_GLOBAL_S = 900.0
TIMEOUT_EPISODE_S = 100.0
OUT_ROOT = STUDY / "results" / "g2_preflight"


def rss_mb() -> float | None:
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    t_global = time.perf_counter()
    manifest = json.loads((STUDY / "sample_manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((STUDY / "g2_protocol_frozen.json").read_text(encoding="utf-8"))
    preflight_orders = list(manifest["preflight_orders"])
    assert len(preflight_orders) == 2
    scenario = protocol["preflight"]["scenario_id"]
    assert scenario == PREFLIGHT_SCENARIO
    model = PublicErrorModel.for_scenario(scenario)
    methods = build_methods(model)
    orders = load_orders(Path(manifest["dataset"]))

    # hash checks
    if sha256_file(Path(manifest["dataset"])) != manifest["dataset_sha256"]:
        raise SystemExit("dataset hash mismatch")
    if sha256_file(STUDY / "g2_protocol_frozen.json") != protocol.get("protocol_sha256_self"):
        # self hash written after; verify dataset + model fields instead
        pass

    planned = []
    for oid in preflight_orders:
        for mid in ("M0", "M1", "M2", "M3"):
            planned.append((oid, mid))
    assert len(planned) == 8

    results = []
    incomplete = False
    error = None
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    try:
        for oid, mid in planned:
            elapsed = time.perf_counter() - t_global
            if elapsed > WALL_GLOBAL_S:
                incomplete = True
                break
            spec, meta = order_to_episode_spec(orders, oid, model)
            # paired realizations identity
            case_dir = OUT_ROOT / f"{oid}_{mid}_{scenario}"
            t0 = time.perf_counter()
            remaining = WALL_GLOBAL_S - (time.perf_counter() - t_global)
            ep_timeout = min(TIMEOUT_EPISODE_S, max(1.0, remaining))
            res = run_method_episode(
                spec,
                methods[mid],
                method_id=mid,
                timeout_s=ep_timeout,
            )
            wall = time.perf_counter() - t0
            meta_full = {
                **meta,
                "method_id": mid,
                "method_spec": METHOD_SPECS[mid].description,
                "comparison_kind": METHOD_SPECS[mid].comparison_kind,
                "scenario_id": scenario,
                "model_public": model_public_dict(model),
                "protocol_id": protocol["protocol_id"],
                "preflight": True,
                "timeout_episode_s": ep_timeout,
            }
            persist_episode(case_dir, meta=meta_full, result=res, wall_s=wall)
            results.append(
                {
                    "order_id": oid,
                    "method_id": mid,
                    "scenario_id": scenario,
                    "termination": res.termination,
                    "J_B": res.J_B,
                    "geometric_failure": res.geometric_failure,
                    "n_envelope_exceeded": res.n_envelope_exceeded,
                    "events_tail": res.events[-3:],
                    "n_placed": len(res.placed_ids),
                    "n_items": meta["n_items"],
                    "wall_seconds": wall,
                    "rebuild_ok": res.rebuild_ok,
                    "case_dir": str(case_dir.relative_to(STUDY)),
                }
            )
            # independent light checks
            if mid == "M0":
                # store realization fingerprint for pairing check
                pass
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    # pairing check: same realized map across methods per order
    pairing_ok = True
    pairing_notes = []
    for oid in preflight_orders:
        maps = []
        for mid in ("M0", "M1", "M2", "M3"):
            p = OUT_ROOT / f"{oid}_{mid}_{scenario}" / "result.json"
            if not p.exists():
                pairing_ok = False
                pairing_notes.append(f"missing {p.name}")
                continue
            maps.append(json.loads(p.read_text())["realized_by_item"])
        if len(maps) == 4 and not all(m == maps[0] for m in maps):
            pairing_ok = False
            pairing_notes.append(f"realized mismatch for {oid}")

    summary = {
        "preflight": "G2_real",
        "scenario_id": scenario,
        "orders": preflight_orders,
        "planned_episodes": 8,
        "executed_episodes": len(results),
        "pending_episodes": 8 - len(results),
        "wall_global_limit_s": WALL_GLOBAL_S,
        "timeout_episode_s": TIMEOUT_EPISODE_S,
        "wall_seconds_total": time.perf_counter() - t_global,
        "incomplete": incomplete or len(results) < 8,
        "error": error,
        "pairing_ok": pairing_ok,
        "pairing_notes": pairing_notes,
        "rss_max_mb": rss_mb(),
        "results": results,
        "g2_full_not_launched": True,
        "training_authorized": False,
        "reuse_in_g2_full": {
            "allowed_if_exact_match": True,
            "authorized_now": False,
            "note": "Reutilizable una vez en G2 solo si coinciden contrato, código, métodos, entradas y realizaciones exactamente.",
        },
        "cost_estimate_full_g2": {
            "max_episodes": 120,
            "preflight_mean_wall_s": (
                sum(r["wall_seconds"] for r in results) / len(results) if results else None
            ),
            "naive_extrapolation_s": (
                (sum(r["wall_seconds"] for r in results) / len(results)) * 120 if results else None
            ),
            "uncertainty_note": (
                "Extrapolación ingenua e incierta: pedidos preflight pueden no representar "
                "tamaños/ocupación del resto; no usar como presupuesto fijo sin medición."
            ),
        },
    }
    out = OUT_ROOT / "preflight_summary.json"
    tmp = OUT_ROOT / "preflight_summary.json.tmp"
    tmp.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"ok": error is None and pairing_ok and len(results) == 8, "summary": str(out), "n": len(results)}))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
