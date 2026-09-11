"""Ruta dedicada de packing online con política aprendida.

El catálogo canónico sigue siendo POST /algorithms/drl_policy_3d_bpp/execute.
Esta ruta fuerza packing_mode=online y el algoritmo DRL para no mezclarlo
con el heurístico.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from ...online.learned.production import (
    CINTA_LOOKAHEAD_P,
    CINTA_MODEL_PATH,
    CINTA_SELECT_S,
    DEFAULT_LOOKAHEAD_P,
    DEFAULT_MODEL_PATH,
    DEFAULT_SELECT_S,
)
from ...schemas.responses import AlgorithmExecuteResponse
from ...services.algorithm_execution_service import AlgorithmExecutionService
from ...utils.errors import InvalidInputError

ALGORITHM_NAME = "drl_policy_3d_bpp"

router = APIRouter(tags=["online-learned"])
_service = AlgorithmExecutionService()


@router.post(
    "/online/learned/execute",
    response_model=AlgorithmExecuteResponse,
    summary="Ejecutar packing online con política aprendida",
    description=(
        "Misma entrada que execute (PackAlgorithmInput o wrapper BED-BPP). "
        "Fuerza packing_mode=online y el algoritmo drl_policy_3d_bpp. "
        "Si no envía model_path, usa el MLP de producción p=1 s=1 "
        f"({DEFAULT_MODEL_PATH}). Los .pt necesitan "
        "pip install 'packing-services[torch]'. "
        "model_path vacío no hace fallback al greedy."
    ),
)
def execute_learned_online(
    payload: dict[str, Any] = Body(
        ...,
        examples={
            "produccion_o3dbp": {
                "summary": "Holdout 00100408 + MLP p=1 s=1",
                "value": {
                    "input_format": "bed_bpp",
                    "order_id": "00100408",
                    "problem_type": "PALLETIZATION",
                    "packing_mode": "online",
                    "parameters": {
                        "model_path": DEFAULT_MODEL_PATH,
                        "lookahead_p": DEFAULT_LOOKAHEAD_P,
                        "select_s": DEFAULT_SELECT_S,
                    },
                },
            },
            "cinta": {
                "summary": "Cinta receding-horizon p=3 s=2",
                "value": {
                    "input_format": "bed_bpp",
                    "order_id": "00100408",
                    "problem_type": "PALLETIZATION",
                    "packing_mode": "online",
                    "parameters": {
                        "model_path": CINTA_MODEL_PATH,
                        "lookahead_p": CINTA_LOOKAHEAD_P,
                        "select_s": CINTA_SELECT_S,
                    },
                },
            },
        },
    ),
) -> AlgorithmExecuteResponse:
    if not isinstance(payload, dict):
        raise InvalidInputError("El body debe ser un objeto JSON.")
    mode = payload.get("packing_mode")
    if mode not in (None, "", "online"):
        raise InvalidInputError(
            "POST /online/learned/execute solo admite packing_mode=online."
        )
    params = dict(payload.get("parameters") or {})
    body = {
        **payload,
        "packing_mode": "online",
        "parameters": params,
    }
    return _service.execute(ALGORITHM_NAME, body)
