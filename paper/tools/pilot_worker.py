#!/usr/bin/env python3
"""Un método y un pedido, en un proceso nuevo. Una sola tentativa."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from pilot_common import TIMEOUT_SECONDS, atomic_write_json, sha256_file
from pilot_problems import build_problem, capture_document, prepare_imports


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    started = time.perf_counter()
    method = job["method"]
    order_id = job["order_id"]
    dataset = Path(job["dataset"])
    checkpoint = Path(job["checkpoint"])
    prepare_imports()
    from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
    from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
    from splits import load_orders

    orders = load_orders(dataset)
    problem = build_problem(
        orders,
        order_id,
        method,
        checkpoint,
        lookahead_p=int(job["lookahead_p"]),
        select_s=int(job["select_s"]),
    )
    if method == "actor":
        solution = DRLPolicy3DBPP().run(problem)
    elif method == "heuristic":
        solution = Online3DBPPHeuristic().run(problem)
    else:
        raise ValueError(f"método desconocido: {method}")
    document = capture_document(
        problem,
        solution,
        method=method,
        order_id=order_id,
        orders_path=dataset,
        orders_sha256=sha256_file(dataset),
        checkpoint_path=checkpoint,
    )
    return {
        "status": "ok",
        "error": None,
        "attempts": 1,
        "timeout_seconds": TIMEOUT_SECONDS,
        "duration_seconds": time.perf_counter() - started,
        "capture": document,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta un método sobre un pedido.")
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    job = json.loads(args.job.expanduser().resolve().read_text(encoding="utf-8"))
    try:
        payload = run_job(job)
    except Exception as exc:
        payload = {
            "status": "crash",
            "error": f"{type(exc).__name__}: {exc}",
            "attempts": 1,
            "timeout_seconds": TIMEOUT_SECONDS,
            "duration_seconds": time.perf_counter() - started,
            "capture": None,
        }
    atomic_write_json(args.result.expanduser().resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
