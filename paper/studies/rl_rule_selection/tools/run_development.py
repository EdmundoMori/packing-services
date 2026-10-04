"""Orquesta los 360 episodios de desarrollo. No aplica la puerta."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import torch

from development_eval import CASE_TIMEOUT_SECONDS, deterministic_action, uniform_stream_seed
from rules import RULE_NAMES

MAX_WORKERS = 2


def _choose(task: dict[str, Any], actor) -> Any:
    if task["arm"] == "fixed":
        action = RULE_NAMES.index(task["label"])

        def fixed(_observation, _info) -> int:
            return action

        return fixed
    if task["arm"] == "uniform":
        generator = torch.Generator()
        generator.manual_seed(uniform_stream_seed(int(task["seed"]), task["order_id"]))

        def uniform(_observation, _info) -> int:
            return int(torch.randint(0, 3, (1,), generator=generator).item())

        return uniform
    if actor is None:
        raise RuntimeError("la evaluación PPO no tiene actor")

    def policy(observation, _info) -> int:
        row = torch.tensor(observation, dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            logits = actor(row)[0]
        return deterministic_action(logits)

    return policy


def execute_case(task: dict[str, Any], orders: dict[str, Any] | None = None) -> dict[str, Any]:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    torch.set_num_threads(1)
    import sys

    tools = Path(__file__).resolve().parent
    paper = tools.parents[2]
    for entry in (str(paper / "tools"), str(paper / "studies" / "counterfactual_ranking" / "tools"), str(tools)):
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)
    from audit_internal_solution import audit_document
    from campaign import recompute_u
    from compact_study import build_compact_problem
    from development_eval import contrast_input
    from environment import RuleSelectionEnv
    from pilot_problems import problem_snapshot
    from train_loop import load_actor

    started = time.perf_counter()
    deadline = min(time.time() + CASE_TIMEOUT_SECONDS, float(task["global_deadline"]))
    destination = Path(task["output_dir"])
    destination.mkdir(parents=True, exist_ok=True)
    if time.time() >= deadline:
        return _pending(task, "el caso no llegó a empezar dentro del reloj")
    if orders is None:
        orders = json.loads(Path(task["dataset"]).read_text(encoding="utf-8"))
    problem = build_compact_problem(orders, task["order_id"])
    snapshot = problem_snapshot(problem)
    actor = load_actor(Path(task["checkpoint"])) if task["arm"] == "ppo" else None
    choose = _choose(task, actor)
    env = RuleSelectionEnv()
    observation, info = env.reset(problem)
    frequencies = [0, 0, 0]
    status = "ok"
    error = None
    while not info.get("terminated"):
        if time.time() >= deadline:
            status = "timeout"
            break
        action = int(choose(observation, info))
        if action not in (0, 1, 2):
            raise RuntimeError("la acción de evaluación no es una de las tres reglas")
        frequencies[action] += 1
        observation, _reward, _terminated, info = env.step(action)
    capture = env.capture(
        order_id=task["order_id"],
        orders_path=Path(task["dataset"]),
        orders_sha256=task["dataset_sha"],
        description=f"Desarrollo {task['key']}. Política determinista en PPO y uniforme en la aleatoria.",
    )
    (destination / "capture.json").write_text(json.dumps(capture, ensure_ascii=False) + "\n", encoding="utf-8")
    audit = None
    raw = None
    contrast = None
    if status == "ok":
        try:
            audit = audit_document(capture)
            contrast = contrast_input(capture, snapshot, task["order_id"])
            raw = recompute_u(capture)
            (destination / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as exc:
            status = "evaluator_error"
            error = f"{type(exc).__name__}: {exc}"
    row = {
        "key": task["key"],
        "order_id": task["order_id"],
        "target": task["target"],
        "arm": task["arm"],
        "label": task["label"],
        "seed": task["seed"],
        "status": status,
        "error": error,
        "raw_u_geom": raw,
        "geometry_valid": None if audit is None else audit.get("internal_geometry_valid"),
        "contrast_matches": None if contrast is None else contrast.get("matches"),
        "contrast_errors": [] if contrast is None else contrast.get("errors"),
        "rule_counts": {name: frequencies[index] for index, name in enumerate(RULE_NAMES)},
        "n_decisions": sum(frequencies),
        "wall_seconds": time.perf_counter() - started,
        "physical_stability_verified": None,
        "sampled_ppo": False,
    }
    (destination / "result.json").write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def _pending(task: dict[str, Any], reason: str) -> dict[str, Any]:
    row = {
        "key": task["key"],
        "order_id": task["order_id"],
        "target": task["target"],
        "arm": task["arm"],
        "label": task["label"],
        "seed": task["seed"],
        "status": "pending",
        "error": reason,
        "raw_u_geom": None,
        "geometry_valid": None,
        "contrast_matches": None,
        "physical_stability_verified": None,
        "sampled_ppo": False,
    }
    destination = Path(task["output_dir"])
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "result.json").write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return row


def worker_main(task_queue: Any, result_queue: Any, dataset_path: str) -> None:
    orders = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    while True:
        task = task_queue.get()
        if task is None:
            result_queue.put({"kind": "worker_done"})
            return
        if time.time() >= float(task["global_deadline"]):
            result_queue.put({"kind": "case", **_pending(task, "reloj global vencido antes del caso")})
            continue
        try:
            result_queue.put({"kind": "case", **execute_case(task, orders)})
        except Exception as exc:
            row = {
                "kind": "case",
                "key": task.get("key"),
                "order_id": task.get("order_id"),
                "target": task.get("target"),
                "arm": task.get("arm"),
                "label": task.get("label"),
                "seed": task.get("seed"),
                "status": "evaluator_error",
                "error": f"{type(exc).__name__}: {exc}",
                "raw_u_geom": None,
                "physical_stability_verified": None,
            }
            destination = Path(task["output_dir"])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "result.json").write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            result_queue.put(row)


def _rss_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        return 0
    return 0


def run_development(study: Path, integrity: dict[str, Any]) -> dict[str, Any]:
    import multiprocessing
    import queue
    import resource

    from development_eval import (
        GLOBAL_TIMEOUT_SECONDS,
        classify_case,
        planned_cases,
        protocol_timeout_conflict,
    )
    from sample_audit import DATASET, EXPECTED_DATASET_SHA256

    if not integrity.get("passed"):
        raise SystemExit("bloqueo: la integridad no autoriza los episodios de desarrollo")
    protocol = json.loads((study / "protocol_frozen.json").read_text(encoding="utf-8"))
    conflict = protocol_timeout_conflict(protocol)
    if conflict:
        raise SystemExit(f"bloqueo: {conflict}")
    output = study / "development"
    if output.exists() and any(output.iterdir()):
        raise SystemExit("bloqueo: development ya tiene contenido")
    development = json.loads((study / "development_manifest.json").read_text(encoding="utf-8"))
    orders = [row for rows in development["selected"].values() for row in rows]
    cases = planned_cases(orders)
    output.mkdir(parents=True)
    (output / "orders_manifest.json").write_text(json.dumps(development, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for case in cases:
        case["output_dir"] = str(output / "cases" / case["order_id"] / f"{case['arm']}_{case['label']}")
        case["dataset"] = str(DATASET)
        case["dataset_sha"] = EXPECTED_DATASET_SHA256
        case["checkpoint"] = str(study / "training" / f"seed_{case['seed']}" / "checkpoint_final.pt") if case["arm"] == "ppo" else None
    (output / "planned_cases.json").write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paper = study.parents[1]
    study_tools = str(study / "tools")
    while study_tools in sys.path:
        sys.path.remove(study_tools)
    sys.path.insert(0, study_tools)
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [
            study_tools,
            str(paper / "tools"),
            str(paper / "studies" / "counterfactual_ranking" / "tools"),
            os.environ.get("PYTHONPATH", ""),
        ]
    )
    context = multiprocessing.get_context("spawn")
    task_queue = context.Queue()
    result_queue = context.Queue()
    deadline = time.time() + GLOBAL_TIMEOUT_SECONDS
    for case in cases:
        case["global_deadline"] = deadline
        task_queue.put(case)
    for _worker in range(MAX_WORKERS):
        task_queue.put(None)
    workers = [
        context.Process(target=worker_main, args=(task_queue, result_queue, str(DATASET)))
        for _worker in range(MAX_WORKERS)
    ]
    samples: list[int] = []
    wall_started = time.perf_counter()
    for process in workers:
        process.start()
    received: dict[str, dict[str, Any]] = {}
    done = 0
    while done < MAX_WORKERS:
        if time.time() > deadline + 60:
            break
        try:
            message = result_queue.get(timeout=1.0)
        except queue.Empty:
            if all(not process.is_alive() for process in workers):
                break
            samples.append(_rss_kb(os.getpid()) + sum(_rss_kb(process.pid) for process in workers if process.is_alive() and process.pid))
            continue
        if message.get("kind") == "worker_done":
            done += 1
        elif message.get("key"):
            received[message["key"]] = message
        samples.append(_rss_kb(os.getpid()) + sum(_rss_kb(process.pid) for process in workers if process.is_alive() and process.pid))
    for process in workers:
        process.join(timeout=max(0.0, deadline + 30 - time.time()))
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    task_queue.close()
    result_queue.close()
    task_queue.join_thread()
    result_queue.join_thread()
    rows = []
    for case in cases:
        row = received.get(case["key"])
        result_path = Path(case["output_dir"]) / "result.json"
        if row is None and result_path.is_file():
            row = json.loads(result_path.read_text(encoding="utf-8"))
        if row is None:
            row = _pending(case, "sin resultado al cerrar el reloj")
        classified = classify_case(
            status=str(row.get("status")),
            raw_u_geom=row.get("raw_u_geom"),
            geometry_valid=bool(row.get("geometry_valid")),
            contrast_matches=bool(row.get("contrast_matches")),
        )
        rows.append({**case, **row, **classified, "global_deadline": None})
    memory = {
        "sampled_joint_rss_max_kb": max(samples) if samples else None,
        "sampled_joint_rss_n": len(samples),
        "parent_ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "wall_seconds": time.perf_counter() - wall_started,
        "case_timeout_seconds": CASE_TIMEOUT_SECONDS,
        "global_timeout_seconds": GLOBAL_TIMEOUT_SECONDS,
        "max_workers": MAX_WORKERS,
        "torch_threads_per_worker": 1,
        "protocol_development_timeout": None,
        "protocol_timeout_conflict": None,
    }
    (output / "memory.json").write_text(json.dumps(memory, indent=2) + "\n", encoding="utf-8")
    (output / "cases_index.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"rows": rows, "memory": memory, "output": str(output)}
