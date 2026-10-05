"""Carga pedidos BED-BPP → EpisodeSpec con realizaciones del modelo sintético."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packing_services.datasets.bed_bpp import convert_order_to_pack_input

from error_model import PublicErrorModel, expand_nominal
from geometry_contract import AxisTriple, validate_positive_dims
from info_separation import EpisodeSpec, SyntheticItem, make_item


def load_orders(dataset_path: Path) -> dict[str, Any]:
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def order_to_episode_spec(
    orders: dict[str, Any],
    order_id: str,
    model: PublicErrorModel,
) -> tuple[EpisodeSpec, dict[str, Any]]:
    payload = convert_order_to_pack_input(
        orders,
        order_id,
        packing_mode="online",
        parameters={"lookahead_p": 1, "select_s": 1, "sort_strategy": "input_order"},
    )
    containers = payload["containers"]
    if len(containers) != 1:
        raise RuntimeError(f"se esperaba 1 contenedor, got {len(containers)}")
    c = containers[0]
    container = validate_positive_dims((c["length"], c["width"], c["height"]), "container")
    items_out: list[SyntheticItem] = []
    realized_map: dict[str, tuple[float, float, float]] = {}
    # Preserve arrival order
    items_sorted = sorted(
        payload["items"],
        key=lambda it: (it.get("arrival_index") is None, it.get("arrival_index") or 0, it["id"]),
    )
    for it in items_sorted:
        nom = validate_positive_dims((it["length"], it["width"], it["height"]), f"{it['id']}.nominal")
        real = expand_nominal(nom, model.alpha)
        items_out.append(SyntheticItem(item_id=it["id"], nominal_mm=nom, realized_mm=real))
        realized_map[it["id"]] = real.as_tuple()
    spec = EpisodeSpec(container_mm=container, items=items_out, allow_rotation=True)
    meta = {
        "order_id": order_id,
        "target": (orders[order_id].get("properties") or {}).get("target"),
        "n_items": len(items_out),
        "container_mm": container.as_tuple(),
        "realized_by_item": realized_map,
        "model": {
            "scenario_id": model.scenario_id,
            "alpha": model.alpha,
            "model_id": model.model_id,
        },
        "constraints_active": ["containment", "non_overlap", "orientations"],
        "physical_stability_verified": None,
    }
    return spec, meta
