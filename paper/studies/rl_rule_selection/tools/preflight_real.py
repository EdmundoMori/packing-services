"""Preflight real de cuatro pedidos. No entrena ni abre desarrollo o test."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import time
import tracemalloc
from pathlib import Path
from typing import Any

CASE_TIMEOUT_SECONDS = 300.0
GLOBAL_TIMEOUT_SECONDS = 900.0
MAX_WORKERS = 2
BASE_SEED = 101
METHODS = (
    "greedy_best_fit",
    "lowest_top",
    "least_height_increase",
    "initial_softmax_seed_101",
)
FIXED_ACTION = {
    "greedy_best_fit": 0,
    "lowest_top": 1,
    "least_height_increase": 2,
}


def trajectory_seed(order_id: str) -> int:
    digest = hashlib.sha256(f"rl-rules-preflight-v1|{BASE_SEED}|{order_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)


def allowed_preflight_orders(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("preflight_orders")
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError("el preflight admite exactamente cuatro pedidos del manifiesto")
    identifiers = [row["order_id"] for row in rows]
    if len(set(identifiers)) != 4:
        raise ValueError("los cuatro pedidos del preflight no son distintos")
    train_ids = {
        row["order_id"]
        for target_rows in manifest["selected"].values()
        for row in target_rows
    }
    if not set(identifiers) <= train_ids:
        raise ValueError("un pedido del preflight no pertenece a train")
    return rows


def planned_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases = []
    for row in sorted(rows, key=lambda item: (item["target"], item["order_id"], item["role"])):
        for method in METHODS:
            cases.append(
                {
                    "order_id": row["order_id"],
                    "target": row["target"],
                    "role": row["role"],
                    "n_items": row["n_items"],
                    "method": method,
                }
            )
    return cases


def _rss_kb(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError, ValueError):
        return 0
    return 0


def execute_case(task: dict[str, Any], orders: dict[str, Any], dataset: Path, dataset_sha: str, deadline: float) -> dict[str, Any]:
    import sys

    study_tools = Path(__file__).resolve().parent
    paper_root = study_tools.parents[2]
    paper_tools = paper_root / "tools"
    counterfactual = paper_root / "studies" / "counterfactual_ranking" / "tools"
    for entry in (str(paper_tools), str(counterfactual), str(study_tools)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    import torch

    torch.set_num_threads(1)
    from audit_internal_solution import audit_document
    from campaign import recompute_u
    from compact_study import build_compact_problem
    from environment import RuleSelectionEnv
    from model import GREEDY_LOGIT_BIAS, build_actor, greedy_softmax_probability

    started = time.perf_counter()
    cpu_start = resource.getrusage(resource.RUSAGE_SELF)
    tracemalloc.start()
    status = "ok"
    build_started = time.perf_counter()
    problem = build_compact_problem(orders, task["order_id"])
    problem_build_seconds = time.perf_counter() - build_started
    env = RuleSelectionEnv()
    observation, info = env.reset(problem)
    decision_seconds = 0.0
    decisions = 0
    pair_hits = 0
    all_three_hits = 0
    action_counts = {0: 0, 1: 0, 2: 0}
    first_logits = None
    generator = None
    actor = None
    if task["method"] == "initial_softmax_seed_101":
        actor = build_actor()
        generator = torch.Generator()
        generator.manual_seed(trajectory_seed(task["order_id"]))
    case_deadline = min(deadline, time.time() + CASE_TIMEOUT_SECONDS)
    loop_started = time.perf_counter()
    while not info["terminated"]:
        if time.time() >= case_deadline:
            status = "global_clock" if time.time() >= deadline else "case_timeout"
            break
        decide_started = time.perf_counter()
        if actor is None:
            action = FIXED_ACTION[task["method"]]
            logits = None
        else:
            row = torch.tensor(observation, dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                logits_tensor = actor(row)[0]
            action = int(torch.multinomial(torch.softmax(logits_tensor, dim=0), 1, generator=generator).item())
            logits = [float(value) for value in logits_tensor]
        decision_seconds += time.perf_counter() - decide_started
        observation, _reward, _terminated, info = env.step(action)
        if info["placed"]:
            decisions += 1
            action_counts[action] += 1
            redundancy = info["decision_redundancy"]
            if redundancy["any_pair"]:
                pair_hits += 1
            if redundancy["all_three"]:
                all_three_hits += 1
            if logits is not None and first_logits is None:
                first_logits = logits
    loop_wall_seconds = time.perf_counter() - loop_started
    capture_seconds = 0.0
    audit_seconds = 0.0
    audit = None
    utilization = None
    recomputed = None
    if status == "ok":
        capture_started = time.perf_counter()
        capture = env.capture(
            order_id=task["order_id"],
            orders_path=dataset,
            orders_sha256=dataset_sha,
            description="Preflight real de selección de reglas. Sin actualización de pesos.",
        )
        capture_seconds = time.perf_counter() - capture_started
        utilization = env.geometric_utilization()
        recomputed = recompute_u(capture)
        audit_started = time.perf_counter()
        audit = audit_document(capture)
        audit_seconds = time.perf_counter() - audit_started
        capture_path = Path(task["output_dir"]) / "capture.json"
        audit_path = Path(task["output_dir"]) / "audit.json"
        capture_path.write_text(json.dumps(capture, ensure_ascii=False) + "\n", encoding="utf-8")
        audit_path.write_text(json.dumps(audit, ensure_ascii=False) + "\n", encoding="utf-8")
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    cpu_end = resource.getrusage(resource.RUSAGE_SELF)
    env.close()
    return {
        **task,
        "status": status,
        "episode_complete": status == "ok",
        "optimizer_steps": 0,
        "policy": (
            "softmax del actor inicial con sesgo [1, 0, 0]; no es uniforme"
            if task["method"] == "initial_softmax_seed_101"
            else "regla fija"
        ),
        "greedy_softmax_probability": greedy_softmax_probability(GREEDY_LOGIT_BIAS),
        "trajectory_seed": trajectory_seed(task["order_id"]) if actor is not None else None,
        "problem_build_seconds": problem_build_seconds,
        "loop_wall_seconds": loop_wall_seconds,
        "decision_seconds": decision_seconds,
        "candidate_seconds": env.candidate_seconds,
        "candidate_generations": env.candidate_generations,
        "capture_seconds": capture_seconds,
        "audit_seconds": audit_seconds,
        "case_wall_seconds": time.perf_counter() - started,
        "cpu_user_seconds": cpu_end.ru_utime - cpu_start.ru_utime,
        "cpu_system_seconds": cpu_end.ru_stime - cpu_start.ru_stime,
        "ru_maxrss_kb": cpu_end.ru_maxrss,
        "tracemalloc_peak_bytes": peak,
        "decisions": decisions,
        "action_counts": {str(key): value for key, value in action_counts.items()},
        "first_logits": first_logits,
        "pair_redundancy_rate": pair_hits / decisions if decisions else None,
        "all_three_redundancy_rate": all_three_hits / decisions if decisions else None,
        "geometric_utilization": utilization,
        "recomputed_u_geom": recomputed,
        "u_geom_used_for_decisions": False,
        "internal_geometry_valid": None if audit is None else audit["internal_geometry_valid"],
        "n_overlap_pairs": None if audit is None else audit["n_overlap_pairs"],
        "n_boxes_outside_bin": None if audit is None else audit["n_boxes_outside_bin"],
        "physical_stability_verified": None,
        "torch_threads": 1,
    }


def worker_main(task_queue: Any, result_queue: Any, dataset: str, dataset_sha: str, deadline: float) -> None:
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    load_started = time.perf_counter()
    orders = json.loads(Path(dataset).read_text(encoding="utf-8"))
    result_queue.put(
        {
            "kind": "startup",
            "pid": os.getpid(),
            "dataset_load_seconds": time.perf_counter() - load_started,
            "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
    )
    while True:
        task = task_queue.get()
        if task is None:
            result_queue.put({"kind": "worker_done", "pid": os.getpid(), "ru_maxrss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
            break
        if time.time() >= deadline:
            payload = {
                **task,
                "kind": "case",
                "status": "pending_global_clock",
                "episode_complete": False,
                "u_geom_used_for_decisions": False,
                "physical_stability_verified": None,
            }
            destination = Path(task["output_dir"])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "result.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            result_queue.put(payload)
            continue
        output_dir = Path(task["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            payload = execute_case(task, orders, Path(dataset), dataset_sha, deadline)
        except Exception as exc:
            payload = {
                **task,
                "kind": "case",
                "status": "error",
                "episode_complete": False,
                "error": f"{type(exc).__name__}: {exc}",
                "u_geom_used_for_decisions": False,
                "physical_stability_verified": None,
            }
        else:
            payload["kind"] = "case"
        result_path = output_dir / "result.json"
        result_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result_queue.put(payload)
