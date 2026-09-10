"""Endpoints de datasets de entrada (BED-BPP integrado en el flujo canónico)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Query

from ...datasets.bed_bpp import (
    BED_BPP_COMPATIBLE_PROBLEM_TYPES,
    TARGET_SIZES_MM,
    convert_order_to_benchmark_input,
    convert_order_to_pack_input,
    list_order_ids,
    looks_like_bed_bpp_orders,
)
from ...domain.enums import ProblemType
from ...utils.errors import InvalidInputError

router = APIRouter(tags=["datasets"])

_EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
_SAMPLE_PATH = _EXAMPLES / "5_bed-bpp.json"


def _load_sample() -> dict[str, Any]:
    if not _SAMPLE_PATH.exists():
        raise InvalidInputError(f"Muestra BED-BPP no encontrada: {_SAMPLE_PATH}")
    return json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))


@router.get("/datasets/bed-bpp/sample")
def get_bed_bpp_sample() -> dict[str, Any]:
    """Devuelve la muestra ``5_bed-bpp.json`` (5 pedidos) embebida en el proyecto."""
    orders = _load_sample()
    return {
        "dataset": "BED-BPP",
        "source": "5_bed-bpp.json",
        "n_orders": len(orders),
        "order_ids": list_order_ids(orders),
        "targets": TARGET_SIZES_MM,
        "compatible_problem_types": [p.value for p in BED_BPP_COMPATIBLE_PROBLEM_TYPES],
        "orders": orders,
    }


@router.get("/datasets/bed-bpp/orders")
def list_bed_bpp_sample_orders() -> dict[str, Any]:
    """Lista ids de pedido de la muestra local (sin el payload completo)."""
    orders = _load_sample()
    summaries = []
    for oid in list_order_ids(orders):
        props = orders[oid].get("properties") or {}
        summaries.append(
            {
                "order_id": oid,
                "order_nr": props.get("order_nr"),
                "target": props.get("target"),
                "type": props.get("type"),
                "n_items": len(orders[oid].get("item_sequence") or {}),
            }
        )
    return {"dataset": "BED-BPP", "orders": summaries}


@router.post("/datasets/bed-bpp/convert")
def convert_bed_bpp(
    payload: dict[str, Any] = Body(
        ...,
        examples={
            "from_sample_order": {
                "summary": "Convertir un pedido de la muestra",
                "value": {
                    "order_id": "00100001",
                    "problem_type": "PALLETIZATION",
                    "mode": "execute",
                },
            }
        },
    ),
    problem_type: ProblemType | None = Query(default=None),
) -> dict[str, Any]:
    """Convierte un pedido BED-BPP al contrato PackAlgorithmInput / BenchmarkRequest.

    Body:
    - ``orders`` (opcional): mapa BED-BPP; si falta, se usa la muestra ``5_bed-bpp.json``
    - ``order_id`` (obligatorio)
    - ``problem_type`` (default PALLETIZATION)
    - ``mode``: ``execute`` | ``benchmark``
    - ``target`` (opcional): fuerza el contenedor (`euro-pallet`, `rollcontainer`)
    """
    order_id = payload.get("order_id")
    if not order_id:
        raise InvalidInputError("Se requiere 'order_id'")

    orders = payload.get("orders") or payload.get("bed_bpp")
    if orders is None:
        orders = _load_sample()
    elif not looks_like_bed_bpp_orders(orders):
        raise InvalidInputError("Campo 'orders' no tiene estructura BED-BPP válida")

    pt = problem_type or payload.get("problem_type") or ProblemType.PALLETIZATION
    if isinstance(pt, str):
        pt = ProblemType(pt)

    mode = (payload.get("mode") or "execute").lower()
    if mode == "benchmark":
        converted = convert_order_to_benchmark_input(
            orders,
            str(order_id),
            problem_type=pt,
            engines=payload.get("engines"),
            profile=payload.get("profile"),
            parameters=payload.get("parameters"),
            constraints=payload.get("constraints"),
            request_id=payload.get("request_id"),
            target_override=payload.get("target"),
        )
    else:
        converted = convert_order_to_pack_input(
            orders,
            str(order_id),
            problem_type=pt,
            parameters=payload.get("parameters"),
            constraints=payload.get("constraints"),
            request_id=payload.get("request_id"),
            random_seed=payload.get("random_seed"),
            time_limit_seconds=payload.get("time_limit_seconds"),
            target_override=payload.get("target"),
        )

    details = converted.pop("details", {})
    return {
        "dataset": "BED-BPP",
        "order_id": order_id,
        "mode": mode,
        "details": details,
        "input": converted,
    }
