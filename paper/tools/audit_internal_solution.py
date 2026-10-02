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
NOTE = (
    "Este auditor comprueba la geometría de la captura: contención, solapes "
    "en el mismo contenedor, partición de ítems y permutaciones autorizadas. "
    "No verifica todas las restricciones físicas ni todas las reglas de los papers. "
    "physical_stability_verified queda null."
)


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


def _triple(value: Any) -> list[float] | None:
    """Lista de exactamente tres números finitos. Los booleanos no cuentan."""

    if not isinstance(value, list) or len(value) != 3 or not all(_finite(item) for item in value):
        return None
    return [float(item) for item in value]


def _positive_triple(value: Any) -> list[float] | None:
    parsed = _triple(value)
    if parsed is None or any(item <= 0 for item in parsed):
        return None
    return parsed


def _axis_match(left: list[float], right: list[float], eps: float = TOLERANCE_MM) -> bool:
    return all(_near(a, b, eps) for a, b in zip(left, right))


def _empty_result(errors: list[str]) -> dict[str, Any]:
    return {
        "tolerance_mm": TOLERANCE_MM,
        "n_input": 0,
        "n_packed": 0,
        "n_unpacked": 0,
        "errors": errors,
        "n_boxes_outside_bin": 0,
        "n_overlap_pairs": 0,
        "boxes": [],
        "pairs": [],
        "per_container": [],
        "internal_geometry_valid": False,
        "all_items_packed": False,
        "physical_stability_verified": None,
        "note": NOTE,
    }


