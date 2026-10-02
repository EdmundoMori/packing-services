"""Conversión y captura compartidas. No ejecuta ninguna política."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pilot_common import ACTOR_ALGORITHM, HEURISTIC_ALGORITHM, REPO_ROOT


def prepare_imports() -> None:
    entries = (
        str(REPO_ROOT / "online_policy_ml" / "src_ml"),
        str(REPO_ROOT / "src"),
    )
    for entry in reversed(entries):
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)


def build_problem(
    orders: dict[str, Any],
    order_id: str,
    method: str,
    checkpoint: Path,
    *,
    lookahead_p: int,
    select_s: int,
) -> Any:
    prepare_imports()
    from problems import order_to_problem

    if method == "actor":
        return order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name=ACTOR_ALGORITHM,
            model_path=str(checkpoint),
        )
    if method == "heuristic":
        return order_to_problem(
            orders,
            order_id,
            lookahead_p=lookahead_p,
            select_s=select_s,
            algorithm_name=HEURISTIC_ALGORITHM,
            model_path=None,
        )
    raise ValueError(f"método desconocido: {method}")


def _dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def problem_snapshot(problem: Any) -> dict[str, Any]:
    prepare_imports()
    from packing_services.online.params import support_threshold, wants_consolidate

    params = dict(problem.algorithm.parameters)
    constraints = _dump(problem.constraints)
    containers = [
        {
            "id": container.id,
            "length_mm": container.length,
            "width_mm": container.width,
            "height_mm": container.height,
            "max_weight_kg": container.max_weight,
            "volume_mm3": container.length * container.width * container.height,
        }
        for container in problem.containers
    ]
    items = [
        {
            "arrival_index": item.arrival_index,
            "list_index": index,
            "item_id": item.id,
            "length_mm": item.length,
            "width_mm": item.width,
            "height_mm": item.height,
            "weight_kg": item.weight,
            "allowed_orientations": item.allowed_orientations,
        }
        for index, item in enumerate(problem.items)
    ]
    return {
        "containers": containers,
        "items": items,
        "constraints": constraints,
        "lookahead_p": params.get("lookahead_p"),
        "select_s": params.get("select_s"),
        "selection": params.get("selection"),
        "sort_strategy": params.get("sort_strategy"),
        "problem_type": str(problem.problem_type.value if hasattr(problem.problem_type, "value") else problem.problem_type),
        "n_containers": len(problem.containers),
        "min_support_ratio_effective": support_threshold(params, problem.constraints.basic_stability),
        "consolidate_effective": wants_consolidate(params, len(problem.containers)),
        "algorithm": problem.algorithm.name,
        "model_path": params.get("model_path"),
        "request_id": problem.request_id,
    }


def shared_config(snapshot: dict[str, Any]) -> dict[str, Any]:
    data = dict(snapshot)
    data.pop("algorithm", None)
    data.pop("model_path", None)
    return data


def capture_document(
    problem: Any,
    solution: Any,
    *,
    method: str,
    order_id: str,
    orders_path: Path,
    orders_sha256: str,
    checkpoint_path: Path,
) -> dict[str, Any]:
    """Geometría interna de una solución ya obtenida. No llama al motor."""

    prepare_imports()
    from packing_services.online.params import support_threshold, wants_consolidate

    params = dict(problem.algorithm.parameters)
    constraints = problem.constraints
    by_id = {item.id: item for item in problem.items}
    placements = []
    for index, packed in enumerate(solution.packed_items):
        original = by_id[packed.item_id]
        placements.append(
            {
                "packed_list_index": index,
                "item_id": packed.item_id,
                "container_id": packed.container_id,
                "flb_mm": [packed.position.x, packed.position.y, packed.position.z],
                "original_lwh_mm": [original.length, original.width, original.height],
                "oriented_lwh_mm": [
                    packed.orientation.length,
                    packed.orientation.width,
                    packed.orientation.height,
                ],
                "weight_kg": packed.weight,
            }
        )
    unpacked = [
        {"item_id": item.item_id, "reason": item.reason}
        for item in solution.unpacked_items
    ]
    snapshot = problem_snapshot(problem)
    recipe = {
        "method": method,
        "orders_path": str(orders_path),
        "orders_sha256": orders_sha256,
        "checkpoint_path": str(checkpoint_path) if method == "actor" else None,
        "lookahead_p": snapshot["lookahead_p"],
        "select_s": snapshot["select_s"],
        "selection": snapshot["selection"],
        "sort_strategy": snapshot["sort_strategy"],
        "packing_mode": "online",
        "problem_type": snapshot["problem_type"],
        "algorithm": snapshot["algorithm"],
        "constraints": _dump(constraints),
        "min_support_ratio_effective": support_threshold(params, constraints.basic_stability),
        "consolidate_effective": wants_consolidate(params, len(problem.containers)),
        "n_containers": snapshot["n_containers"],
        "device": "cpu",
        "attempts": 1,
        "sampling": False,
        "actor_eval_mode": method == "actor",
        "decision": (
            "argmax de LearnedPlacementPolicy.decide; el loader existente llama model.eval()"
            if method == "actor"
            else "GreedyBestFitPolicy dentro de Online3DBPPHeuristic.run"
        ),
    }
    return {
        "units": {"length": "mm", "volume": "mm3", "weight": "kg", "time": "s"},
        "order_id": order_id,
        "method": method,
        "recipe": recipe,
        "containers": snapshot["containers"],
        "input_items": snapshot["items"],
        "placements": placements,
        "unpacked": unpacked,
        "physical_stability_verified": None,
    }
