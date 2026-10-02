#!/usr/bin/env python3
"""Adaptador yaw 0/1 estricto. Conserva la geometría o rechaza el plan entero.

orientation 0 es exactamente (L, W, H). orientation 1 es exactamente (W, L, H).
Si ambas coinciden, se elige 0. No se intercambian dimensiones en silencio,
no se recolocan cajas y no se escribe un plan parcial.

Esta versión rechaza capturas con más de un contenedor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _load_internal():
    path = Path(__file__).resolve().parent / "audit_internal_solution.py"
    spec = importlib.util.spec_from_file_location("audit_internal_solution", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_INTERNAL = _load_internal()


def yaw_orientation(original: list[float], oriented: list[float]) -> int | None:
    """0 si coincide (L,W,H); 1 si coincide solo (W,L,H); None si ninguna."""

    length, width, height = original
    same = _INTERNAL._axis_match
    if same(oriented, [length, width, height]):
        return 0
    if same(oriented, [width, length, height]):
        return 1
    return None


def assess_yaw_export(document: dict[str, Any]) -> dict[str, Any]:
    """Informe de compatibilidad. `plan` es None si la exportación se rechaza."""

    audit = _INTERNAL.audit_document(document)
    placements = document.get("placements") if isinstance(document, dict) and isinstance(document.get("placements"), list) else []
    containers = document.get("containers") if isinstance(document, dict) and isinstance(document.get("containers"), list) else []
    incompatible: list[str] = []
    flags: list[dict[str, Any]] = []
    for placement in placements:
        if not isinstance(placement, dict):
            continue
        original = _INTERNAL._positive_triple(placement.get("original_lwh_mm"))
        oriented = _INTERNAL._positive_triple(placement.get("oriented_lwh_mm"))
        item_id = placement.get("item_id")
        if original is None or oriented is None:
            incompatible.append(str(item_id))
            continue
        flag = yaw_orientation(original, oriented)
        flags.append({"item_id": item_id, "orientation": flag})
        if flag is None:
            incompatible.append(str(item_id))
    geometry_valid = bool(audit["internal_geometry_valid"])
    yaw_representable = bool(placements) and not incompatible and len(flags) == len(placements)
    multi = len(containers) > 1
    exportable = geometry_valid and yaw_representable and not multi
    plan = None
    if exportable:
        order_id = str(document.get("order_id"))
        actions = []
        for placement, chosen in zip(placements, flags):
            length, width, height = (float(value) for value in placement["original_lwh_mm"])
            actions.append(
                {
                    "item": {
                        "id": placement["item_id"],
                        "length": length,
                        "width": width,
                        "height": height,
                        "weight": placement.get("weight_kg"),
                    },
                    "orientation": chosen["orientation"],
                    "flb_coordinates": [float(value) for value in placement["flb_mm"]],
                }
            )
        plan = {order_id: actions}
    reasons = []
    if not geometry_valid:
        reasons.append("geometría interna no válida")
    if not yaw_representable:
        reasons.append("hay orientaciones no representables como yaw 0/1")
    if multi:
        reasons.append("esta versión rechaza capturas con más de un contenedor")
    return {
        "internal_geometry_valid": geometry_valid,
        "yaw_representable": yaw_representable,
        "yaw_exportable": exportable,
        "n_incompatible_orientations": len(incompatible),
        "incompatible_item_ids": incompatible,
        "multi_container_rejected": multi,
        "multi_container_limit": "Esta versión no exporta capturas con más de un contenedor.",
        "physical_stability_verified": None,
        "rejection_reasons": reasons,
        "plan": plan,
        "note": (
            "Geometría válida y representabilidad yaw son distintas. "
            "El adaptador no fabrica un plan intercambiando dimensiones, "
            "no verifica estabilidad física y no afirma superioridad frente a PCT."
        ),
    }


def emit(document: dict[str, Any], *, report_path: Path | None = None, plan_path: Path | None = None) -> int:
    """Escribe el informe. El plan solo se crea si la conversión es aceptada.

    Si informe y plan resuelven al mismo archivo, no escribe nada y devuelve 2.
    """

    if (
        report_path is not None
        and plan_path is not None
        and report_path.expanduser().resolve() == plan_path.expanduser().resolve()
    ):
        return 2
    report = assess_yaw_export(document)
    public = {key: value for key, value in report.items() if key != "plan"}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if plan_path is not None:
        if not report["yaw_exportable"] or report["plan"] is None:
            return 1
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(report["plan"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Informe de compatibilidad yaw 0/1, o plan estricto si todas las "
            "orientaciones coinciden exactamente con (L,W,H) o (W,L,H). "
            "Si la conversión falla, no crea ni sobrescribe el plan."
        )
    )
    parser.add_argument("--solution", required=True, type=Path, help="Captura interna con el esquema 01C.")
    parser.add_argument("--report", type=Path, default=None, help="Informe de compatibilidad. No contiene un plan fabricado.")
    parser.add_argument("--plan", type=Path, default=None, help="Plan legacy. Solo se escribe si la exportación es aceptada.")
    args = parser.parse_args(argv)
    if args.report is None and args.plan is None:
        parser.error("indica --report, --plan o ambos")
    document = json.loads(args.solution.expanduser().resolve().read_text(encoding="utf-8"))
    code = emit(
        document,
        report_path=None if args.report is None else args.report.expanduser().resolve(),
        plan_path=None if args.plan is None else args.plan.expanduser().resolve(),
    )
    if code == 2:
        print("report y plan resuelven al mismo archivo; no se escribió nada", file=sys.stderr)
        return 2
    if args.report is not None and args.report.expanduser().exists():
        summary = json.loads(args.report.expanduser().resolve().read_text(encoding="utf-8"))
        print(
            json.dumps(
                {
                    "yaw_exportable": summary.get("yaw_exportable"),
                    "internal_geometry_valid": summary.get("internal_geometry_valid"),
                    "n_incompatible_orientations": summary.get("n_incompatible_orientations"),
                    "exit_code": code,
                },
                ensure_ascii=False,
            )
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
