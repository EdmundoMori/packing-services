"""Rutas dedicadas de packing online con política aprendida.

El catálogo canónico sigue siendo POST /algorithms/drl_policy_3d_bpp/execute.
Estas rutas fuerzan packing_mode=online y el algoritmo drl_policy_3d_bpp con
el checkpoint RL (PPO). No añaden un motor al catálogo.
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
    PPO_MODEL_PATH,
    apply_policy_preset,
    rl_learned_parameters,
)
from ...schemas.responses import AlgorithmExecuteResponse
from ...services.algorithm_execution_service import AlgorithmExecutionService
from ...utils.errors import InvalidInputError

ALGORITHM_NAME = "drl_policy_3d_bpp"

router = APIRouter(tags=["online-learned"])
_service = AlgorithmExecutionService()


def _execute_online(payload: dict[str, Any], *, route: str) -> AlgorithmExecuteResponse:
    if not isinstance(payload, dict):
        raise InvalidInputError("El body debe ser un objeto JSON.")
    mode = payload.get("packing_mode")
    if mode not in (None, "", "online"):
        raise InvalidInputError(f"POST {route} solo admite packing_mode=online.")
    params = apply_policy_preset(dict(payload.get("parameters") or {}))
    body = {
        **payload,
        "packing_mode": "online",
        "parameters": params,
    }
    return _service.execute(ALGORITHM_NAME, body)


@router.post(
    "/online/learned/execute",
    response_model=AlgorithmExecuteResponse,
    summary="Ejecutar packing online con política RL (PPO)",
    description=(
        "Misma entrada que execute (PackAlgorithmInput o wrapper BED-BPP). "
        "Fuerza packing_mode=online y el algoritmo drl_policy_3d_bpp con el "
        f"checkpoint PPO ({DEFAULT_MODEL_PATH}). Alias de /online/rl/execute. "
        "Los .pt necesitan pip install 'packing-services[torch]'. "
        "model_path vacío no hace fallback al greedy."
    ),
)
def execute_learned_online(
    payload: dict[str, Any] = Body(
        ...,
        examples={
            "produccion_o3dbp": {
                "summary": "Holdout 00100408 + PPO p=1 s=1",
                "value": {
                    "input_format": "bed_bpp",
                    "order_id": "00100408",
                    "problem_type": "PALLETIZATION",
                    "packing_mode": "online",
                    "parameters": {
                        "policy": "rl",
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
            "rl_ppo": {
                "summary": "RL (PPO) sobre el mismo MLP",
                "value": {
                    "input_format": "bed_bpp",
                    "order_id": "00100408",
                    "problem_type": "PALLETIZATION",
                    "packing_mode": "online",
                    "parameters": {
                        "policy": "rl",
                        "model_path": PPO_MODEL_PATH,
                    },
                },
            },
        },
    ),
) -> AlgorithmExecuteResponse:
    return _execute_online(payload, route="/online/learned/execute")


@router.post(
    "/online/rl/execute",
    response_model=AlgorithmExecuteResponse,
    summary="Ejecutar packing online con política RL (PPO)",
    description=(
        "Igual que /online/learned/execute: fuerza parameters.policy=rl "
        f"y el checkpoint PPO de producción ({PPO_MODEL_PATH}). "
        "Sigue siendo drl_policy_3d_bpp: no hay un algoritmo nuevo en el "
        "catálogo. Entrenos nuevos van a online_policy_ml/versions/v2/."
    ),
)
def execute_rl_online(
    payload: dict[str, Any] = Body(
        ...,
        examples={
            "rl_holdout": {
                "summary": "Holdout 00100408 + PPO p=1 s=1",
                "value": {
                    "input_format": "bed_bpp",
                    "order_id": "00100408",
                    "problem_type": "PALLETIZATION",
                    "packing_mode": "online",
                    "parameters": rl_learned_parameters(),
                },
            },
        },
    ),
) -> AlgorithmExecuteResponse:
    if not isinstance(payload, dict):
        raise InvalidInputError("El body debe ser un objeto JSON.")
    params = dict(payload.get("parameters") or {})
    params["policy"] = "rl"
    if not params.get("model_path"):
        params["model_path"] = PPO_MODEL_PATH
    return _execute_online({**payload, "parameters": params}, route="/online/rl/execute")
