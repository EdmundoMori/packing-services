"""Endpoint de benchmark/comparación de algoritmos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Query
from pydantic import ValidationError

from pathlib import Path

from ...benchmark.joint_single_container import (
    DEFAULT_TARGET,
    run_joint_single_container,
)
from ...datasets.bed_bpp import looks_like_bed_bpp_orders, normalize_benchmark_payload
from ...domain.enums import ProblemType
from ...schemas.requests import BenchmarkRequest
from ...schemas.responses import BenchmarkResponse
from ...services.benchmark_service import BenchmarkService
from ...utils.errors import InvalidInputError

router = APIRouter(tags=["benchmark"])
_service = BenchmarkService()


@router.get("/benchmark/profiles")
def list_benchmark_profiles(
    problem_type: ProblemType | None = Query(default=None),
) -> dict:
    """Lista perfiles estándar de benchmark (motores comparables por tipo de problema)."""

    return {"profiles": _service.list_profiles(problem_type)}


@router.post("/benchmark", response_model=BenchmarkResponse)
def benchmark(
    payload: dict[str, Any] = Body(
        ...,
        description=(
            "BenchmarkRequest estándar, o entrada BED-BPP con "
            "input_format=bed_bpp + order_id + orders."
        ),
    ),
) -> BenchmarkResponse:
    """Ejecuta varios algoritmos sobre la misma instancia y los compara."""

    normalized = normalize_benchmark_payload(payload)
    try:
        request = BenchmarkRequest.model_validate(normalized)
    except ValidationError as exc:
        raise InvalidInputError(str(exc)) from exc
    return _service.benchmark(request)


_SAMPLE_PATH = Path(__file__).resolve().parents[4] / "examples" / "5_bed-bpp.json"


def _load_sample_orders() -> dict[str, Any]:
    if not _SAMPLE_PATH.exists():
        raise InvalidInputError(f"Muestra BED-BPP no encontrada: {_SAMPLE_PATH}")
    return json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))


@router.post("/benchmark/joint-single-container", response_model=BenchmarkResponse)
def benchmark_joint_single_container(
    payload: dict[str, Any] | None = Body(default=None),
) -> BenchmarkResponse:
    """Compara 3D_BPP, SCL, PALLETIZATION y STACKING_AWARE en un euro-pallet.

    Mismo pedido BED-BPP (el más pequeño si no se indica ``order_id``),
    mismo validador y mismas métricas. ``packing_mode=offline`` (default)
    reordena por volumen; ``packing_mode=online`` respeta la llegada.
    """

    body = payload or {}
    orders = body.get("orders") or body.get("bed_bpp")
    if orders is None:
        orders = _load_sample_orders()
    elif not looks_like_bed_bpp_orders(orders):
        raise InvalidInputError("Campo 'orders' no tiene estructura BED-BPP válida")

    return run_joint_single_container(
        orders,
        order_id=body.get("order_id"),
        target=body.get("target") or DEFAULT_TARGET,
        sort_strategy=body.get("sort_strategy"),
        packing_mode=body.get("packing_mode"),
        request_id=body.get("request_id"),
    )
