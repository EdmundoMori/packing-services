"""BED-BPP → PackingProblem sin pasar por la API."""

from __future__ import annotations

from typing import Any

from packing_services.datasets.bed_bpp import convert_order_to_pack_input
from packing_services.domain.models import AlgorithmConfig, PackingProblem

from config import PROBLEM_TYPE, SELECTION


def online_params(
    lookahead_p: int,
    select_s: int,
    *,
    model_path: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "sort_strategy": "input_order",
        "lookahead_p": int(lookahead_p),
        "select_s": int(select_s),
        "selection": SELECTION,
    }
    if model_path:
        params["model_path"] = model_path
    return params


def order_to_problem(
    orders: dict[str, Any],
    order_id: str,
    *,
    lookahead_p: int,
    select_s: int,
    packing_mode: str = "online",
    problem_type: str = PROBLEM_TYPE,
    algorithm_name: str = "drl_policy_3d_bpp",
    model_path: str | None = None,
) -> PackingProblem:
    params = online_params(lookahead_p, select_s, model_path=model_path)
    payload = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=problem_type,
        parameters=params,
        packing_mode=packing_mode,
    )
    return PackingProblem(
        problem_type=payload["problem_type"],
        request_id=payload.get("request_id"),
        containers=payload["containers"],
        items=payload["items"],
        constraints=payload["constraints"],
        objective=payload.get("objective", "maximize_volume_utilization"),
        algorithm=AlgorithmConfig(name=algorithm_name, parameters=params),
    )
