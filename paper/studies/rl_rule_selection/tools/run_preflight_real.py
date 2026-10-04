"""Orquesta el preflight real. Rechaza cualquier pedido fuera de los cuatro."""

from __future__ import annotations

import argparse
import json
import os
import queue
import resource
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
PAPER_TOOLS = STUDY.parents[1] / "tools"
if str(PAPER_TOOLS) not in sys.path:
    sys.path.insert(0, str(PAPER_TOOLS))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from pilot_common import sha256_file  # noqa: E402
from preflight_real import (  # noqa: E402
    GLOBAL_TIMEOUT_SECONDS,
    MAX_WORKERS,
    _rss_kb,
    allowed_preflight_orders,
    planned_cases,
    worker_main,
)
from sample_audit import DATASET, EXPECTED_DATASET_SHA256  # noqa: E402

STUDY = HERE.parent


def run(manifest_path: Path, output_dir: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = allowed_preflight_orders(manifest)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit("bloqueo: el directorio de preflight real ya tiene contenido")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_sha = sha256_file(DATASET)
    if dataset_sha != EXPECTED_DATASET_SHA256:
        raise SystemExit("bloqueo: el SHA256 del dataset no coincide")
    cases = planned_cases(rows)
    for case in cases:
        case["output_dir"] = str(output_dir / "cases" / case["order_id"] / case["method"])
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(PAPER_TOOLS), os.environ.get("PYTHONPATH", "")]
    )
    import multiprocessing

    context = multiprocessing.get_context("spawn")
    task_queue = context.Queue()
    result_queue = context.Queue()
    deadline = time.time() + GLOBAL_TIMEOUT_SECONDS
    for case in cases:
        task_queue.put(case)
    for _worker in range(MAX_WORKERS):
        task_queue.put(None)
    workers = [
        context.Process(
            target=worker_main,
            args=(task_queue, result_queue, str(DATASET), dataset_sha, deadline),
        )
        for _worker in range(MAX_WORKERS)
    ]
    samples: list[int] = []
    stop = threading.Event()

    def sample_rss() -> None:
        while not stop.is_set():
            joint = _rss_kb(os.getpid()) + sum(_rss_kb(process.pid) for process in workers if process.pid)
            samples.append(joint)
            stop.wait(0.25)

    wall_started = time.perf_counter()
    for process in workers:
        process.start()
    sampler = threading.Thread(target=sample_rss, daemon=True)
    sampler.start()
    startups = []
    case_results = []
    done_workers = 0
    while done_workers < MAX_WORKERS:
        if time.time() > deadline + 60:
            break
        try:
            message = result_queue.get(timeout=1.0)
        except queue.Empty:
            if all(not process.is_alive() for process in workers):
                break
            continue
        kind = message.get("kind")
        if kind == "startup":
            startups.append(message)
        elif kind == "worker_done":
            done_workers += 1
            startups.append(message)
        else:
            case_results.append(message)
    stop.set()
    sampler.join(timeout=2)
    grace = deadline + 30
    for process in workers:
        process.join(timeout=max(0.0, grace - time.time()))
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    received = {(row["order_id"], row["method"]) for row in case_results if "order_id" in row}
    for case in cases:
        key = (case["order_id"], case["method"])
        if key in received:
            continue
        pending = {
            **case,
            "kind": "case",
            "status": "pending_global_clock",
            "episode_complete": False,
            "u_geom_used_for_decisions": False,
            "physical_stability_verified": None,
        }
        case_results.append(pending)
        destination = Path(case["output_dir"])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "result.json").write_text(
            json.dumps(pending, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    import resource

    memory = {
        "sampled_joint_rss_max_kb": max(samples) if samples else None,
        "sampled_joint_rss_n": len(samples),
        "sampled_joint_rss_note": "Máximo de la suma de VmRSS del proceso padre y de los workers, muestreada. No es ru_maxrss.",
        "parent_ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "parent_ru_maxrss_note": "Pico del kernel para el proceso padre desde su inicio. No es la memoria conjunta simultánea.",
        "tracemalloc_note": "El pico de tracemalloc de cada caso mide asignaciones de Python. No mide toda la memoria de Torch ni del proceso.",
        "workers": startups,
        "max_workers": MAX_WORKERS,
        "torch_threads_per_worker": 1,
        "wall_seconds": time.perf_counter() - wall_started,
        "global_timeout_seconds": GLOBAL_TIMEOUT_SECONDS,
        "case_timeout_seconds": 300.0,
        "episodes_repeated": False,
    }
    (output_dir / "memory.json").write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "cases_index.json").write_text(
        json.dumps(case_results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {"memory": memory, "cases": case_results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
