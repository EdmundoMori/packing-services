"""Preflight del piloto 03A. Hashea el checkpoint y no lo deserializa."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

from pilot_common import (
    ACTOR_ALGORITHM,
    EXPECTED_N,
    HEURISTIC_ALGORITHM,
    MANIFEST_REL,
    METHODS,
    REPO_ROOT,
    SUBSET_REL,
    PilotError,
    evaluator_hashes,
    git_snapshot,
    load_json,
    sha256_file,
)
from pilot_problems import build_problem, problem_snapshot, shared_config

FLAG_KEYS = (
    "non_overlap",
    "containment",
    "allow_rotation",
    "max_weight",
    "basic_stability",
    "load_bearing",
    "fragility",
    "unloading_sequence",
)


def _condition(protocol: dict[str, Any], condition_id: str) -> Any:
    for row in protocol.get("common_conditions") or []:
        if isinstance(row, dict) and row.get("id") == condition_id:
            return row.get("value")
    raise PilotError(f"el protocolo no trae la condición {condition_id}", code="preflight")


def _sequence_records(order: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    sequence = order.get("item_sequence")
    if not isinstance(sequence, dict) or not sequence:
        raise ValueError("item_sequence vacío")
    records = []
    for raw in sequence.values():
        if not isinstance(raw, dict):
            raise ValueError("entrada de item_sequence inválida")
        weight = raw.get("weight/kg", 0.0)
        records.append(
            (
                float(raw["length/mm"]),
                float(raw["width/mm"]),
                float(raw["height/mm"]),
                float(weight),
            )
        )
    return sorted(records)


def _snapshot_records(snapshot: dict[str, Any]) -> list[tuple[float, float, float, float]]:
    return sorted(
        (
            float(item["length_mm"]),
            float(item["width_mm"]),
            float(item["height_mm"]),
            float(item["weight_kg"]),
        )
        for item in snapshot["items"]
    )


def _finite_positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) > 0


def _finite_nonnegative(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and float(value) >= 0


def preflight_independent(
    *,
    protocol: dict[str, Any],
    protocol_path: Path,
    dataset_path: Path,
    checkpoint_path: Path,
) -> dict[str, Any]:
    """Preflight del protocolo 07. Hashea el checkpoint y no lo deserializa."""

    from freeze_independent_sample import (
        FreezeStopped,
        check_pools,
        dataset_targets_match,
        frozen_list_sha256,
        pools_from_exposure,
        protocol_items,
        select_sample,
    )

    errors: list[str] = []
    if protocol.get("protocol_id") != "07_independent_evaluation":
        errors.append("el protocolo no es 07_independent_evaluation")
    if protocol.get("evaluation_executed") is True or protocol.get("not_scale_val") is not True:
        errors.append("la muestra 07 no está marcada como congelada y distinta de scale.val")
    orders = protocol.get("orders") or {}
    items = orders.get("items")
    if orders.get("n") != 200 or not isinstance(items, list) or len(items) != 200:
        errors.append("el protocolo 07 debe listar 200 pedidos")
        items = items if isinstance(items, list) else []
    if orders.get("n_euro_pallet") != 91 or orders.get("n_rollcontainer") != 109:
        errors.append("las cuotas deben ser 91 euro-pallet y 109 rollcontainer")

    def file_record(path: Path, role: str) -> dict[str, Any]:
        if not path.is_file():
            errors.append(f"no existe el archivo de {role}: {path}")
            return {"path": str(path), "role": role, "sha256": None}
        return {"path": str(path), "role": role, "sha256": sha256_file(path)}

    exposure_path = REPO_ROOT / str(orders.get("exposure_file") or "")
    full_path = REPO_ROOT / str(orders.get("full_test_manifest") or "")
    freeze_path = REPO_ROOT / str(orders.get("freeze_file") or "")
    files = {
        "source_dataset": file_record(dataset_path, "dataset fuente"),
        "full_test_manifest": file_record(full_path, "manifiesto full.test"),
        "exposure": file_record(exposure_path, "clasificación 06A"),
        "freeze": file_record(freeze_path, "muestra congelada"),
        "checkpoint": file_record(checkpoint_path, "checkpoint, solo hash de bytes"),
    }
    expected_checkpoint = ((protocol.get("methods") or {}).get("A") or {}).get("sha256")
    comparisons = {
        "source_dataset": orders.get("source_dataset_sha256"),
        "full_test_manifest": orders.get("full_test_sha256"),
        "exposure": orders.get("exposure_sha256"),
        "freeze": orders.get("freeze_sha256"),
        "checkpoint": expected_checkpoint,
    }
    for key, expected in comparisons.items():
        observed = files[key]["sha256"]
        if observed is None or observed != expected:
            errors.append(f"el hash de {key} no coincide con el protocolo")
    if "scale.val" in str(dataset_path) or "scale/val" in str(dataset_path):
        errors.append("el dataset de la evaluación 07 no es un subconjunto scale.val")
    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})

    exposure = load_json(exposure_path)
    full_split = load_json(full_path)
    full_test = {str(item) for item in (full_split.get("test") or [])} if isinstance(full_split, dict) else set()
    try:
        pools, exclusions = pools_from_exposure(exposure)
        check_pools(pools, exclusions, full_test)
        source_orders = load_json(dataset_path)
        if not isinstance(source_orders, dict):
            raise FreezeStopped("el dataset fuente no es un objeto")
        dataset_targets_match(source_orders, pools)
        selected = select_sample(pools, exclusions, full_test)
    except FreezeStopped as exc:
        raise PilotError(str(exc), code="preflight", details={"errors": [str(exc)], "files": files}) from exc
    expected_items = protocol_items(selected)
    if items != expected_items:
        errors.append("los pedidos del protocolo no reproducen la selección congelada")
    if frozen_list_sha256([row["order_id"] for row in items]) != orders.get("frozen_list_sha256"):
        errors.append("el hash de la lista congelada no coincide")
    if [row.get("order_id") for row in items] != sorted(row.get("order_id") for row in items):
        errors.append("el orden de ejecución no es el id ascendente")
    excluded_ids = {order_id for values in exclusions.values() for order_id in values}
    if excluded_ids & {row.get("order_id") for row in items}:
        errors.append("la muestra incluye una exclusión positiva")
    p_s = _condition(protocol, "p_s")
    constraints_expected = _condition(protocol, "constraints")
    arrival = _condition(protocol, "arrival_order")
    lookahead_p = int(p_s["lookahead_p"])
    select_s = int(p_s["select_s"])
    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})

    snapshots: dict[str, dict[str, dict[str, Any]]] = {}
    for row in items:
        order_id = str(row["order_id"])
        source_order = source_orders.get(order_id)
        if not isinstance(source_order, dict):
            errors.append(f"el pedido no está en el dataset fuente: {order_id}")
            continue
        source_target = str((source_order.get("properties") or {}).get("target") or "")
        if source_target != row.get("target") or source_target != row.get("target_source"):
            errors.append(f"el target del archivo no coincide con el protocolo: {order_id}")
            continue
        try:
            converted = {
                method: problem_snapshot(
                    build_problem(
                        source_orders,
                        order_id,
                        method,
                        checkpoint_path,
                        lookahead_p=lookahead_p,
                        select_s=select_s,
                    )
                )
                for method in METHODS
            }
        except Exception as exc:
            errors.append(f"la conversión falló: {order_id}: {exc}")
            continue
        shared = [shared_config(snapshot) for snapshot in converted.values()]
        if shared[0] != shared[1]:
            errors.append(f"los métodos no reciben el mismo problema: {order_id}")
        actor = converted["actor"]
        heuristic = converted["heuristic"]
        if actor["algorithm"] != ACTOR_ALGORITHM or heuristic["algorithm"] != HEURISTIC_ALGORITHM:
            errors.append(f"nombre de algoritmo distinto del ejecutor de producción: {order_id}")
        if actor["model_path"] != str(checkpoint_path) or heuristic["model_path"] is not None:
            errors.append(f"la ruta de modelo no queda solo en el actor: {order_id}")
        if actor["lookahead_p"] != lookahead_p or actor["select_s"] != select_s or actor["sort_strategy"] != arrival:
            errors.append(f"p, s o el orden de llegada no son los del protocolo: {order_id}")
        if actor["selection"] != "best_fit" or actor["problem_type"] != "3D_BPP" or actor["n_containers"] != 1:
            errors.append(f"selección, tipo o número de contenedores inesperado: {order_id}")
        if actor["min_support_ratio_effective"] != 0.0 or actor["consolidate_effective"] is not False:
            errors.append(f"soporte o consolidación efectivos distintos de la receta: {order_id}")
        flags = actor["constraints"]
        for key in FLAG_KEYS:
            if flags.get(key) is not constraints_expected.get(key):
                errors.append(f"bandera {key} distinta del protocolo: {order_id}")
        container = actor["containers"][0]
        expected_volume = float(row["container_length_mm"]) * float(row["container_width_mm"]) * float(row["container_height_mm"])
        checks = {
            "id": (container["id"], row["container_id"]),
            "length_mm": (container["length_mm"], row["container_length_mm"]),
            "width_mm": (container["width_mm"], row["container_width_mm"]),
            "height_mm": (container["height_mm"], row["container_height_mm"]),
            "max_weight_kg": (container["max_weight_kg"], row["max_weight_kg"]),
            "volume_mm3": (container["volume_mm3"], row["container_volume_mm3"]),
            "expected_volume": (expected_volume, row["container_volume_mm3"]),
            "protocol_max_weight": (container["max_weight_kg"], constraints_expected.get("max_weight_kg")),
        }
        for name, (observed, expected) in checks.items():
            if isinstance(observed, float) or isinstance(expected, float):
                if abs(float(observed) - float(expected)) > 1e-6:
                    errors.append(f"contenedor {name} distinto: {order_id}")
            elif observed != expected:
                errors.append(f"contenedor {name} distinto: {order_id}")
        if _snapshot_records(actor) != _sequence_records(source_order):
            errors.append(f"dimensiones o peso convertidos no coinciden con la entrada: {order_id}")
        for item in actor["items"]:
            if not _finite_positive(item["length_mm"]) or not _finite_positive(item["width_mm"]) or not _finite_positive(item["height_mm"]):
                errors.append(f"dimensión no positiva: {order_id}")
            if not _finite_nonnegative(item["weight_kg"]):
                errors.append(f"peso de entrada no finito o negativo: {order_id}")
            if item["allowed_orientations"] != "all":
                errors.append(f"orientaciones efectivas distintas de all: {order_id}")
        snapshots[order_id] = {"actor": actor, "heuristic": heuristic}
    euro = sum(1 for row in items if row.get("target") == "euro-pallet")
    roll = sum(1 for row in items if row.get("target") == "rollcontainer")
    if euro != 91 or roll != 109:
        errors.append("el recuento por target no coincide con el protocolo")
    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})
    try:
        provenance = {"git": git_snapshot(), "evaluator_sha256": evaluator_hashes()}
    except PilotError as exc:
        raise PilotError(str(exc), code="preflight", details=exc.details) from exc
    return {
        "ok": True,
        "checkpoint_loaded": False,
        "workers_started": False,
        "equivalent_configs": True,
        "amendment": "07",
        "protocol_id": "07_independent_evaluation",
        "n_orders": 200,
        "n_euro_pallet": 91,
        "n_rollcontainer": 109,
        "frozen_list_sha256": orders.get("frozen_list_sha256"),
        "files": files,
        "provenance": provenance,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "orders": [
            {
                "order_id": row["order_id"],
                "target": row["target"],
                "container_id": row["container_id"],
                "container_volume_mm3": row["container_volume_mm3"],
                "n_items": len(snapshots[row["order_id"]]["actor"]["items"]),
                "equivalent": True,
            }
            for row in items
        ],
        "snapshots": snapshots,
    }


def preflight(
    *,
    protocol_path: Path,
    dataset_path: Path,
    checkpoint_path: Path,
    manifest_path: Path | None = None,
    subset_path: Path | None = None,
) -> dict[str, Any]:
    protocol_path = protocol_path.expanduser().resolve()
    dataset_path = dataset_path.expanduser().resolve()
    checkpoint_path = checkpoint_path.expanduser().resolve()
    peeked = load_json(protocol_path)
    if isinstance(peeked, dict) and peeked.get("protocol_id") == "07_independent_evaluation":
        if manifest_path is not None or subset_path is not None:
            raise PilotError(
                "el protocolo 07 no acepta manifiesto ni subconjunto de validación",
                code="preflight",
            )
        return preflight_independent(
            protocol=peeked,
            protocol_path=protocol_path,
            dataset_path=dataset_path,
            checkpoint_path=checkpoint_path,
        )
    manifest_path = (manifest_path or (REPO_ROOT / MANIFEST_REL)).expanduser().resolve()
    subset_path = (subset_path or (REPO_ROOT / SUBSET_REL)).expanduser().resolve()
    errors: list[str] = []
    try:
        provenance = {
            "git": git_snapshot(),
            "evaluator_sha256": evaluator_hashes(),
        }
    except PilotError as exc:
        raise PilotError(str(exc), code="preflight", details=exc.details) from exc

    protocol = load_json(protocol_path)
    if not isinstance(protocol, dict):
        raise PilotError("el protocolo no es un objeto", code="preflight")
    if protocol.get("amendment") != "03A":
        errors.append("el protocolo vigente debe ser el ajuste 03A")
    if protocol.get("pilot_executed") is True:
        errors.append("este evaluador no marca ni acepta el protocolo como ya ejecutado")
    items = (protocol.get("orders") or {}).get("items")
    declared_n = (protocol.get("orders") or {}).get("n")
    if declared_n != EXPECTED_N or not isinstance(items, list) or len(items) != EXPECTED_N:
        errors.append(f"el protocolo debe listar exactamente {EXPECTED_N} pedidos")
        items = items if isinstance(items, list) else []
    expected_hashes = (protocol.get("orders") or {}).get("hashes") or {}
    expected_checkpoint = ((protocol.get("methods") or {}).get("A") or {}).get("sha256")

    def file_record(path: Path, role: str) -> dict[str, Any]:
        if not path.is_file():
            errors.append(f"no existe el archivo de {role}: {path}")
            return {"path": str(path), "role": role, "sha256": None}
        return {"path": str(path), "role": role, "sha256": sha256_file(path)}

    files = {
        "source_dataset": file_record(dataset_path, "dataset fuente"),
        "scale_val_orders": file_record(subset_path, "subconjunto de validación"),
        "scale_val_manifest": file_record(manifest_path, "manifiesto scale.val"),
        "checkpoint": file_record(checkpoint_path, "checkpoint, solo hash de bytes"),
    }
    source_sha = files["source_dataset"]["sha256"]
    subset_sha = files["scale_val_orders"]["sha256"]
    manifest_sha = files["scale_val_manifest"]["sha256"]
    checkpoint_sha = files["checkpoint"]["sha256"]
    if dataset_path == subset_path or (source_sha and source_sha == expected_hashes.get("scale_val_orders")):
        errors.append("el archivo --dataset es el subconjunto de validación, no el dataset fuente")
    elif source_sha != expected_hashes.get("source_dataset"):
        errors.append("el hash del dataset fuente no coincide con el protocolo")
    if subset_sha != expected_hashes.get("scale_val_orders"):
        errors.append("el hash del subconjunto de validación no coincide con el protocolo")
    if manifest_sha != expected_hashes.get("scale_val_manifest"):
        errors.append("el hash del manifiesto no coincide con el protocolo")
    if checkpoint_sha != expected_checkpoint:
        errors.append("el hash del checkpoint no coincide con el protocolo")
    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})

    manifest = load_json(manifest_path)
    source_orders = load_json(dataset_path)
    subset_orders = load_json(subset_path)
    if not isinstance(manifest, list) or [str(order_id) for order_id in manifest] != [row.get("order_id") for row in items]:
        errors.append("el manifiesto no reproduce los 20 ids en el orden del protocolo")
    p_s = _condition(protocol, "p_s")
    constraints_expected = _condition(protocol, "constraints")
    arrival = _condition(protocol, "arrival_order")
    lookahead_p = int(p_s["lookahead_p"])
    select_s = int(p_s["select_s"])
    accepted: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for index, row in enumerate(items):
        order_id = str(row.get("order_id"))
        if row.get("position") != index or row.get("targets_match") is not True:
            errors.append(f"posición o coincidencia de target inválida: {order_id}")
            continue
        target = row.get("target")
        if target not in {"euro-pallet", "rollcontainer"} or target != row.get("target_subset") or target != row.get("target_source"):
            errors.append(f"target distinto del contrato 03A: {order_id}")
            continue
        source_order = source_orders.get(order_id) if isinstance(source_orders, dict) else None
        subset_order = subset_orders.get(order_id) if isinstance(subset_orders, dict) else None
        if not isinstance(source_order, dict) or not isinstance(subset_order, dict):
            errors.append(f"el pedido no está en la fuente y en el subconjunto: {order_id}")
            continue
        source_target = str((source_order.get("properties") or {}).get("target") or "")
        subset_target = str((subset_order.get("properties") or {}).get("target") or "")
        if source_target != target or subset_target != target:
            errors.append(f"el target del archivo no coincide con el protocolo: {order_id}")
            continue
        try:
            if _sequence_records(source_order) != _sequence_records(subset_order):
                errors.append(f"la fuente y el subconjunto difieren en dimensiones o peso: {order_id}")
                continue
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"secuencia ilegible: {order_id}: {exc}")
            continue
        accepted.append((row, source_order))
    euro = sum(1 for row in items if row.get("target") == "euro-pallet")
    roll = sum(1 for row in items if row.get("target") == "rollcontainer")
    if euro != protocol["orders"].get("n_euro_pallet") or roll != protocol["orders"].get("n_rollcontainer"):
        errors.append("el recuento por target no coincide con el protocolo")
    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})

    snapshots: dict[str, dict[str, dict[str, Any]]] = {}
    for row, source_order in accepted:
        order_id = str(row["order_id"])
        converted: dict[str, dict[str, Any]] = {}
        try:
            for origin, orders in (("source", source_orders), ("subset", subset_orders)):
                for method in METHODS:
                    problem = build_problem(
                        orders,
                        order_id,
                        method,
                        checkpoint_path,
                        lookahead_p=lookahead_p,
                        select_s=select_s,
                    )
                    converted[f"{origin}:{method}"] = problem_snapshot(problem)
        except Exception as exc:
            errors.append(f"la conversión falló: {order_id}: {exc}")
            continue
        shared = [shared_config(snapshot) for snapshot in converted.values()]
        if any(candidate != shared[0] for candidate in shared[1:]):
            errors.append(f"los métodos o los archivos no reciben el mismo problema: {order_id}")
        actor = converted["source:actor"]
        heuristic = converted["source:heuristic"]
        if actor["algorithm"] != ACTOR_ALGORITHM or heuristic["algorithm"] != HEURISTIC_ALGORITHM:
            errors.append(f"nombre de algoritmo distinto del ejecutor de producción: {order_id}")
        if actor["model_path"] != str(checkpoint_path) or heuristic["model_path"] is not None:
            errors.append(f"la ruta de modelo no queda solo en el actor: {order_id}")
        if actor["lookahead_p"] != lookahead_p or actor["select_s"] != select_s or actor["sort_strategy"] != arrival:
            errors.append(f"p, s o el orden de llegada no son los del protocolo: {order_id}")
        if actor["selection"] != "best_fit" or actor["problem_type"] != "3D_BPP" or actor["n_containers"] != 1:
            errors.append(f"selección, tipo o número de contenedores inesperado: {order_id}")
        if actor["min_support_ratio_effective"] != 0.0 or actor["consolidate_effective"] is not False:
            errors.append(f"soporte o consolidación efectivos distintos de la receta: {order_id}")
        flags = actor["constraints"]
        for key in FLAG_KEYS:
            if flags.get(key) is not constraints_expected.get(key):
                errors.append(f"bandera {key} distinta del protocolo: {order_id}")
        container = actor["containers"][0]
        expected_volume = float(row["container_length_mm"]) * float(row["container_width_mm"]) * float(row["container_height_mm"])
        checks = {
            "id": (container["id"], row["container_id"]),
            "length_mm": (container["length_mm"], row["container_length_mm"]),
            "width_mm": (container["width_mm"], row["container_width_mm"]),
            "height_mm": (container["height_mm"], row["container_height_mm"]),
            "max_weight_kg": (container["max_weight_kg"], row["max_weight_kg"]),
            "volume_mm3": (container["volume_mm3"], row["container_volume_mm3"]),
            "expected_volume": (expected_volume, row["container_volume_mm3"]),
            "protocol_max_weight": (container["max_weight_kg"], constraints_expected.get("max_weight_kg")),
        }
        for name, (observed, expected) in checks.items():
            if isinstance(observed, float) or isinstance(expected, float):
                if abs(float(observed) - float(expected)) > 1e-6:
                    errors.append(f"contenedor {name} distinto: {order_id}")
            elif observed != expected:
                errors.append(f"contenedor {name} distinto: {order_id}")
        if _snapshot_records(actor) != _sequence_records(source_order):
            errors.append(f"dimensiones o peso convertidos no coinciden con la entrada: {order_id}")
        for item in actor["items"]:
            if not _finite_positive(item["length_mm"]) or not _finite_positive(item["width_mm"]) or not _finite_positive(item["height_mm"]):
                errors.append(f"dimensión no positiva: {order_id}")
            if not _finite_nonnegative(item["weight_kg"]):
                errors.append(f"peso de entrada no finito o negativo: {order_id}")
            if item["allowed_orientations"] != "all":
                errors.append(f"orientaciones efectivas distintas de all: {order_id}")
        snapshots[order_id] = {"actor": actor, "heuristic": heuristic}

    if errors:
        raise PilotError("preflight rechazado", code="preflight", details={"errors": errors, "files": files})
    return {
        "ok": True,
        "checkpoint_loaded": False,
        "workers_started": False,
        "equivalent_configs": True,
        "amendment": "03A",
        "n_orders": EXPECTED_N,
        "files": files,
        "provenance": provenance,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "orders": [
            {
                "order_id": row["order_id"],
                "target": row["target"],
                "container_id": row["container_id"],
                "container_volume_mm3": row["container_volume_mm3"],
                "n_items": len(snapshots[row["order_id"]]["actor"]["items"]),
                "equivalent": True,
            }
            for row in items
        ],
        "snapshots": snapshots,
    }