def _usable_containers(rows: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return {}, ["containers no es una lista"]
    ids: list[str] = []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row.get("id"):
            errors.append("contenedor mal formado")
            continue
        ids.append(row["id"])
        parsed.append(row)
    if len(ids) != len(set(ids)):
        errors.append("ids de contenedor duplicados")
        return {}, errors
    usable: dict[str, dict[str, Any]] = {}
    for row in parsed:
        dims = (row.get("length_mm"), row.get("width_mm"), row.get("height_mm"))
        if not all(_finite(value) and float(value) > 0 for value in dims):
            errors.append(f"bin no finito o no positivo: {row['id']}")
            continue
        usable[row["id"]] = {
            "id": row["id"],
            "length_mm": float(dims[0]),
            "width_mm": float(dims[1]),
            "height_mm": float(dims[2]),
        }
    return usable, errors


def _input_map(rows: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return {}, ["input_items no es una lista"]
    found: dict[str, dict[str, Any]] = {}
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or not row.get("item_id"):
            errors.append("id de entrada inválido")
            continue
        item_id = row["item_id"]
        ids.append(item_id)
        dims = (row.get("length_mm"), row.get("width_mm"), row.get("height_mm"))
        if not all(_finite(value) and float(value) > 0 for value in dims):
            errors.append(f"dimensiones de entrada no finitas o no positivas: {item_id}")
            continue
        found[item_id] = {
            "item_id": item_id,
            "length_mm": float(dims[0]),
            "width_mm": float(dims[1]),
            "height_mm": float(dims[2]),
            "allowed_orientations": row.get("allowed_orientations"),
        }
    if len(ids) != len(set(ids)):
        errors.append("ids de entrada duplicados")
    return found, errors


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
    if not isinstance(document, dict):
        return _empty_result(["el documento no es un objeto"])
    errors: list[str] = []
    containers, container_errors = _usable_containers(document.get("containers"))
    errors.extend(container_errors)
    input_by_id, input_errors = _input_map(document.get("input_items"))
    errors.extend(input_errors)
    placements = document.get("placements")
    unpacked = document.get("unpacked")
    if not isinstance(placements, list):
        errors.append("placements no es una lista")
        placements = []
    if not isinstance(unpacked, list):
        errors.append("unpacked no es una lista")
        unpacked = []

    packed_ids: list[Any] = []
    boxes: list[dict[str, Any]] = []
    allow_rotation = bool(((document.get("recipe") or {}) if isinstance(document.get("recipe"), dict) else {}).get("constraints", {}).get("allow_rotation", False))
    for placement in placements:
        if not isinstance(placement, dict):
            errors.append("colocación mal formada")
            continue
        item_id = placement.get("item_id")
        container_id = placement.get("container_id")
        packed_ids.append(item_id)
        if item_id not in input_by_id:
            errors.append(f"ítem colocado desconocido: {item_id}")
            continue
        if container_id not in containers:
            errors.append(f"contenedor desconocido o no utilizable: {container_id}")
            continue
        flb = _triple(placement.get("flb_mm"))
        original = _positive_triple(placement.get("original_lwh_mm"))
        oriented = _positive_triple(placement.get("oriented_lwh_mm"))
        if flb is None or original is None or oriented is None:
            errors.append(f"vectores de tres números finitos y dimensiones positivas requeridos: {item_id}")
            continue
        source = input_by_id[item_id]
        source_dims = [source["length_mm"], source["width_mm"], source["height_mm"]]
        if not _axis_match(source_dims, original):
            errors.append(f"dimensiones originales no coinciden eje a eje con la entrada: {item_id}")
            continue
        rotation_allowed = allow_rotation and source.get("allowed_orientations") == "all"
        compatible = _is_permutation(original, oriented) if rotation_allowed else _axis_match(original, oriented)
        if not compatible:
            errors.append(f"dimensión orientada incompatible: {item_id}")
            continue
        checked = {
            **placement,
            "flb_mm": flb,
            "original_lwh_mm": original,
            "oriented_lwh_mm": oriented,
        }
        boxes.append(_box_record(checked, containers[container_id]))

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
        "note": NOTE,
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
    """Compara solo el orden de IDs colocados y el FLB. No es igualdad del plan."""

    placements = document.get("placements") if isinstance(document.get("placements"), list) else []
    new_ids = [row.get("item_id") for row in placements if isinstance(row, dict)]
    old_ids = [((action.get("item") or {}).get("id")) if isinstance(action, dict) else None for action in historical_plan]
    same_order = new_ids == old_ids
    position_matches = 0
    old_by_id: dict[Any, list[float]] = {}
    for action in historical_plan:
        if not isinstance(action, dict):
            continue
        item_id = (action.get("item") or {}).get("id")
        flb = _triple(action.get("flb_coordinates"))
        if flb is not None:
            old_by_id[item_id] = flb
    for placement in placements:
        if not isinstance(placement, dict):
            continue
        previous = old_by_id.get(placement.get("item_id"))
        current = _triple(placement.get("flb_mm"))
        if previous is not None and current is not None and all(_near(a, b) for a, b in zip(current, previous)):
            position_matches += 1
    same_ids_and_flb = same_order and position_matches == len(placements) == len(historical_plan)
    return {
        "comparison_scope": (
            "Orden de item_id colocados y coordenadas FLB. "
            "No incluye dimensiones ni orientation; no es igualdad completa del plan."
        ),
        "same_ordered_ids": same_order,
        "n_new": len(new_ids),
        "n_historical": len(old_ids),
        "n_matching_flb": position_matches,
        "same_ordered_ids_and_flb": same_ids_and_flb,
    }


def legacy_actions_equal(left: list[Any], right: list[Any], eps: float = TOLERANCE_MM) -> bool:
    """Igualdad completa de dos listas de acciones legacy: id, dimensiones, orientation y FLB."""

    if len(left) != len(right):
        return False
    for first, second in zip(left, right):
        if not isinstance(first, dict) or not isinstance(second, dict):
            return False
        item_a = first.get("item") if isinstance(first.get("item"), dict) else {}
        item_b = second.get("item") if isinstance(second.get("item"), dict) else {}
        if item_a.get("id") != item_b.get("id") or first.get("orientation") != second.get("orientation"):
            return False
        for key in ("length", "width", "height"):
            if not _finite(item_a.get(key)) or not _finite(item_b.get(key)) or not _near(float(item_a[key]), float(item_b[key]), eps):
                return False
        flb_a = _triple(first.get("flb_coordinates"))
        flb_b = _triple(second.get("flb_coordinates"))
        if flb_a is None or flb_b is None or not all(_near(a, b, eps) for a, b in zip(flb_a, flb_b)):
            return False
    return True


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
        if result.get("export_contrast") and not result["historical_contrast"]["same_ordered_ids_and_flb"]:
            result["historical_contrast"]["note"] = (
                "Los IDs ordenados o el FLB no coinciden con el plan histórico. "
                "Esta comprobación no es igualdad completa de las acciones."
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
