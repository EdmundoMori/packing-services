"""Métricas y auditoría de peso del piloto. No usa feasible del motor."""

from __future__ import annotations

import importlib.util
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pilot_common import NO_CANDIDATE_REASON, TIE_EPS, format_delta

NUMERIC_TOLERANCE = 1e-6
RECIPE_EXACT = (
    "lookahead_p",
    "select_s",
    "selection",
    "sort_strategy",
    "problem_type",
    "algorithm",
    "n_containers",
    "consolidate_effective",
)

_AUDIT = None


def _audit_module() -> Any:
    global _AUDIT
    if _AUDIT is not None:
        return _AUDIT
    path = Path(__file__).resolve().parent / "audit_internal_solution.py"
    spec = importlib.util.spec_from_file_location("paper_tools_audit_internal_solution", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _AUDIT = module
    return module


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def audit_weight(document: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    containers = document.get("containers")
    inputs = document.get("input_items")
    placements = document.get("placements")
    recipe = document.get("recipe") if isinstance(document.get("recipe"), dict) else {}
    constraints = recipe.get("constraints") if isinstance(recipe.get("constraints"), dict) else {}
    max_weight_active = bool(constraints.get("max_weight"))
    if not isinstance(containers, list) or not isinstance(inputs, list) or not isinstance(placements, list):
        return {
            "weight_valid": False,
            "errors": ["la captura no trae contenedores, entrada y colocaciones"],
            "loaded_weight_kg": {},
            "physical_stability_verified": None,
        }
    input_weight: dict[str, float] = {}
    for row in inputs:
        if not isinstance(row, dict):
            errors.append("entrada de peso mal formada")
            continue
        item_id = row.get("item_id")
        weight = _finite_number(row.get("weight_kg"))
        if not isinstance(item_id, str) or weight is None or weight < 0:
            errors.append(f"peso de entrada no finito o negativo: {item_id}")
            continue
        input_weight[item_id] = weight
    container_max: dict[str, float] = {}
    for row in containers:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            errors.append("contenedor de peso mal formado")
            continue
        maximum = _finite_number(row.get("max_weight_kg"))
        if maximum is None or maximum < 0:
            errors.append(f"máximo de peso no finito o negativo: {row.get('id')}")
            continue
        container_max[row["id"]] = maximum
    loaded: dict[str, float] = {}
    for placement in placements:
        if not isinstance(placement, dict):
            errors.append("colocación de peso mal formada")
            continue
        item_id = placement.get("item_id")
        container_id = placement.get("container_id")
        weight = _finite_number(placement.get("weight_kg"))
        if not isinstance(item_id, str) or weight is None or weight < 0:
            errors.append(f"peso colocado no finito o negativo: {item_id}")
            continue
        expected = input_weight.get(item_id)
        if expected is None:
            errors.append(f"peso colocado sin entrada: {item_id}")
            continue
        if abs(weight - expected) > 1e-6:
            errors.append(f"peso colocado distinto de la entrada: {item_id}")
        if not isinstance(container_id, str):
            errors.append(f"contenedor del peso ausente: {item_id}")
            continue
        loaded[container_id] = loaded.get(container_id, 0.0) + weight
    if max_weight_active:
        for container_id, total in loaded.items():
            maximum = container_max.get(container_id)
            if maximum is None:
                errors.append(f"peso acumulado en contenedor desconocido: {container_id}")
                continue
            if total > maximum + 1e-6:
                errors.append(f"peso acumulado supera el máximo activo: {container_id}")
    return {
        "weight_valid": not errors,
        "errors": errors,
        "loaded_weight_kg": loaded,
        "max_weight_active": max_weight_active,
        "physical_stability_verified": None,
    }


def _close(observed: Any, expected: Any, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    left = _finite_number(observed)
    right = _finite_number(expected)
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def _index_rows(rows: Any, label: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return {}, [f"{label} no es una lista"]
    found: dict[str, dict[str, Any]] = {}
    seen: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"{label} contiene una entrada mal formada")
            continue
        identity = row.get("item_id") if "item_id" in row else row.get("id")
        if not isinstance(identity, str) or not identity:
            errors.append(f"{label} contiene una identidad ausente")
            continue
        seen.append(identity)
        if identity in found:
            errors.append(f"{label} repite la identidad {identity}")
            continue
        found[identity] = row
    if len(seen) != len(set(seen)):
        return found, errors
    return found, errors


def contrast_capture(
    capture: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    order_id: str,
    method: str,
) -> dict[str, Any]:
    """Compara la captura con el snapshot del preflight, no con otra parte de la captura."""

    errors: list[str] = []
    if capture.get("order_id") != order_id:
        errors.append(f"order_id de la captura distinto del caso: {capture.get('order_id')}")
    if capture.get("method") != method:
        errors.append(f"método de la captura distinto del caso: {capture.get('method')}")
    recipe = capture.get("recipe") if isinstance(capture.get("recipe"), dict) else {}
    if not recipe:
        errors.append("la captura no trae la configuración efectiva")
    elif recipe.get("method") not in (None, method):
        errors.append(f"método de la receta distinto del caso: {recipe.get('method')}")
    for key in RECIPE_EXACT:
        if recipe.get(key) != snapshot.get(key):
            errors.append(f"parámetro {key} distinto del snapshot")
    if not _close(recipe.get("min_support_ratio_effective"), snapshot.get("min_support_ratio_effective")):
        errors.append("soporte efectivo distinto del snapshot")
    expected_checkpoint = snapshot.get("model_path")
    observed_checkpoint = recipe.get("checkpoint_path")
    if expected_checkpoint is None:
        if observed_checkpoint not in (None,):
            errors.append("la heurística trae una ruta de modelo")
    elif observed_checkpoint != expected_checkpoint:
        errors.append("la ruta de modelo distinta del snapshot")
    expected_flags = snapshot.get("constraints") if isinstance(snapshot.get("constraints"), dict) else {}
    observed_flags = recipe.get("constraints") if isinstance(recipe.get("constraints"), dict) else None
    if not isinstance(observed_flags, dict):
        errors.append("las restricciones efectivas no son un objeto")
    else:
        if set(observed_flags) != set(expected_flags):
            errors.append("las restricciones efectivas no tienen las mismas claves que el snapshot")
        for key, expected in expected_flags.items():
            observed = observed_flags.get(key)
            if isinstance(expected, bool) or isinstance(observed, bool):
                if observed is not expected:
                    errors.append(f"restricción {key} distinta del snapshot")
            elif isinstance(expected, (int, float)):
                if not _close(observed, expected):
                    errors.append(f"restricción {key} distinta del snapshot")
            elif observed != expected:
                errors.append(f"restricción {key} distinta del snapshot")
    expected_items, item_errors = _index_rows(snapshot.get("items"), "snapshot de ítems")
    observed_items, observed_item_errors = _index_rows(capture.get("input_items"), "entrada de la captura")
    errors.extend(item_errors)
    errors.extend(observed_item_errors)
    if set(observed_items) != set(expected_items):
        errors.append("las identidades de la entrada no coinciden con el snapshot")
    for item_id, expected in expected_items.items():
        observed = observed_items.get(item_id)
        if observed is None:
            continue
        for axis, key in (("longitud", "length_mm"), ("anchura", "width_mm"), ("altura", "height_mm")):
            if not _close(observed.get(key), expected.get(key)):
                errors.append(f"dimensión original {axis} distinta del snapshot: {item_id}")
        if not _close(observed.get("weight_kg"), expected.get("weight_kg")):
            errors.append(f"peso de entrada distinto del snapshot: {item_id}")
        if observed.get("allowed_orientations") != expected.get("allowed_orientations"):
            errors.append(f"autorización de orientaciones distinta del snapshot: {item_id}")
    expected_bins, bin_errors = _index_rows(snapshot.get("containers"), "snapshot de contenedores")
    observed_bins, observed_bin_errors = _index_rows(capture.get("containers"), "contenedores de la captura")
    errors.extend(bin_errors)
    errors.extend(observed_bin_errors)
    if set(observed_bins) != set(expected_bins):
        errors.append("las identidades de contenedor no coinciden con el snapshot")
    for container_id, expected in expected_bins.items():
        observed = observed_bins.get(container_id)
        if observed is None:
            continue
        for axis, key in (("longitud", "length_mm"), ("anchura", "width_mm"), ("altura", "height_mm")):
            if not _close(observed.get(key), expected.get(key)):
                errors.append(f"dimensión de contenedor {axis} distinta del snapshot: {container_id}")
        if not _close(observed.get("max_weight_kg"), expected.get("max_weight_kg")):
            errors.append(f"peso máximo distinto del snapshot: {container_id}")
    placements = capture.get("placements") if isinstance(capture.get("placements"), list) else []
    for placement in placements:
        if not isinstance(placement, dict):
            errors.append("colocación mal formada frente al snapshot")
            continue
        item_id = placement.get("item_id")
        expected = expected_items.get(item_id) if isinstance(item_id, str) else None
        if expected is None:
            errors.append(f"colocación de un ítem ausente en el snapshot: {item_id}")
            continue
        original = placement.get("original_lwh_mm")
        expected_axes = [expected.get("length_mm"), expected.get("width_mm"), expected.get("height_mm")]
        if not isinstance(original, list) or len(original) != 3 or any(
            not _close(original[index], expected_axes[index]) for index in range(3)
        ):
            errors.append(f"dimensiones originales colocadas distintas del snapshot: {item_id}")
        if not _close(placement.get("weight_kg"), expected.get("weight_kg")):
            errors.append(f"peso colocado distinto del snapshot: {item_id}")
    return {
        "matches": not errors,
        "errors": errors,
        "reference": "preflight_snapshot",
        "tolerance": NUMERIC_TOLERANCE,
    }


def _requested_volume(document: dict[str, Any]) -> float | None:
    total = 0.0
    for row in document.get("input_items") or []:
        if not isinstance(row, dict):
            return None
        dims = [_finite_number(row.get(key)) for key in ("length_mm", "width_mm", "height_mm")]
        if any(value is None or value <= 0 for value in dims):
            return None
        total += float(dims[0]) * float(dims[1]) * float(dims[2])
    return total


def evaluate_outcome(
    outcome: dict[str, Any],
    *,
    order_id: str,
    method: str,
    target: str,
    container_volume_mm3: float,
    run_id: str,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = str(outcome.get("status") or "crash")
    duration = outcome.get("duration_seconds")
    duration_value = _finite_number(duration)
    base = {
        "run_id": run_id,
        "order_id": order_id,
        "method": method,
        "target": target,
        "worker_status": status,
        "error": outcome.get("error"),
        "duration_seconds": duration_value,
        "container_volume_mm3": container_volume_mm3,
        "effective_u_geom": 0.0,
        "raw_u_geom": None,
        "raw_packed_volume_mm3": None,
        "item_fraction": None,
        "requested_volume_fraction": None,
        "max_height_mm": None,
        "n_packed": None,
        "n_unpacked": None,
        "n_unpacked_no_candidate": None,
        "method_failure": True,
        "geometry_invalid": False,
        "weight_violation": False,
        "input_mismatch": False,
        "worker_failure": outcome.get("worker_failure"),
        "returncode": outcome.get("returncode"),
        "failure_types": ["method_failure"],
        "physical_stability_verified": None,
        "time_is_diagnostic_only": True,
    }
    if status != "ok":
        return base
    document = outcome.get("capture")
    if not isinstance(document, dict):
        base["error"] = base["error"] or "el worker no entregó una captura"
        return base
    geometry = _audit_module().audit_document(document)
    weight = audit_weight(document)
    base["method_failure"] = False
    base["failure_types"] = []
    packed_volume = 0.0
    max_height = None
    per_container = geometry.get("per_container") if isinstance(geometry, dict) else None
    if isinstance(per_container, list):
        for row in per_container:
            if not isinstance(row, dict):
                continue
            volume = _finite_number(row.get("packed_volume_mm3"))
            if volume is not None and volume >= 0:
                packed_volume += volume
            height = _finite_number(row.get("max_height_mm"))
            if height is not None:
                max_height = height if max_height is None else max(max_height, height)
    container_ok = True
    containers = document.get("containers")
    if not isinstance(containers, list) or len(containers) != 1:
        container_ok = False
    else:
        container = containers[0]
        dims = [_finite_number(container.get(key)) for key in ("length_mm", "width_mm", "height_mm")]
        if any(value is None or value <= 0 for value in dims):
            container_ok = False
        else:
            observed = float(dims[0]) * float(dims[1]) * float(dims[2])
            if abs(observed - container_volume_mm3) > 1e-6:
                container_ok = False
    geometry_valid = bool(geometry.get("internal_geometry_valid")) and container_ok
    weight_valid = bool(weight.get("weight_valid"))
    n_input = geometry.get("n_input")
    n_packed = geometry.get("n_packed")
    n_unpacked = geometry.get("n_unpacked")
    unpacked_rows = document.get("unpacked") if isinstance(document.get("unpacked"), list) else []
    n_no_candidate = sum(
        1
        for row in unpacked_rows
        if isinstance(row, dict) and row.get("reason") == NO_CANDIDATE_REASON
    )
    requested = _requested_volume(document)
    raw_u = None
    if container_volume_mm3 > 0 and packed_volume >= 0 and container_ok:
        raw_u = packed_volume / container_volume_mm3
    base.update(
        {
            "raw_u_geom": raw_u,
            "raw_packed_volume_mm3": packed_volume if container_ok else None,
            "item_fraction": (n_packed / n_input) if isinstance(n_input, int) and n_input > 0 and isinstance(n_packed, int) else None,
            "requested_volume_fraction": (packed_volume / requested) if requested not in (None, 0) and container_ok else None,
            "max_height_mm": max_height,
            "n_packed": n_packed if isinstance(n_packed, int) else None,
            "n_unpacked": n_unpacked if isinstance(n_unpacked, int) else None,
            "n_unpacked_no_candidate": n_no_candidate,
            "geometry_invalid": not geometry_valid,
            "weight_violation": not weight_valid,
            "audit_error_count": len(geometry.get("errors") or []) + len(weight.get("errors") or []),
        }
    )
    if not geometry_valid:
        base["failure_types"].append("geometry_invalid")
    if not weight_valid:
        base["failure_types"].append("weight_violation")
    contrast = None
    if snapshot is not None:
        contrast = contrast_capture(document, snapshot, order_id=order_id, method=method)
        base["input_mismatch"] = not contrast["matches"]
        if not contrast["matches"]:
            base["failure_types"].append("input_mismatch")
            base["error"] = "; ".join(contrast["errors"])
    base["effective_u_geom"] = 0.0 if base["failure_types"] else float(raw_u or 0.0)
    base["audits"] = {"geometry": geometry, "weight": weight, "input_contrast": contrast}
    return base


def _winner(delta: float) -> str:
    if abs(delta) <= TIE_EPS:
        return "tie"
    if delta > 0:
        return "actor"
    return "heuristic"


def build_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_order: dict[str, dict[str, dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        order_id = row["order_id"]
        if order_id not in by_order:
            by_order[order_id] = {}
            order.append(order_id)
        by_order[order_id][row["method"]] = row
    pairs = []
    for order_id in order:
        sides = by_order[order_id]
        actor = sides["actor"]
        heuristic = sides["heuristic"]
        delta = float(actor["effective_u_geom"]) - float(heuristic["effective_u_geom"])
        raw_delta = None
        if actor["raw_u_geom"] is not None and heuristic["raw_u_geom"] is not None:
            raw_delta = float(actor["raw_u_geom"]) - float(heuristic["raw_u_geom"])
        pairs.append(
            {
                "order_id": order_id,
                "target": actor["target"],
                "container_volume_mm3": actor["container_volume_mm3"],
                "delta": delta,
                "raw_delta": raw_delta,
                "tie": abs(delta) <= TIE_EPS,
                "winner": _winner(delta),
                "actor_failure": bool(actor["failure_types"]),
                "heuristic_failure": bool(heuristic["failure_types"]),
                "actor": {key: value for key, value in actor.items() if key != "audits"},
                "heuristic": {key: value for key, value in heuristic.items() if key != "audits"},
            }
        )
    return pairs


def _group_stats(deltas: list[float], actor_failures: int, heuristic_failures: int) -> dict[str, Any]:
    ordered = sorted(deltas)
    return {
        "n": len(deltas),
        "mean_delta": statistics.fmean(deltas),
        "median_delta": statistics.median(ordered),
        "wins": sum(1 for value in deltas if value > TIE_EPS),
        "ties": sum(1 for value in deltas if abs(value) <= TIE_EPS),
        "losses": sum(1 for value in deltas if value < -TIE_EPS),
        "actor_failures": actor_failures,
        "heuristic_failures": heuristic_failures,
    }


def aggregate(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if not pairs:
        raise ValueError("no hay pares")
    deltas = [float(pair["delta"]) for pair in pairs]
    by_target: dict[str, dict[str, Any]] = {}
    targets: list[str] = []
    for pair in pairs:
        target = str(pair["target"])
        if target not in by_target:
            by_target[target] = {"deltas": [], "actor_failures": 0, "heuristic_failures": 0}
            targets.append(target)
        bucket = by_target[target]
        bucket["deltas"].append(float(pair["delta"]))
        bucket["actor_failures"] += int(bool(pair["actor_failure"]))
        bucket["heuristic_failures"] += int(bool(pair["heuristic_failure"]))
    grouped = {
        target: _group_stats(bucket["deltas"], bucket["actor_failures"], bucket["heuristic_failures"])
        for target, bucket in by_target.items()
    }
    overall = _group_stats(
        deltas,
        sum(int(bool(pair["actor_failure"])) for pair in pairs),
        sum(int(bool(pair["heuristic_failure"])) for pair in pairs),
    )
    return {
        "n": len(pairs),
        "mean_delta": overall["mean_delta"],
        "median_delta": overall["median_delta"],
        "wins": overall["wins"],
        "ties": overall["ties"],
        "losses": overall["losses"],
        "actor_failures": overall["actor_failures"],
        "heuristic_failures": overall["heuristic_failures"],
        "by_target": {target: grouped[target] for target in targets},
        "tie_rule": "abs(delta) <= 1e-9",
        "primary": "media aritmética de delta, mismo peso por pedido",
        "time_is_diagnostic_only": True,
        "physical_stability_verified": None,
    }


def secondary_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for method in ("actor", "heuristic"):
        selected = [row for row in rows if row["method"] == method]

        def mean(key: str, group: list[dict[str, Any]] = selected) -> float | None:
            values = [float(row[key]) for row in group if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)]
            return statistics.fmean(values) if values else None

        kinds: Counter[str] = Counter()
        for row in selected:
            for kind in row["failure_types"]:
                kinds[kind] += 1
        report[method] = {
            "n": len(selected),
            "item_fraction_mean": mean("item_fraction"),
            "requested_volume_fraction_mean": mean("requested_volume_fraction"),
            "max_height_mm_mean": mean("max_height_mm"),
            "duration_seconds_mean": mean("duration_seconds"),
            "null_item_fraction": sum(1 for row in selected if row.get("item_fraction") is None),
            "failure_types": dict(kinds),
            "rows_with_unpacked_no_candidate": sum(1 for row in selected if (row.get("n_unpacked_no_candidate") or 0) > 0),
        }
    report["time_is_diagnostic_only"] = True
    return report


def render_summary(summary: dict[str, Any]) -> str:
    lines = ["# Resumen del piloto interno", "", f"Estado: {summary['status']}."]
    if summary.get("status") != "complete":
        lines.extend(
            [
                "",
                "Esta corrida no está completa. No hay un resultado del piloto.",
                "El tiempo es diagnóstico y no permite afirmar mayor eficiencia.",
                "La estabilidad física permanece sin verificar.",
            ]
        )
        return "\n".join(lines) + "\n"
    sentence = (
        "En este conjunto de desarrollo, bajo el protocolo geométrico especificado, "
        f"el actor obtuvo una diferencia de {format_delta(summary['mean_delta'])} frente a GreedyBestFit."
    )
    lines.extend(
        [
            "",
            sentence,
            "El agregado depende de la composición de estos pedidos. No equivale a una ventaja demostrada para cada target ni para toda la colección.",
            "El tiempo es diagnóstico y no permite afirmar mayor eficiencia.",
            "La estabilidad física permanece sin verificar.",
            "",
            (
                f"n={summary['n']}, media={format_delta(summary['mean_delta'])}, "
                f"mediana={format_delta(summary['median_delta'])}, "
                f"victorias={summary['wins']}, empates={summary['ties']}, derrotas={summary['losses']}."
            ),
            "",
            "Desglose por target:",
        ]
    )
    for target, group in summary["by_target"].items():
        lines.append(
            f"- {target}: n={group['n']}, media={format_delta(group['mean_delta'])}, "
            f"mediana={format_delta(group['median_delta'])}, victorias={group['wins']}, "
            f"empates={group['ties']}, derrotas={group['losses']}, "
            f"fallos actor={group['actor_failures']}, fallos heurística={group['heuristic_failures']}."
        )
    secondary = summary.get("secondary") or {}
    if secondary:
        lines.extend(["", "Secundarias, con el tiempo solo como diagnóstico:"])
        for method in ("actor", "heuristic"):
            block = secondary.get(method) or {}
            lines.append(
                f"- {method}: fracción de ítems={format_delta(block['item_fraction_mean']) if block.get('item_fraction_mean') is not None else 'null'}, "
                f"fracción del volumen solicitado={format_delta(block['requested_volume_fraction_mean']) if block.get('requested_volume_fraction_mean') is not None else 'null'}, "
                f"altura máxima media={format_delta(block['max_height_mm_mean']) if block.get('max_height_mm_mean') is not None else 'null'}, "
                f"tipos de fallo={block.get('failure_types')}, "
                f"filas con ítems sin candidata={block.get('rows_with_unpacked_no_candidate')}."
            )
    lines.extend(
        [
            "",
            (
                f"Fallos de método, geometría o peso: actor={summary['actor_failures']}, "
                f"heurística={summary['heuristic_failures']}. Siguen dentro del denominador."
            ),
            "Los ítems no colocados por falta de candidata forman parte del resultado y no son un fallo de método.",
        ]
    )
    return "\n".join(lines) + "\n"
