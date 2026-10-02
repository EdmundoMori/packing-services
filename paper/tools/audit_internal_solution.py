#!/usr/bin/env python3
"""Auditoría geométrica de la solución interna. No infiere yaw ni usa el validador de producción."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

TOLERANCE_MM = 1e-6


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    export_path = Path(__file__).resolve().parent / "audit_exported_plan.py"
    spec = importlib.util.spec_from_file_location("audit_exported_plan", export_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module._interval_overlap(a0, a1, b0, b1)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _near(a: float, b: float, eps: float = TOLERANCE_MM) -> bool:
    return abs(a - b) <= eps


def _is_permutation(original: list[float], oriented: list[float], eps: float = TOLERANCE_MM) -> bool:
    if len(original) != 3 or len(oriented) != 3:
        return False
    left = sorted(float(v) for v in original)
    right = sorted(float(v) for v in oriented)
    return all(_near(a, b, eps) for a, b in zip(left, right))


def _yaw_representable(original: list[float], oriented: list[float], eps: float = TOLERANCE_MM) -> bool:
    length, width, height = (float(v) for v in original)
    candidates = ((length, width, height), (width, length, height))
    got = tuple(float(v) for v in oriented)
    return any(all(_near(a, b, eps) for a, b in zip(candidate, got)) for candidate in candidates)


def _box_record(placement: dict[str, Any], container: dict[str, Any]) -> dict[str, Any]:
    x, y, z = (float(v) for v in placement["flb_mm"])
    length, width, height = (float(v) for v in placement["oriented_lwh_mm"])
    max_corner = [x + length, y + width, z + height]
    bin_lwh = (float(container["length_mm"]), float(container["width_mm"]), float(container["height_mm"]))
    lower_negative = {"x": x < -TOLERANCE_MM, "y": y < -TOLERANCE_MM, "z": z < -TOLERANCE_MM}
    upper_excess = {
        "x": max_corner[0] > bin_lwh[0] + TOLERANCE_MM,
        "y": max_corner[1] > bin_lwh[1] + TOLERANCE_MM,
        "z": max_corner[2] > bin_lwh[2] + TOLERANCE_MM,
    }
    return {
        "item_id": placement["item_id"],
        "container_id": placement["container_id"],
        "flb_mm": [x, y, z],
        "oriented_lwh_mm": [length, width, height],
        "max_corner_mm": max_corner,
        "volume_mm3": length * width * height,
        "lower_negative": lower_negative,
        "upper_excess": upper_excess,
        "outside_bin": any(lower_negative.values()) or any(upper_excess.values()),
    }


def audit_document(document: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    containers = {row["id"]: row for row in document.get("containers") or [] if isinstance(row, dict) and "id" in row}
    inputs = document.get("input_items") or []
    placements = document.get("placements") or []
    unpacked = document.get("unpacked") or []
    input_ids = [row.get("item_id") for row in inputs]
    if len(input_ids) != len(set(input_ids)) or any(not isinstance(item_id, str) or not item_id for item_id in input_ids):
        errors.append("ids de entrada duplicados o inválidos")
    input_by_id = {row["item_id"]: row for row in inputs if isinstance(row, dict) and isinstance(row.get("item_id"), str)}

    for container in containers.values():
        dims = (container.get("length_mm"), container.get("width_mm"), container.get("height_mm"))
        if not all(_finite(value) and float(value) > 0 for value in dims):
            errors.append(f"bin no finito o no positivo: {container.get('id')}")

    packed_ids = []
    boxes = []
    for placement in placements:
        item_id = placement.get("item_id")
        container_id = placement.get("container_id")
        packed_ids.append(item_id)
        if item_id not in input_by_id:
            errors.append(f"ítem colocado desconocido: {item_id}")
            continue
        if container_id not in containers:
            errors.append(f"contenedor desconocido: {container_id}")
            continue
        numbers = list(placement.get("flb_mm") or []) + list(placement.get("oriented_lwh_mm") or []) + list(placement.get("original_lwh_mm") or [])
        if len(numbers) != 9 or not all(_finite(value) for value in numbers):
            errors.append(f"valores no finitos en {item_id}")
            continue
        if any(float(value) <= 0 for value in placement["oriented_lwh_mm"]):
            errors.append(f"dimensión orientada no positiva: {item_id}")
            continue
        original = [float(v) for v in placement["original_lwh_mm"]]
        oriented = [float(v) for v in placement["oriented_lwh_mm"]]
        source = input_by_id[item_id]
        source_dims = [float(source["length_mm"]), float(source["width_mm"]), float(source["height_mm"])]
        if not _is_permutation(source_dims, original):
            errors.append(f"dimensiones originales no coinciden con la entrada: {item_id}")
        allowed = source.get("allowed_orientations") == "all" and bool((document.get("recipe") or {}).get("constraints", {}).get("allow_rotation", False))
        compatible = _is_permutation(original, oriented) if allowed else all(_near(a, b) for a, b in zip(original, oriented))
        if not compatible:
            errors.append(f"dimensión orientada incompatible: {item_id}")
        boxes.append(_box_record(placement, containers[container_id]))

    if len(packed_ids) != len(set(packed_ids)):
        errors.append("ids colocados duplicados")
    unpacked_ids = [row.get("item_id") for row in unpacked]
    if len(unpacked_ids) != len(set(unpacked_ids)):
        errors.append("ids no colocados duplicados")
    packed_set = set(packed_ids)
    unpacked_set = set(unpacked_ids)
    input_set = set(input_by_id)
    if packed_set & unpacked_set:
        errors.append("un ítem está colocado y no colocado")
    if packed_set | unpacked_set != input_set:
        errors.append("partición incompleta de la entrada")

    pairs = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i]["container_id"] != boxes[j]["container_id"]:
                continue
            ix = _interval_overlap(boxes[i]["flb_mm"][0], boxes[i]["max_corner_mm"][0], boxes[j]["flb_mm"][0], boxes[j]["max_corner_mm"][0])
            iy = _interval_overlap(boxes[i]["flb_mm"][1], boxes[i]["max_corner_mm"][1], boxes[j]["flb_mm"][1], boxes[j]["max_corner_mm"][1])
            iz = _interval_overlap(boxes[i]["flb_mm"][2], boxes[i]["max_corner_mm"][2], boxes[j]["flb_mm"][2], boxes[j]["max_corner_mm"][2])
            overlap = ix > TOLERANCE_MM and iy > TOLERANCE_MM and iz > TOLERANCE_MM
            pairs.append(
                {
                    "id_i": boxes[i]["item_id"],
                    "id_j": boxes[j]["item_id"],
                    "container_id": boxes[i]["container_id"],
                    "intersection_mm": {"x": ix, "y": iy, "z": iz},
                    "overlap": overlap,
                }
            )
    overlap_pairs = [pair for pair in pairs if pair["overlap"]]
    outside = [box for box in boxes if box["outside_bin"]]
    per_container = []
    for container_id, container in containers.items():
        owned = [box for box in boxes if box["container_id"] == container_id]
        per_container.append(
            {
                "container_id": container_id,
                "n_boxes": len(owned),
                "max_height_mm": max((box["max_corner_mm"][2] for box in owned), default=None),
                "packed_volume_mm3": sum(box["volume_mm3"] for box in owned),
                "bin_volume_mm3": float(container["length_mm"]) * float(container["width_mm"]) * float(container["height_mm"]),
            }
        )
    geometry_valid = not errors and not outside and not overlap_pairs
    return {
        "tolerance_mm": TOLERANCE_MM,
        "n_input": len(input_by_id),
        "n_packed": len(boxes),
        "n_unpacked": len(unpacked),
        "errors": errors,
        "n_boxes_outside_bin": len(outside),
        "n_overlap_pairs": len(overlap_pairs),
        "boxes": boxes,
        "pairs": pairs,
        "per_container": per_container,
        "internal_geometry_valid": geometry_valid,
        "all_items_packed": geometry_valid and len(unpacked) == 0 and len(boxes) == len(input_by_id),
        "physical_stability_verified": None,
        "note": "feasible del motor no se usa. Esta auditoría no declara cumplimiento de Zhao.",
    }


def contrast_export(document: dict[str, Any], legacy_plan: dict[str, Any], order_id: str) -> dict[str, Any]:
    actions = legacy_plan.get(order_id)
    if not isinstance(actions, list):
        return {"error": "el plan exportado no tiene la lista del pedido"}
    exported = {}
    for action in actions:
        item = action.get("item") or {}
        item_id = item.get("id")
        length, width, height = float(item["length"]), float(item["width"]), float(item["height"])
        orientation = int(action.get("orientation") or 0)
        oriented = (width, length, height) if orientation == 1 else (length, width, height)
        exported[item_id] = {
            "flb_mm": [float(v) for v in action["flb_coordinates"]],
            "exported_oriented_lwh_mm": list(oriented),
            "orientation": orientation,
        }
    lost = []
    position_mismatches = []
    for placement in document["placements"]:
        item_id = placement["item_id"]
        side = exported.get(item_id)
        if side is None:
            position_mismatches.append({"item_id": item_id, "reason": "ausente en la exportación"})
            continue
        if not all(_near(a, b) for a, b in zip(placement["flb_mm"], side["flb_mm"])):
            position_mismatches.append({"item_id": item_id, "reason": "FLB distinto"})
        if not _yaw_representable(placement["original_lwh_mm"], placement["oriented_lwh_mm"]):
            lost.append(
                {
                    "item_id": item_id,
                    "original_lwh_mm": placement["original_lwh_mm"],
                    "oriented_lwh_mm": placement["oriented_lwh_mm"],
                    "exported_yaw_lwh_mm": side["exported_oriented_lwh_mm"],
                }
            )
    return {
        "n_not_representable_as_yaw_0_1": len(lost),
        "lost_permutation_examples": lost[:8],
        "n_position_mismatches": len(position_mismatches),
        "same_item_ids": [row["item_id"] for row in document["placements"]] == [((action.get("item") or {}).get("id")) for action in actions],
    }


def contrast_historical(document: dict[str, Any], historical_plan: list[dict[str, Any]]) -> dict[str, Any]:
    new_ids = [row["item_id"] for row in document["placements"]]
    old_ids = [((action.get("item") or {}).get("id")) for action in historical_plan]
    same_order = new_ids == old_ids
    position_matches = 0
    old_by_id = {}
    for action in historical_plan:
        item_id = (action.get("item") or {}).get("id")
        old_by_id[item_id] = [float(v) for v in action["flb_coordinates"]]
    for placement in document["placements"]:
        previous = old_by_id.get(placement["item_id"])
        if previous is not None and all(_near(a, b) for a, b in zip(placement["flb_mm"], previous)):
            position_matches += 1
    reproduces = same_order and position_matches == len(document["placements"]) == len(historical_plan)
    return {
        "same_packed_id_order": same_order,
        "n_new": len(new_ids),
        "n_historical": len(old_ids),
        "n_matching_flb": position_matches,
        "reproduces_historical_placements": reproduces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita una solución interna capturada.")
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--legacy-export", type=Path, default=None)
    parser.add_argument("--historical-report", type=Path, default=None)
    parser.add_argument("--order-id", default=None)
    args = parser.parse_args(argv)
    document = json.loads(args.solution.expanduser().resolve().read_text(encoding="utf-8"))
    result = audit_document(document)
    order_id = args.order_id or document.get("order_id")
    if args.legacy_export is not None:
        legacy = json.loads(args.legacy_export.expanduser().resolve().read_text(encoding="utf-8"))
        result["export_contrast"] = contrast_export(document, legacy, str(order_id))
    if args.historical_report is not None:
        historical = json.loads(args.historical_report.expanduser().resolve().read_text(encoding="utf-8"))
        plan = (historical.get("packing_plan_nuestro") or {}).get(str(order_id))
        result["historical_contrast"] = contrast_historical(document, plan or [])
        if result.get("export_contrast") and not result["historical_contrast"]["reproduces_historical_placements"]:
            result["historical_contrast"]["note"] = (
                "La inferencia nueva no reproduce las colocaciones históricas. "
                "La pérdida yaw de esta ejecución no explica por sí sola el plan 09."
            )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "internal_geometry_valid": result["internal_geometry_valid"],
                "all_items_packed": result["all_items_packed"],
                "n_packed": result["n_packed"],
                "n_unpacked": result["n_unpacked"],
                "n_boxes_outside_bin": result["n_boxes_outside_bin"],
                "n_overlap_pairs": result["n_overlap_pairs"],
                "physical_stability_verified": result["physical_stability_verified"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
