"""Medición sintética para un preflight futuro. No empaqueta pedidos reales."""

from __future__ import annotations

import tracemalloc
from typing import Any

from compact_study import build_compact_problem
from environment import RuleSelectionEnv
from model import synthetic_ppo_update_seconds


def _order(order_id: str, items: list[tuple[str, int, int, int]]) -> dict:
    sequence = {}
    for index, (name, length, width, height) in enumerate(items, start=1):
        sequence[str(index)] = {
            "sequence": index,
            "id": name,
            "length/mm": length,
            "width/mm": width,
            "height/mm": height,
            "weight/kg": 1,
        }
    return {order_id: {"properties": {"target": "euro-pallet"}, "item_sequence": sequence}}


def synthetic_orders() -> list[tuple[str, Any]]:
    specs = [
        ("synthetic-a", [("a", 200, 180, 120), ("b", 150, 140, 100), ("c", 80, 80, 80)]),
        ("synthetic-b", [("a", 300, 200, 100), ("b", 100, 100, 400)]),
        ("synthetic-c", [("a", 120, 120, 120), ("b", 90, 80, 70), ("c", 60, 50, 40), ("d", 40, 40, 40)]),
    ]
    return [(order_id, build_compact_problem(_order(order_id, items), order_id)) for order_id, items in specs]


def run_greedy_episode(problem: Any) -> dict[str, Any]:
    import time

    env = RuleSelectionEnv()
    started = time.perf_counter()
    _observation, info = env.reset(problem)
    decisions = 0
    pair_hits = 0
    while not info["terminated"]:
        _observation, _reward, _terminated, info = env.step(0)
        if info["placed"]:
            decisions += 1
            if info["decision_redundancy"]["any_pair"] is True:
                pair_hits += 1
        if info["terminated"]:
            break
    elapsed = time.perf_counter() - started
    utilization = env.geometric_utilization()
    env.close()
    return {
        "seconds": elapsed,
        "decisions": decisions,
        "pair_redundancy_decisions": pair_hits,
        "utilization": utilization,
    }


def measure_synthetic() -> dict[str, Any]:
    tracemalloc.start()
    episodes = []
    for order_id, problem in synthetic_orders():
        row = run_greedy_episode(problem)
        row["order_id"] = order_id
        episodes.append(row)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    update_seconds = synthetic_ppo_update_seconds()
    decisions = [row["decisions"] for row in episodes]
    return {
        "mode": "synthetic",
        "real_orders_packed": False,
        "training_executed": False,
        "episodes": episodes,
        "seconds_per_episode": [row["seconds"] for row in episodes],
        "decisions_per_episode": decisions,
        "pair_redundancy_rate": (
            sum(row["pair_redundancy_decisions"] for row in episodes) / sum(decisions)
            if sum(decisions)
            else None
        ),
        "tracemalloc_peak_bytes": peak,
        "ppo_update_seconds": update_seconds,
        "ppo_update_rows": 32,
        "ppo_update_epochs": 4,
        "torch_threads": 1,
    }
