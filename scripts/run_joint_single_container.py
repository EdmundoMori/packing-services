#!/usr/bin/env python3
"""Ejecuta el experimento conjunto BED-BPP (euro-pallet, packing_mode=offline).

Uso::

    PYTHONPATH=src python scripts/run_joint_single_container.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from packing_services.benchmark.joint_single_container import (  # noqa: E402
    run_joint_single_container,
)


def main() -> int:
    sample = ROOT / "examples" / "5_bed-bpp.json"
    orders = json.loads(sample.read_text(encoding="utf-8"))
    response = run_joint_single_container(orders, target="euro-pallet")
    d = response.details
    print(
        f"Pedido {d['order_id']} · {d['n_items']} ítems · "
        f"mode={d.get('packing_mode')} · target={d['target']} {d['container_size']} · "
        f"sort={d['sort_strategy']}"
    )
    print(f"Válidos: {d['engines_valid']}/{d['engines_total']} · mejor: {d['best_engine']}")
    print()
    header = (
        f"{'motor':<48} {'ok':>4} {'emp.':>5} {'no':>4} "
        f"{'util':>8} {'t(s)':>8}"
    )
    print(header)
    print("-" * len(header))
    by_engine = {r.engine: r for r in response.results}
    for name in response.ranking:
        r = by_engine[name]
        m = r.metrics
        print(
            f"{name:<48} {str(r.is_valid):>4} {m.items_packed:>5} "
            f"{m.items_unpacked:>4} {m.volume_utilization:>7.1%} "
            f"{m.execution_time_seconds:>8.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
