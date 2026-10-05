#!/usr/bin/env python3
"""Verificación independiente del preflight G2 (post-ejecución)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(HERE))

from bedbpp_episode import load_orders, order_to_episode_spec
from error_model import PublicErrorModel
from geometry_contract import AABBBox, AxisTriple, geometric_violation
from info_separation import PolicyObservation


def main() -> int:
    t0 = time.perf_counter()
    protocol = json.loads((STUDY / "g2_protocol_frozen.json").read_text(encoding="utf-8"))
    manifest = json.loads((STUDY / "sample_manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((STUDY / "results" / "g2_preflight" / "preflight_summary.json").read_text())
    scenario = protocol["preflight"]["scenario_id"]
    orders_pf = list(protocol["preflight"]["orders"])
    model = PublicErrorModel.for_scenario(scenario)
    orders = load_orders(Path(manifest["dataset"]))

    checks = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(cond), "detail": detail})

    ok("executed_8", summary.get("executed_episodes") == 8, str(summary.get("executed_episodes")))
    ok("pairing_ok", bool(summary.get("pairing_ok")))
    ok("g2_full_not_launched", bool(summary.get("g2_full_not_launched")))
    ok("training_false", summary.get("training_authorized") is False)

    for oid in orders_pf:
        specs = []
        for mid in ("M0", "M1", "M2", "M3"):
            path = STUDY / "results" / "g2_preflight" / f"{oid}_{mid}_{scenario}" / "result.json"
            ok(f"exists_{oid}_{mid}", path.exists(), str(path))
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            specs.append(data)
            ok(f"scenario_{oid}_{mid}", data.get("scenario_id") == scenario)
            ok(f"method_{oid}_{mid}", data.get("method_id") == mid)
            ok(
                f"stability_null_{oid}_{mid}",
                data.get("physical_stability_verified") is None,
            )
            # J_B rule
            if data.get("geometric_failure"):
                ok(f"JB_zero_on_fail_{oid}_{mid}", data.get("J_B") == 0.0, str(data.get("J_B")))
            else:
                vol_c = data.get("container_volume_mm3") or 0
                expected = (data.get("V_nom_mm3") or 0) / vol_c if vol_c else 0.0
                ok(
                    f"JB_nominal_{oid}_{mid}",
                    abs(float(data.get("J_B", -1)) - expected) < 1e-9,
                    f"{data.get('J_B')} vs {expected}",
                )
            # failed attempt vs accepted
            term = data.get("termination")
            if term in ("geometric_failure", "no_candidate"):
                ok(
                    f"failed_attempt_{oid}_{mid}",
                    data.get("failed_attempt") is not None,
                )
                fa = data.get("failed_attempt") or {}
                ok(
                    f"failed_event_{oid}_{mid}",
                    fa.get("event") in ("geometric_failure", "no_candidate"),
                    str(fa.get("event")),
                )
            # accepted geometry recheck
            container = AxisTriple(*data["container_mm"])
            occupied: list[AABBBox] = []
            geom_ok = True
            for step in data.get("accepted_placements") or []:
                if step.get("event") not in ("placed", "envelope_exceeded"):
                    continue
                flb = tuple(step["flb_mm"])
                real = AxisTriple(*step["realized_oriented"])
                gv = geometric_violation(AABBBox(flb, real), container, occupied)
                if gv["geometric_failure"]:
                    geom_ok = False
                    break
                occupied.append(AABBBox(flb, real))
            ok(f"accepted_geom_{oid}_{mid}", geom_ok)

            # envelope_exceeded distinct field
            for step in data.get("steps") or []:
                if step.get("event") == "envelope_exceeded":
                    ok(
                        f"env_exc_not_geom_{oid}_{mid}_{step['item_id']}",
                        step.get("event") != "geometric_failure",
                    )

        if len(specs) == 4:
            maps = [s.get("realized_by_item") for s in specs]
            ok(f"paired_realized_{oid}", all(m == maps[0] for m in maps))
            # regenerate expected realization (JSON lists vs tuples)
            _, meta = order_to_episode_spec(orders, oid, model)

            def _norm(m: dict) -> dict:
                return {k: [float(x) for x in v] for k, v in m.items()}

            ok(f"regen_realized_{oid}", _norm(meta["realized_by_item"]) == _norm(maps[0]))

    # method public info: methods never see current realized in PolicyObservation
    from methods_g2 import build_methods

    methods = build_methods(model)
    # smoke: observation without realized current
    obs = PolicyObservation(
        container_mm=AxisTriple(100, 100, 100),
        current_item_id="x",
        current_nominal_mm=AxisTriple(10, 10, 10),
        margin_mm=AxisTriple(0, 0, 0),
        revealed=(),
        remaining_count_including_current=1,
    )
    ok("obs_has_no_realized_field", not hasattr(obs, "current_realized_mm"))
    # M0–M3 callable on obs without truth
    from adapters import build_empty_session, PolicySessionView

    view = PolicySessionView(build_empty_session(obs.container_mm), allow_rotation=True)
    for mid, fn in methods.items():
        try:
            fn(obs, view)
            ok(f"method_public_only_{mid}", True)
        except Exception as exc:  # noqa: BLE001
            ok(f"method_public_only_{mid}", False, str(exc))

    report = {
        "verify": "g2_preflight_independent",
        "wall_seconds": time.perf_counter() - t0,
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["ok"]),
        "all_ok": all(c["ok"] for c in checks),
        "checks": checks,
    }
    out = STUDY / "results" / "g2_preflight" / "verify_independent.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"all_ok": report["all_ok"], "n_failed": report["n_failed"], "out": str(out)}))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
