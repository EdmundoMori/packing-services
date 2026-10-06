"""Selección determinista de muestra de preflight (sin packing)."""

from __future__ import annotations

from typing import Any


def select_by_item_count_quantiles(
    pool: list[dict[str, Any]],
    *,
    targets: tuple[str, str] = ("euro-pallet", "rollcontainer"),
    excluded_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Elige 2 pedidos por target: más cercano a q25 y q75 de n_items.

    ``pool`` elementos: ``{order_id, target, n_items}``.
    No observa utilizaciones. Empates: ``order_id`` lexicográficamente menor.
    """

    excluded = excluded_ids or set()
    selected: list[dict[str, Any]] = []
    by_target: dict[str, Any] = {}
    for target in targets:
        rows = [
            row
            for row in pool
            if row.get("target") == target and row.get("order_id") not in excluded
        ]
        if len(rows) < 2:
            raise ValueError(f"pool insuficiente para target {target}: {len(rows)}")
        rows = sorted(rows, key=lambda r: (int(r["n_items"]), str(r["order_id"])))
        n = len(rows)
        q25_idx = max(0, min(n - 1, (n - 1) // 4))
        q75_idx = max(0, min(n - 1, (3 * (n - 1)) // 4))
        if q25_idx == q75_idx:
            q75_idx = min(n - 1, q25_idx + 1)
        lower = rows[q25_idx]
        upper = rows[q75_idx]
        if lower["order_id"] == upper["order_id"]:
            upper = rows[min(n - 1, q75_idx + 1)]
        pair = [
            {
                "order_id": lower["order_id"],
                "target": target,
                "n_items": int(lower["n_items"]),
                "role": "lower_quantile",
                "quantile_index": q25_idx,
                "pool_n": n,
            },
            {
                "order_id": upper["order_id"],
                "target": target,
                "n_items": int(upper["n_items"]),
                "role": "upper_quantile",
                "quantile_index": q75_idx,
                "pool_n": n,
            },
        ]
        by_target[target] = pair
        selected.extend(pair)
    return {
        "rule": "within_target_item_count_quantiles_q25_q75",
        "n_orders": len(selected),
        "selected": selected,
        "by_target": by_target,
        "excluded_ids_n": len(excluded),
        "selection_before_utilization": True,
        "absolute_independence_not_claimed": True,
    }


def synthetic_metadata_pool() -> list[dict[str, Any]]:
    """Catálogo sintético solo para static-only / pruebas de la regla."""

    euro = [
        {"order_id": f"E{i:03d}", "target": "euro-pallet", "n_items": n}
        for i, n in enumerate([2, 3, 4, 5, 8, 10, 12, 15, 20, 30], start=1)
    ]
    roll = [
        {"order_id": f"R{i:03d}", "target": "rollcontainer", "n_items": n}
        for i, n in enumerate([1, 2, 4, 6, 7, 9, 11, 14, 18, 25], start=1)
    ]
    return euro + roll
