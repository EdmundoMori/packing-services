#!/usr/bin/env python3
"""Preflight G1 sintético corto. Límite de pared: 120 s. Sin BED-BPP / PPO."""

from __future__ import annotations

import json
import resource
import sys
import time
import traceback
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE
sys.path.insert(0, str(TOOLS))

from baselines import margin_axis, margin_uniform, margin_zero
from episode import ProtectionEpisode
from info_separation import EpisodeSpec

WALL_LIMIT_S = 120.0
OUT = HERE.parent / "results" / "g1_preflight.json"


def rss_mb() -> float | None:
    # Linux: ru_maxrss en KB.
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return None


def main() -> int:
    t0 = time.perf_counter()
    tracemalloc.start()
    cases = []
    incomplete = False
    error = None

    scenarios = [
        ("zero_error", (100, 100, 100), [("a", (20, 20, 20), (20, 20, 20))], margin_zero),
        ("smaller", (100, 100, 100), [("a", (20, 20, 20), (12, 12, 12))], margin_zero),
        (
            "exceed_continue",
            (100, 100, 100),
            [("a", (20, 20, 20), (25, 20, 20)), ("b", (10, 10, 10), (10, 10, 10))],
            margin_zero,
        ),
        (
            "exceed_exit",
            (55, 55, 55),
            [("a", (50, 50, 50), (60, 50, 50))],
            margin_zero,
        ),
        (
            "no_candidate_partial",
            (50, 50, 50),
            [("a", (20, 20, 20), (20, 20, 20)), ("b", (40, 40, 40), (40, 40, 40))],
            lambda obs: margin_zero() if obs.current_item_id == "a" else margin_uniform(30)(),
        ),
        (
            "uniform_margin",
            (100, 100, 100),
            [("a", (30, 30, 30), (32, 30, 30))],
            margin_uniform(5),
        ),
        (
            "axis_margin",
            (100, 100, 100),
            [("a", (10, 20, 30), (11, 20, 32))],
            margin_axis((1, 0, 2)),
        ),
    ]

    try:
        for name, container, items, marg in scenarios:
            if time.perf_counter() - t0 > WALL_LIMIT_S:
                incomplete = True
                break
            spec = EpisodeSpec.build(container, items)
            res = ProtectionEpisode(spec, margin_fn=marg).run()
            cases.append(
                {
                    "name": name,
                    "termination": res.termination,
                    "J_B": res.J_B,
                    "V_nom_mm3": res.V_nom_mm3,
                    "V_nom_before_failure_mm3": res.V_nom_before_failure_mm3,
                    "geometric_failure": res.geometric_failure,
                    "n_envelope_exceeded": res.n_envelope_exceeded,
                    "events": res.events,
                    "rebuild_ok": res.rebuild_ok,
                    "rebuild_note": res.rebuild_note,
                    "placed_ids": res.placed_ids,
                }
            )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    wall = time.perf_counter() - t0

    payload = {
        "preflight": "G1_synthetic",
        "wall_limit_seconds": WALL_LIMIT_S,
        "wall_seconds": wall,
        "incomplete": incomplete or wall > WALL_LIMIT_S,
        "error": error,
        "n_cases": len(cases),
        "cases": cases,
        "memory": {
            "tracemalloc_current_mb": current / (1024 * 1024),
            "tracemalloc_peak_mb": peak / (1024 * 1024),
            "rss_max_mb": rss_mb(),
            "note": "tracemalloc ≠ RSS; rss_max_mb from resource.ru_maxrss",
        },
        "training_authorized": False,
        "bed_bpp_read": False,
        "ppo_implemented": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": error is None and not payload["incomplete"], "wall_seconds": wall, "out": str(OUT)}))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
