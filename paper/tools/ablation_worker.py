#!/usr/bin/env python3
"""Un caso de la ablación, en un proceso nuevo. Una sola tentativa."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from ablation_pack import run_actor_problem, run_heuristic_problem
from ablation_train import configure_process_threads, load_research_checkpoint
from pilot_common import TIMEOUT_SECONDS, atomic_write_json, sha256_file
from pilot_problems import capture_document, prepare_imports


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    configure_process_threads()
    if job.get("attempts") not in (None, 1):
        raise ValueError("el caso admite una sola tentativa")
    started = time.perf_counter()
    role = job["role"]
    order_id = job["order_id"]
    dataset = Path(job["dataset"])
    prepare_imports()
    from problems import order_to_problem
    from splits import load_orders

    orders = load_orders(dataset)
    if role == "heuristic":
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=int(job["lookahead_p"]),
            select_s=int(job["select_s"]),
            algorithm_name="online_3d_bpp_heuristic",
            model_path=None,
        )
        solution = run_heuristic_problem(problem)
        method = "heuristic"
        checkpoint_path = dataset
    else:
        checkpoint_path = Path(job["checkpoint"])
        loaded = load_research_checkpoint(
            checkpoint_path,
            expected_standardizer_sha256=job.get("standardizer_sha256"),
        )
        if loaded["arm"] != job["arm"] or int(loaded["seed"]) != int(job["seed"]):
            raise ValueError("el artefacto no corresponde al brazo y la semilla del caso")
        problem = order_to_problem(
            orders,
            order_id,
            lookahead_p=int(job["lookahead_p"]),
            select_s=int(job["select_s"]),
            algorithm_name="drl_policy_3d_bpp",
            model_path=str(checkpoint_path),
        )
        solution = run_actor_problem(problem, loaded)
        method = "actor"
    document = capture_document(
        problem,
        solution,
        method=method,
        order_id=order_id,
        orders_path=dataset,
        orders_sha256=sha256_file(dataset),
        checkpoint_path=checkpoint_path,
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
    parser = argparse.ArgumentParser(description="Empaqueta un caso de la ablación.")
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
