#!/usr/bin/env python3
"""Un pedido del teacher, en un proceso nuevo. Una sola tentativa."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from pilot_common import TIMEOUT_SECONDS, atomic_write_json
from teacher_probe import capture_teacher_case


def run_job(job: dict[str, Any]) -> dict[str, Any]:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    if job.get("attempts") not in (None, 1):
        raise ValueError("el pedido admite una sola tentativa")
    if int(job["lookahead_p"]) != 1 or int(job["select_s"]) != 1:
        raise ValueError("el diagnóstico usa p=s=1")
    started = time.perf_counter()
    dataset = Path(job["dataset"])
    prepare_and_load(dataset)
    from splits import load_orders

    orders = load_orders(dataset)
    _snapshot, document, diagnostics = capture_teacher_case(
        orders,
        job["order_id"],
        dataset_path=dataset,
    )
    return {
        "status": "ok",
        "error": None,
        "attempts": 1,
        "timeout_seconds": TIMEOUT_SECONDS,
        "duration_seconds": time.perf_counter() - started,
        "capture": document,
        "diagnostics": diagnostics,
    }


def prepare_and_load(dataset: Path) -> None:
    del dataset
    from pilot_problems import prepare_imports

    prepare_imports()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecuta el teacher sobre un pedido.")
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
            "diagnostics": None,
        }
    atomic_write_json(args.result.expanduser().resolve(), payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
