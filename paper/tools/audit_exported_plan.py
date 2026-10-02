#!/usr/bin/env python3
"""Auditoría geométrica independiente de un packing plan exportado con orientación 0/1.

No importa el evaluador del repositorio. Interpreta:
  orientation 0 = length, width, height originales
  orientation 1 = intercambio length/width, height igual

Cualquier otra orientación se rechaza. No reconstruye permutaciones internas.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

TOLERANCE_MM = 1e-6


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"campo no numérico: {field}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"campo no finito: {field}")
    return number


def _orientation_flag(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise ValueError(f"orientación no representable por 0/1: {value!r}")
    return value


def oriented_lwh(length: float, width: float, height: float, orientation: int) -> tuple[float, float, float]:
    if orientation == 0:
        return length, width, height
    if orientation == 1:
        return width, length, height
    raise ValueError(f"orientación no representable por 0/1: {orientation!r}")


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


def _parse_action(action: Any, index: int) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValueError("la acción no es un objeto")
    item = action.get("item")
    if not isinstance(item, dict):
        raise ValueError("falta item")
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("id de ítem ausente o vacío")
    length = _finite_number(item.get("length"), "item.length")
    width = _finite_number(item.get("width"), "item.width")
    height = _finite_number(item.get("height"), "item.height")
    if length <= 0 or width <= 0 or height <= 0:
        raise ValueError("dimensiones no positivas")
    orientation = _orientation_flag(action.get("orientation"))
    flb = action.get("flb_coordinates")
    if not isinstance(flb, (list, tuple)) or len(flb) != 3:
        raise ValueError("flb_coordinates debe tener 3 números")
    x = _finite_number(flb[0], "flb.x")
    y = _finite_number(flb[1], "flb.y")
    z = _finite_number(flb[2], "flb.z")
    ol, ow, oh = oriented_lwh(length, width, height, orientation)
    return {
        "index": index,
        "id": item_id,
        "orientation": orientation,
        "original_lwh_mm": [length, width, height],
        "oriented_lwh_mm": [ol, ow, oh],
        "flb_mm": [x, y, z],
        "max_corner_mm": [x + ol, y + ow, z + oh],
        "volume_mm3": ol * ow * oh,
    }


def _bounds(box: dict[str, Any], bin_mm: tuple[float, float, float], eps: float) -> dict[str, Any]:
    x, y, z = box["flb_mm"]
    xe, ye, ze = box["max_corner_mm"]
    length, width, height = bin_mm
    lower_negative = {"x": x < -eps, "y": y < -eps, "z": z < -eps}
    upper_excess = {
        "x": xe > length + eps,
        "y": ye > width + eps,
        "z": ze > height + eps,
    }
    outside = any(lower_negative.values()) or any(upper_excess.values())
    return {
        "lower_negative": lower_negative,
        "upper_excess": upper_excess,
        "outside_bin": outside,
    }


def _pair(a: dict[str, Any], b: dict[str, Any], eps: float) -> dict[str, Any]:
    ax, ay, az = a["flb_mm"]
    bx, by, bz = b["flb_mm"]
    axe, aye, aze = a["max_corner_mm"]
    bxe, bye, bze = b["max_corner_mm"]
    ix = _interval_overlap(ax, axe, bx, bxe)
    iy = _interval_overlap(ay, aye, by, bye)
    iz = _interval_overlap(az, aze, bz, bze)
    overlap = ix > eps and iy > eps and iz > eps
    return {
        "i": a["index"],
        "j": b["index"],
        "id_i": a["id"],
        "id_j": b["id"],
        "intersection_mm": {"x": ix, "y": iy, "z": iz},
        "overlap": overlap,
    }


def _reported_for_order(report: dict[str, Any], order_id: str) -> dict[str, Any] | None:
    nuestro = report.get("nuestro")
    if isinstance(nuestro, list):
        for row in nuestro:
            if isinstance(row, dict) and str(row.get("order_id")) == order_id:
                return row
        return None
    if isinstance(nuestro, dict):
        return nuestro
    return None


def _copy_reported(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    keys = (
        "order_id",
        "method",
        "uti",
        "num",
        "N",
        "nu",
        "hn_m",
        "feasible",
        "n_fuera_bin",
        "packed_volume_in",
        "bin_volume",
        "bin_mm",
        "eta_util",
        "items_packed",
        "allow_rotation",
    )
    return {key: row.get(key) for key in keys if key in row}


def audit_actions(
    actions: list[Any],
    bin_mm: tuple[float, float, float],
    *,
    reported: dict[str, Any] | None = None,
    order_id: str | None = None,
) -> dict[str, Any]:
    """Reconstruye AABB bajo el esquema 0/1 y no modifica las acciones."""

    if len(bin_mm) != 3 or any(axis <= 0 for axis in bin_mm):
        raise ValueError("bin-mm debe ser L W H positivos")
    parse_errors: list[dict[str, Any]] = []
    boxes: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        try:
            box = _parse_action(action, index)
        except ValueError as exc:
            parse_errors.append({"index": index, "error": str(exc)})
            continue
        box.update(_bounds(box, bin_mm, TOLERANCE_MM))
        boxes.append(box)

    id_counts: dict[str, int] = {}
    for box in boxes:
        id_counts[box["id"]] = id_counts.get(box["id"], 0) + 1
    duplicate_ids = sorted(item_id for item_id, count in id_counts.items() if count > 1)

    pairs = [_pair(boxes[i], boxes[j], TOLERANCE_MM) for i in range(len(boxes)) for j in range(i + 1, len(boxes))]
    overlap_pairs = [pair for pair in pairs if pair["overlap"]]
    outside_boxes = [box for box in boxes if box["outside_bin"]]
    max_height = max((box["max_corner_mm"][2] for box in boxes), default=None)
    total_volume = sum(box["volume_mm3"] for box in boxes)

    geometry_valid = (
        len(actions) > 0
        and not parse_errors
        and not duplicate_ids
        and not outside_boxes
        and not overlap_pairs
    )
    reported_copy = _copy_reported(reported)
    reported_hn_mm = None
    if reported_copy and isinstance(reported_copy.get("hn_m"), (int, float)) and not isinstance(reported_copy.get("hn_m"), bool):
        reported_hn_mm = float(reported_copy["hn_m"]) * 1000.0
    hn_diff = None
    if max_height is not None and reported_hn_mm is not None:
        hn_diff = max_height - reported_hn_mm

    return {
        "order_id": order_id,
        "tolerance_mm": TOLERANCE_MM,
        "orientation_scheme": {
            "0": "length, width, height originales",
            "1": "intercambia length y width; height se conserva",
        },
        "bin_mm": list(bin_mm),
        "n_actions": len(actions),
        "n_boxes_parsed": len(boxes),
        "parse_errors": parse_errors,
        "duplicate_ids": duplicate_ids,
        "max_height_mm": max_height,
        "total_volume_mm3": total_volume,
        "n_boxes_outside_bin": len(outside_boxes),
        "n_overlap_pairs": len(overlap_pairs),
        "boxes": boxes,
        "pairs": pairs,
        "exported_plan_geometry_valid": geometry_valid,
        "internal_solution_valid": None,
        "internal_reported": reported_copy,
        "contrast": {
            "reconstructed_max_height_mm": max_height,
            "reported_hn_mm": reported_hn_mm,
            "height_minus_reported_hn_mm": hn_diff,
            "reconstructed_total_volume_mm3": total_volume,
            "reported_packed_volume_in": None if reported_copy is None else reported_copy.get("packed_volume_in"),
            "reported_n_fuera_bin": None if reported_copy is None else reported_copy.get("n_fuera_bin"),
            "reported_feasible": None if reported_copy is None else reported_copy.get("feasible"),
            "note": (
                "El contraste numérico no declara falsas las métricas internas. "
                "internal_solution_valid queda null: no hay dimensiones orientadas internas."
            ),
        },
    }


def load_report_plan(report_path: Path, order_id: str) -> tuple[list[Any], dict[str, Any] | None, dict[str, Any]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    plan = report.get("packing_plan_nuestro")
    observed = {
        "packing_plan_nuestro_type": type(plan).__name__,
        "nuestro_type": type(report.get("nuestro")).__name__,
    }
    if not isinstance(plan, dict) or order_id not in plan:
        raise ValueError(
            f"no está packing_plan_nuestro[{order_id!r}]; "
            f"tipo observado={observed['packing_plan_nuestro_type']}"
        )
    actions = plan[order_id]
    if not isinstance(actions, list):
        raise ValueError("packing_plan_nuestro[order] no es una lista de acciones")
    observed["n_actions"] = len(actions)
    if actions and isinstance(actions[0], dict):
        observed["action_keys"] = sorted(actions[0].keys())
    return actions, _reported_for_order(report, order_id), observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita la geometría 0/1 de un packing plan exportado.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bin-mm", required=True, nargs=3, type=float, metavar=("L", "W", "H"))
    args = parser.parse_args(argv)
    report_path = args.report.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    try:
        actions, reported, observed = load_report_plan(report_path, args.order_id)
        result = audit_actions(
            actions,
            (args.bin_mm[0], args.bin_mm[1], args.bin_mm[2]),
            reported=reported,
            order_id=args.order_id,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result["report_path"] = str(report_path)
    result["observed_structure"] = observed
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "n_boxes_parsed": result["n_boxes_parsed"],
                "max_height_mm": result["max_height_mm"],
                "n_boxes_outside_bin": result["n_boxes_outside_bin"],
                "n_overlap_pairs": result["n_overlap_pairs"],
                "exported_plan_geometry_valid": result["exported_plan_geometry_valid"],
                "internal_solution_valid": result["internal_solution_valid"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
