"""Un pedido GreedyBestFit con el contrato compacto. No entrena."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import build_compact_problem, capture_compact_case, run_compact_greedy  # noqa: E402
from pilot_common import atomic_write_json  # noqa: E402
from pilot_problems import prepare_imports  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    process_started = time.perf_counter()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    prepare_imports()
    from splits import load_orders

    orders = load_orders(Path(job["dataset"]))
    problem = build_compact_problem(orders, job["order_id"])
    ready = time.perf_counter()
    solution, diagnostics = run_compact_greedy(problem)
    document = capture_compact_case(
        problem,
        solution,
        order_id=job["order_id"],
        dataset=job["dataset"],
        dataset_sha256=job["dataset_sha256"],
    )
    finished = time.perf_counter()
    atomic_write_json(
        args.result,
        {
            "status": "ok",
            "error": None,
            "attempts": 1,
            "timeout_seconds": 300,
            "capture": document,
            "diagnostics": diagnostics,
            "timings": {
                "startup_seconds": ready - process_started,
                "packing_loop_seconds": diagnostics["packing_loop_seconds"],
                "capture_build_seconds": finished - ready - diagnostics["packing_loop_seconds"],
            },
            "returncode": 0,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        destination = Path(sys.argv[sys.argv.index("--result") + 1])
        atomic_write_json(
            destination,
            {
                "status": "crash",
                "error": f"{type(exc).__name__}: {exc}",
                "worker_failure": "crash",
                "attempts": 1,
                "capture": None,
                "diagnostics": None,
                "returncode": 0,
            },
        )
        raise SystemExit(0)
