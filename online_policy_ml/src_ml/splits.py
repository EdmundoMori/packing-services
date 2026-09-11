"""Carga BED-BPP y split estricto por order_id."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from config import SEED, SPLIT_FRACTIONS, WORKING_COUNTS, SCALE_COUNTS
from paths import (
    BED_JSON_NAME,
    DEMO_BED_BPP,
    HOLDOUT_DIR,
    ORDER_IDS_NAME,
    RAW_DIR,
    SOURCE_BED_BPP,
    SPLITS_DIR,
    split_dir,
)


def load_orders(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not data:
        raise ValueError(f"Dataset vacío o inválido: {path}")
    return data


def order_item_count(order: dict[str, Any]) -> int:
    return len(order.get("item_sequence") or {})


def order_target(order: dict[str, Any]) -> str:
    return str((order.get("properties") or {}).get("target") or "?")


def demo_order_ids(demo_path: Path | None = None) -> list[str]:
    return sorted(load_orders(demo_path or DEMO_BED_BPP).keys())


def summarize_orders(orders: dict[str, Any]) -> dict[str, Any]:
    counts = [order_item_count(order) for order in orders.values()]
    targets: dict[str, int] = {}
    for order in orders.values():
        target = order_target(order)
        targets[target] = targets.get(target, 0) + 1
    counts_sorted = sorted(counts)
    n = len(counts_sorted)
    return {
        "n_orders": n,
        "n_items_min": counts_sorted[0] if n else 0,
        "n_items_p50": counts_sorted[n // 2] if n else 0,
        "n_items_mean": (sum(counts_sorted) / n) if n else 0.0,
        "n_items_p90": counts_sorted[int(n * 0.9)] if n else 0,
        "n_items_max": counts_sorted[-1] if n else 0,
        "targets": targets,
    }


def split_order_ids(
    all_ids: Iterable[str],
    *,
    blocked: Iterable[str],
    seed: int = SEED,
    fractions: dict[str, float] | None = None,
) -> dict[str, list[str]]:
    frac = fractions or SPLIT_FRACTIONS
    blocked_set = set(blocked)
    eligible = [oid for oid in sorted(all_ids) if oid not in blocked_set]
    rng = random.Random(seed)
    rng.shuffle(eligible)
    n = len(eligible)
    n_train = int(round(frac["train"] * n))
    n_val = int(round(frac["val"] * n))
    train = eligible[:n_train]
    val = eligible[n_train : n_train + n_val]
    test = eligible[n_train + n_val :]
    return {"train": train, "val": val, "test": test}


def working_subset(
    full_split: dict[str, list[str]],
    orders: dict[str, Any],
) -> dict[str, list[str]]:
    """Pedidos más cortos de cada split (el demo sigue fuera)."""

    out: dict[str, list[str]] = {}
    for name, ids in full_split.items():
        ranked = sorted(ids, key=lambda oid: (order_item_count(orders[oid]), oid))
        out[name] = ranked[: WORKING_COUNTS[name]]
    return out


def scale_subset(full_split: dict[str, list[str]]) -> dict[str, list[str]]:
    """Primeros K de cada split ya barajado (muestra aleatoria, semilla 42)."""

    return {name: ids[: SCALE_COUNTS[name]] for name, ids in full_split.items()}


def subset_orders(orders: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    missing = [oid for oid in ids if oid not in orders]
    if missing:
        raise KeyError(f"order_id ausente: {missing[:5]}")
    return {oid: orders[oid] for oid in ids}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def materialize_splits(
    source_orders: dict[str, Any],
    full_split: dict[str, list[str]],
    working: dict[str, list[str]],
    demo_orders: dict[str, Any],
) -> dict[str, Path]:
    written: dict[str, Path] = {}
    write_json(SPLITS_DIR / "full_split.json", full_split)
    write_json(SPLITS_DIR / "working_split.json", working)
    write_json(
        SPLITS_DIR / "blocked_demo_ids.json",
        {
            "reason": "examples/5_bed-bpp.json — ni train ni tune",
            "order_ids": demo_order_ids(),
        },
    )
    write_json(
        RAW_DIR / "source_pointer.json",
        {
            "source_path": str(SOURCE_BED_BPP),
            "n_orders_source": len(source_orders),
            "note": "No se copia bed-bpp_v1.json (75 MB). Los JSON de trabajo están en data/train|val|test.",
        },
    )
    written["source_pointer"] = RAW_DIR / "source_pointer.json"

    for name, ids in working.items():
        dest_dir = split_dir(name)
        write_json(dest_dir / ORDER_IDS_NAME, ids)
        write_json(SPLITS_DIR / f"{name}_order_ids_full.json", full_split[name])
        bed_path = dest_dir / BED_JSON_NAME
        write_json(bed_path, subset_orders(source_orders, ids))
        written[name] = bed_path

    holdout_path = HOLDOUT_DIR / "5_bed-bpp.json"
    write_json(holdout_path, demo_orders)
    write_json(HOLDOUT_DIR / ORDER_IDS_NAME, sorted(demo_orders.keys()))
    written["holdout_producto"] = holdout_path
    return written


def materialize_scale(
    source_orders: dict[str, Any],
    scale: dict[str, list[str]],
) -> dict[str, Path]:
    """Escribe data/scale/* sin pisar los JSON cortos de las fases 1–3."""

    from paths import scale_split_dir

    written: dict[str, Path] = {}
    write_json(SPLITS_DIR / "scale_split.json", scale)
    for name, ids in scale.items():
        dest = scale_split_dir(name)
        dest.mkdir(parents=True, exist_ok=True)
        write_json(dest / ORDER_IDS_NAME, ids)
        bed_path = dest / BED_JSON_NAME
        write_json(bed_path, subset_orders(source_orders, ids))
        written[name] = bed_path
    return written
