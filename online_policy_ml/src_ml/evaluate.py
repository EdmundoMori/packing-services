"""Evaluación packing_mode=online: modelo vs heurístico vs placeholder."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.online.learned.policy import LearnedPlacementPolicy

from problems import order_to_problem


def run_engine(
    orders: dict[str, Any],
    order_id: str,
    *,
    engine: str,
    lookahead_p: int,
    select_s: int,
    model_path: str | None = None,
) -> dict[str, Any]:
    if engine == "heuristic":
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="online_3d_bpp_heuristic",
        )
        t0 = time.perf_counter()
        solution = Online3DBPPHeuristic().run(problem)
    elif engine == "learned":
        if not model_path:
            raise ValueError("learned requiere model_path")
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name="drl_policy_3d_bpp",
            model_path=model_path,
        )
        t0 = time.perf_counter()
        solution = DRLPolicy3DBPP().run(problem)
    else:
        raise ValueError(engine)

    report = solution.validation_report
    return {
        "order_id": order_id,
        "engine": engine,
        "model_path": model_path,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "volume_utilization": solution.metrics.volume_utilization,
        "items_packed": solution.metrics.items_packed,
        "items_unpacked": solution.metrics.items_unpacked,
        "is_valid": bool(report and report.is_valid),
        "seconds": time.perf_counter() - t0,
        "n_items": len(problem.items),
    }


def evaluate_orders(
    orders: dict[str, Any],
    order_ids: list[str],
    *,
    engine: str,
    lookahead_p: int,
    select_s: int,
    model_path: str | None = None,
    max_orders: int | None = None,
) -> list[dict[str, Any]]:
    ids = order_ids[:max_orders] if max_orders else order_ids
    return [
        run_engine(
            orders,
            oid,
            engine=engine,
            lookahead_p=lookahead_p,
            select_s=select_s,
            model_path=model_path,
        )
        for oid in ids
    ]


def smoke_from_path(model_path: Path, orders: dict[str, Any], order_id: str) -> dict[str, Any]:
    LearnedPlacementPolicy.from_path(model_path)
    return run_engine(
        orders,
        order_id,
        engine="learned",
        lookahead_p=1,
        select_s=1,
        model_path=str(model_path),
    )


def write_report(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
