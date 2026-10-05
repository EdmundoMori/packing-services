#!/usr/bin/env python3
"""Trabajador sintético para pruebas del lanzador (no packing)."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

# tools on path when launched via absolute python -m or script path
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_io import atomic_write_json  # noqa: E402
from labeling_runctl import write_heartbeat, write_state  # noqa: E402


def main() -> int:
    run_dir = Path(os.environ["LABELING_RUN_DIR"])
    mode = os.environ.get("SYNTH_MODE", "ok")
    sleep_s = float(os.environ.get("SYNTH_SLEEP", "0.3"))
    stop = {"flag": False}

    def _handler(signum, _frame):  # noqa: ANN001
        stop["flag"] = True
        write_state(
            run_dir,
            {
                "run_id": os.environ.get("LABELING_RUN_ID"),
                "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
                "status": "interrupted_signal",
                "signal": int(signum),
                "pid": os.getpid(),
            },
        )

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)

    write_heartbeat(run_dir, {"pid": os.getpid(), "unix": time.time(), "phase": "start", "current_order_id": "synthetic"})
    t0 = time.time()
    while time.time() - t0 < sleep_s:
        if stop["flag"]:
            return 130
        write_heartbeat(
            run_dir,
            {
                "pid": os.getpid(),
                "unix": time.time(),
                "phase": "work",
                "current_order_id": "synthetic",
                "last_persisted_key": "synthetic:0",
            },
        )
        time.sleep(0.05)

    if mode == "fail":
        write_state(
            run_dir,
            {
                "run_id": os.environ.get("LABELING_RUN_ID"),
                "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
                "status": "exited_nonzero",
                "exit_code": 7,
                "pid": os.getpid(),
            },
        )
        return 7

    write_state(
        run_dir,
        {
            "run_id": os.environ.get("LABELING_RUN_ID"),
            "attempt_id": os.environ.get("LABELING_ATTEMPT_ID"),
            "status": "completed",
            "exit_code": 0,
            "pid": os.getpid(),
            "finished_unix": time.time(),
        },
    )
    atomic_write_json(run_dir / "synthetic_result.json", {"ok": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
