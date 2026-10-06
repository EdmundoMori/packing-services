#!/usr/bin/env python3
"""Una inferencia diagnóstica. Guarda la geometría interna, no el plan 0/1.

La exportación yaw estricta es opcional (`--yaw-export`) y va a otro archivo.
Si se rechaza, la captura interna se conserva. El exportador legacy inseguro
(`--legacy-unsafe-yaw-export`) es solo forense y nunca es fallback automático.
No es evaluación ni comparación con PCT.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import subprocess
import sys
import time
import warnings
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


def _resolve_path(path: Path) -> Path:
    return path.expanduser().resolve()


def assert_distinct_write_paths(*paths: Path | None, label: str = "escritura") -> None:
    """Rechaza rutas de escritura que resuelven al mismo archivo antes de tocar disco."""

    seen: list[Path] = []
    for path in paths:
        if path is None:
            continue
        resolved = _resolve_path(path)
        for prior in seen:
            if prior == resolved:
                raise ValueError(
                    f"rutas de {label} coinciden tras resolve: {resolved}. "
                    "No se escribe nada; archivos existentes se conservan."
                )
        seen.append(resolved)


def write_strict_yaw_export(
    problem: Any,
    solution: Any,
    order_id: str,
    yaw_export: Path,
) -> dict[str, Any]:
    """Intenta exportación yaw estricta. No usa legacy como fallback.

    Si el plan se rechaza, no crea ni trunca el archivo destino.
    """

    from bedbpp_eval import YawExportError, packing_plan_actions

    target = _resolve_path(yaw_export)
    try:
        plan = {order_id: packing_plan_actions(problem, solution)}
    except YawExportError as exc:
        return {
            "ok": False,
            "path": str(target),
            "exporter": "packing_plan_actions",
            "contract": "yaw_0_1_v1_internal",
            "error": str(exc),
            "incompatible": list(exc.incompatible),
            "wrote_plan": False,
            "file_created_or_modified": False,
            "note": (
                "Rechazo yaw: la captura interna permanece válida por separado. "
                "No se escribió plan parcial ni vacío. "
                "No se invocó packing_plan_actions_legacy_unsafe_yaw."
            ),
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "exporter": "packing_plan_actions",
        "contract": "yaw_0_1_v1_internal",
        "n_actions": len(plan[order_id]),
        "wrote_plan": True,
        "file_created_or_modified": True,
    }


def write_legacy_unsafe_yaw_export(
    problem: Any,
    solution: Any,
    order_id: str,
    legacy_path: Path,
) -> dict[str, Any]:
    """Forense explícito. No es el exportador vigente ni fallback de rechazo."""

    from bedbpp_eval import packing_plan_actions_legacy_unsafe_yaw

    target = _resolve_path(legacy_path)
    plan = {
        "_legacy_unsafe_yaw_export": True,
        "_warning": (
            "Exportación pre-C03 INSEGURA: puede aplastar orientaciones que cambian altura. "
            "No usar como plan geométricamente fiel. No es fallback del exportador estricto. "
            "Solo con --legacy-unsafe-yaw-export (o alias deprecado --legacy-export)."
        ),
        order_id: packing_plan_actions_legacy_unsafe_yaw(problem, solution),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "path": str(target),
        "exporter": "packing_plan_actions_legacy_unsafe_yaw",
        "contract": "legacy_unsafe_pre_C03",
        "wrote_plan": True,
        "file_created_or_modified": True,
        "legacy_unsafe_yaw_export": True,
    }


def capture(
    orders_path: Path,
    order_id: str,
    checkpoint_path: Path,
    *,
    output_path: Path | None = None,
    yaw_export: Path | None = None,
    legacy_unsafe_yaw_export: Path | None = None,
    legacy_export: Path | None = None,
) -> dict[str, Any]:
    _prepare_imports()
    from packing_services.algorithms.drl_policy_3d_bpp import DRLPolicy3DBPP
    from packing_services.online.params import support_threshold, wants_consolidate
    from problems import order_to_problem
    from splits import load_orders

    if legacy_export is not None and legacy_unsafe_yaw_export is None:
        warnings.warn(
            "--legacy-export es alias de --legacy-unsafe-yaw-export (forense pre-C03 INSEGURO). "
            "Para yaw fiel use --yaw-export. Nunca es fallback automático del estricto.",
            DeprecationWarning,
            stacklevel=2,
        )
        legacy_unsafe_yaw_export = legacy_export

    # Validación de rutas antes de inferir/escribir: conserva archivos existentes.
    assert_distinct_write_paths(
        output_path,
        yaw_export,
        legacy_unsafe_yaw_export,
        label="captura/exportación",
    )

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

    yaw_export_report = None
    if yaw_export is not None:
        yaw_export_report = write_strict_yaw_export(problem, solution, order_id, yaw_export)

    legacy_unsafe_report = None
    if legacy_unsafe_yaw_export is not None:
        legacy_unsafe_report = write_legacy_unsafe_yaw_export(
            problem, solution, order_id, legacy_unsafe_yaw_export
        )

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
        "yaw_export": yaw_export_report,
        "legacy_unsafe_yaw_export": legacy_unsafe_report,
        "legacy_export_path": (
            None if legacy_unsafe_report is None else legacy_unsafe_report.get("path")
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Captura la geometría interna de una inferencia. "
            "Opcional: --yaw-export (estricto C03) o "
            "--legacy-unsafe-yaw-export (forense pre-C03, nunca fallback)."
        )
    )
    parser.add_argument("--orders", required=True, type=Path)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--yaw-export",
        type=Path,
        default=None,
        help="Plan yaw 0/1 estricto. Si se rechaza, no se escribe el plan y la captura sigue.",
    )
    parser.add_argument(
        "--legacy-unsafe-yaw-export",
        type=Path,
        default=None,
        help="Forense pre-C03 (aplastamiento). Nunca se usa como fallback del estricto.",
    )
    parser.add_argument(
        "--legacy-export",
        type=Path,
        default=None,
        help="Alias deprecado de --legacy-unsafe-yaw-export.",
    )
    args = parser.parse_args(argv)
    orders = args.orders.expanduser().resolve()
    checkpoint = args.checkpoint.expanduser().resolve()
    output = args.output.expanduser().resolve()
    yaw_path = None if args.yaw_export is None else args.yaw_export.expanduser().resolve()
    unsafe = (
        None
        if args.legacy_unsafe_yaw_export is None
        else args.legacy_unsafe_yaw_export.expanduser().resolve()
    )
    legacy_alias = None if args.legacy_export is None else args.legacy_export.expanduser().resolve()
    unsafe_effective = unsafe if unsafe is not None else legacy_alias

    # Antes de inferir o escribir: colisión de rutas → no tocar archivos existentes.
    try:
        assert_distinct_write_paths(
            output,
            yaw_path,
            unsafe_effective,
            label="captura/exportación",
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "wrote": False}, ensure_ascii=False), file=sys.stderr)
        return 2

    document = capture(
        orders,
        args.order_id,
        checkpoint,
        output_path=output,
        yaw_export=yaw_path,
        legacy_unsafe_yaw_export=unsafe,
        legacy_export=legacy_alias,
    )
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
                "yaw_export_ok": None
                if document.get("yaw_export") is None
                else document["yaw_export"].get("ok"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
