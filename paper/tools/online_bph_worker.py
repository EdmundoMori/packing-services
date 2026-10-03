"""Un pedido OnlineBPH con el intérprete aislado. No importa packing_services."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import capture_online_bph  # noqa: E402
from online_bph_case import run_online_bph_episode  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    process_started = time.perf_counter()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    snapshot = job["snapshot"]
    container_row = snapshot["containers"][0]
    container = (
        float(container_row["length_mm"]),
        float(container_row["width_mm"]),
        float(container_row["height_mm"]),
    )
    items = [
        (float(item["length_mm"]), float(item["width_mm"]), float(item["height_mm"]))
        for item in snapshot["items"]
    ]
    ready = time.perf_counter()
    episode = run_online_bph_episode(repo=job["external_repo"], container_lwh=container, items_lwh=items)
    capture = capture_online_bph(
        snapshot,
        episode,
        order_id=job["order_id"],
        dataset=job["dataset"],
        dataset_sha256=job["dataset_sha256"],
    )
    finished = time.perf_counter()
    destination = args.result
    payload = {
        "status": "ok",
        "error": None,
        "attempts": 1,
        "timeout_seconds": 300,
        "capture": capture,
        "episode": {
            "n_input": episode["n_input"],
            "n_placed": len(episode["placed"]),
            "sentinel_lwh_mm": episode["sentinel_lwh_mm"],
            "orientation": episode["orientation"],
            "setting": episode["setting"],
            "reset_calls": episode["reset_calls"],
            "generator": episode["generator"],
            "packing_loop_seconds": episode["packing_loop_seconds"],
            "import_seconds": episode["import_seconds"],
        },
        "diagnostics": {
            "n_packed": len(episode["placed"]),
            "generator": episode["generator"],
            "orientation": episode["orientation"],
            "setting": episode["setting"],
            "reset_calls": episode["reset_calls"],
            "physical_stability_verified": None,
        },
        "timings": {
            "startup_seconds": ready - process_started,
            "packing_loop_seconds": episode["packing_loop_seconds"],
            "import_seconds": episode["import_seconds"],
            "worker_after_loop_seconds": finished - ready - episode["packing_loop_seconds"],
        },
        "returncode": 0,
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        destination = Path(sys.argv[sys.argv.index("--result") + 1])
        destination.write_text(
            json.dumps(
                {
                    "status": "crash",
                    "error": f"{type(exc).__name__}: {exc}",
                    "worker_failure": "crash",
                    "attempts": 1,
                    "capture": None,
                    "diagnostics": None,
                    "returncode": 0,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        raise SystemExit(0)
