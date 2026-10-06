"""Problemas sintéticos compactos para R02. No usa pedidos BED-BPP reales."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_PAPER_TOOLS = _HERE.parents[2] / "tools"
for _entry in (str(_PAPER_TOOLS),):
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

from compact_study import build_compact_problem  # noqa: E402


def synthetic_order(
    order_id: str,
    items: list[tuple[str, int, int, int]],
    *,
    target: str = "euro-pallet",
    weight_kg: float = 1.0,
) -> dict[str, Any]:
    sequence: dict[str, Any] = {}
    for index, (name, length, width, height) in enumerate(items, start=1):
        sequence[str(index)] = {
            "sequence": index,
            "id": name,
            "length/mm": length,
            "width/mm": width,
            "height/mm": height,
            "weight/kg": weight_kg,
        }
    return {
        order_id: {
            "properties": {"target": target},
            "item_sequence": sequence,
        }
    }


def make_problem(
    order_id: str,
    items: list[tuple[str, int, int, int]],
    *,
    target: str = "euro-pallet",
) -> Any:
    return build_compact_problem(synthetic_order(order_id, items, target=target), order_id)


def scenario_catalog() -> dict[str, Any]:
    """Escenarios sintéticos nombrados (solo geometría artificial)."""

    return {
        "all_fit": make_problem(
            "syn-all-fit",
            [("a", 200, 180, 120), ("b", 150, 140, 100), ("c", 80, 80, 80)],
        ),
        "first_impossible": make_problem(
            "syn-first-imp",
            [("big", 2000, 2000, 2000), ("tail", 100, 100, 100)],
        ),
        "next_impossible": make_problem(
            "syn-next-imp",
            [("a", 1100, 700, 1800), ("b", 1100, 700, 1800)],
        ),
        "two_fit": make_problem(
            "syn-two-fit",
            [("a", 200, 180, 120), ("b", 150, 140, 100)],
        ),
        "suffix_independence_base": make_problem(
            "syn-sfx-base",
            [("a", 200, 180, 120), ("u", 50, 50, 50), ("v", 40, 40, 40)],
        ),
        "suffix_independence_alt": make_problem(
            "syn-sfx-alt",
            [("a", 200, 180, 120), ("x", 300, 200, 150), ("y", 90, 90, 90)],
        ),
    }
