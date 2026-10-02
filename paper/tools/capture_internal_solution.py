#!/usr/bin/env python3
"""Una inferencia diagnóstica. Guarda la geometría interna, no el plan 0/1.

La exportación yaw es opcional y va a otro archivo. No es evaluación ni comparación con PCT.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def _prepare_imports() -> None:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    sys.path.insert(0, str(REPO_ROOT / "online_policy_ml" / "src_ml"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def _git() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    status = run("status", "--short")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "dirty": bool(status),
        "status_short_count": len([line for line in status.splitlines() if line.strip()]),
    }


def _dump(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model


def capture(
    orders_path: Path,
    order_id: str,
    checkpoint_path: Path,
    *,
    legacy_export: Path | None = None,
) -> dict[str, Any]:
    _prepare_imports()
    from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
    from packing_services.online.params import support_threshold, wants_consolidate
    from problems import order_to_problem
    from splits import load_orders

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    orders = load_orders(orders_path)
    if order_id not in orders:
        raise ValueError(f"{order_id} no está en {orders_path}")
    problem = order_to_problem(
        orders,
        order_id,
        lookahead_p=1,
        select_s=1,
        algorithm_name="drl_policy_3d_bpp",
        model_path=str(checkpoint_path),
    )
    params = dict(problem.algorithm.parameters)
    constraints = problem.constraints
    containers = [
        {
            "id": container.id,
            "length_mm": container.length,
            "width_mm": container.width,
            "height_mm": container.height,
            "max_weight_kg": container.max_weight,
        }
        for container in problem.containers
    ]
    input_items = [
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
    recipe = {
        "source": "online_policy_ml/notebooks/09_homologar_pct.ipynb llama order_to_problem y DRLPolicy3DBPP().run",
        "orders_path": str(orders_path),
        "orders_sha256": _sha256(orders_path),
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "lookahead_p": params.get("lookahead_p"),
        "select_s": params.get("select_s"),
        "selection": params.get("selection"),
        "sort_strategy": params.get("sort_strategy"),
        "packing_mode": "online",
        "problem_type": str(problem.problem_type.value if hasattr(problem.problem_type, "value") else problem.problem_type),
        "algorithm": problem.algorithm.name,
        "constraints": _dump(constraints),
        "min_support_ratio_effective": support_threshold(params, constraints.basic_stability),
        "consolidate_effective": wants_consolidate(params, len(problem.containers)),
        "n_containers": len(problem.containers),
        "item_does_not_fit": (
            "run_online_loop descarta el más antiguo del buffer si nadie cabe "
            "y continúa. Motivo: 'No hay colocación legal con el presupuesto de información actual'."
        ),
        "physical_stability": "no evaluada; basic_stability efectivo false y no hay simulación rígida",
    }
    solution = DRLPolicy3DBPP().run(problem)
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
    if legacy_export is not None:
        from bedbpp_eval import packing_plan_actions

        plan = {order_id: packing_plan_actions(problem, solution)}
        legacy_export.parent.mkdir(parents=True, exist_ok=True)
        legacy_export.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    elapsed = time.perf_counter() - t0
    return {
        "units": {"length": "mm", "volume": "mm3", "weight": "kg", "time": "s"},
        "captured_at_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": elapsed,
        "git": _git(),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "torch": _package("torch"),
            "numpy": _package("numpy"),
            "pydantic": _package("pydantic"),
            "torch_map_location": "cpu, vía loader existente; esta captura no pide CUDA",
        },
        "order_id": order_id,
        "recipe": recipe,
        "containers": containers,
        "input_items": input_items,
        "placements": placements,
        "unpacked": unpacked,
        "metrics": _dump(solution.metrics),
        "validation_report": _dump(solution.validation_report),
        "solution_status": str(solution.status.value if hasattr(solution.status, "value") else solution.status),
        "physical_stability_verified": None,
        "list_index_note": (
            "packed_list_index es la posición en solution.packed_items. "
            "El código no acredita que sea un timestamp de decisión."
        ),
        "legacy_export_path": None if legacy_export is None else str(legacy_export),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Captura la geometría interna de una inferencia.")
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--legacy-export", type=Path, default=None)
    args = parser.parse_args(argv)
    orders = args.orders.expanduser().resolve()
    checkpoint = args.checkpoint.expanduser().resolve()
    output = args.output.expanduser().resolve()
    legacy = None if args.legacy_export is None else args.legacy_export.expanduser().resolve()
    document = capture(orders, args.order_id, checkpoint, legacy_export=legacy)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "n_input": len(document["input_items"]),
                "n_packed": len(document["placements"]),
                "n_unpacked": len(document["unpacked"]),
                "duration_seconds": document["duration_seconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
