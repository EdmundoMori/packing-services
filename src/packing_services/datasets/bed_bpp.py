"""Conversión BED-BPP → contratos internos de packing-services.

Dataset de referencia (IJRR 2023):
https://github.com/floriankagerer/bed-bpp-env

Integra pedidos reales (secuencia de ítems + target pallet/rollcontainer)
en ``PackAlgorithmInput`` / ``BenchmarkRequest`` sin alterar el núcleo
de algoritmos.
"""

from __future__ import annotations

from typing import Any

from ..domain.enums import PackingMode, ProblemType
from ..domain.models import ConstraintFlags, Container, Item
from ..domain.packing_modes import parse_packing_mode
from ..utils.errors import InvalidInputError

# Dimensiones oficiales del entorno bed-bpp-env (mm).
TARGET_SIZES_MM: dict[str, tuple[float, float, float]] = {
    "euro-pallet": (1200.0, 800.0, 2000.0),
    "rollcontainer": (800.0, 700.0, 2000.0),
}

DEFAULT_PALLET_MAX_WEIGHT_KG = 1500.0

BED_BPP_COMPATIBLE_PROBLEM_TYPES = {
    ProblemType.PALLETIZATION,
    ProblemType.STACKING_AWARE,
    ProblemType.SINGLE_CONTAINER_LOADING,
    ProblemType.THREE_D_BPP,
    ProblemType.CONTAINER_LOADING,
}


def looks_like_bed_bpp_orders(data: Any) -> bool:
    """True si ``data`` es un mapa pedido_id → {item_sequence, properties}."""
    if not isinstance(data, dict) or not data:
        return False
    # Evitar confusiones con PackAlgorithmInput.
    if "containers" in data and "items" in data:
        return False
    if data.get("input_format") == "bed_bpp":
        return False
    sample = next(iter(data.values()))
    return (
        isinstance(sample, dict)
        and isinstance(sample.get("item_sequence"), dict)
        and isinstance(sample.get("properties"), dict)
    )


def list_order_ids(orders: dict[str, Any]) -> list[str]:
    return sorted(orders.keys())


def smallest_order_id(orders: dict[str, Any]) -> str:
    """Pedido con menos ítems en ``item_sequence`` (desempate por id)."""
    ids = list_order_ids(orders)
    if not ids:
        raise InvalidInputError("Dataset BED-BPP vacío")
    return min(
        ids,
        key=lambda oid: (
            len((orders.get(oid) or {}).get("item_sequence") or {}),
            oid,
        ),
    )


def _resolve_target_container(target: str, order_id: str) -> Container:
    key = (target or "euro-pallet").strip().lower()
    if key in TARGET_SIZES_MM:
        length, width, height = TARGET_SIZES_MM[key]
        container_id = "EURO_PALLET" if key == "euro-pallet" else "ROLLCONTAINER"
    elif "," in key:
        parts = [float(p.strip()) for p in key.split(",")]
        if len(parts) < 2:
            raise InvalidInputError(f"target BED-BPP inválido: {target!r}")
        length, width = parts[0], parts[1]
        height = parts[2] if len(parts) >= 3 else 2000.0
        container_id = f"TARGET_{order_id}"
    else:
        raise InvalidInputError(
            f"target BED-BPP desconocido: {target!r}. "
            f"Use euro-pallet, rollcontainer o 'L,W,H' en mm."
        )
    return Container(
        id=container_id,
        length=length,
        width=width,
        height=height,
        max_weight=DEFAULT_PALLET_MAX_WEIGHT_KG,
    )


def _items_from_sequence(item_sequence: dict[str, Any]) -> list[Item]:
    items: list[Item] = []
    sorted_entries = sorted(
        item_sequence.items(),
        key=lambda kv: int(kv[1].get("sequence", kv[0]))
        if str(kv[1].get("sequence", kv[0])).isdigit()
        else int(kv[0]) if str(kv[0]).isdigit() else 0,
    )
    for _key, raw in sorted_entries:
        if not isinstance(raw, dict):
            raise InvalidInputError("Cada entrada de item_sequence debe ser un objeto")
        try:
            seq = int(raw.get("sequence", _key))
            article_id = str(raw["id"])
            items.append(
                Item(
                    id=f"{article_id}#{seq}",
                    length=float(raw["length/mm"]),
                    width=float(raw["width/mm"]),
                    height=float(raw["height/mm"]),
                    weight=float(raw.get("weight/kg", 0.0)),
                    quantity=1,
                    arrival_index=seq,
                    # bed-bpp-env usa orientación xy (rotar en planta) ≈ all axis-aligned.
                    allowed_orientations="all",
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidInputError(
                f"Ítem BED-BPP inválido en secuencia {_key}: {exc}"
            ) from exc
    if not items:
        raise InvalidInputError("item_sequence vacío")
    return items


def _default_constraints(problem_type: ProblemType) -> ConstraintFlags:
    if problem_type == ProblemType.STACKING_AWARE:
        return ConstraintFlags(
            non_overlap=True,
            containment=True,
            allow_rotation=True,
            max_weight=True,
            basic_stability=True,
            load_bearing=False,
        )
    return ConstraintFlags(
        non_overlap=True,
        containment=True,
        allow_rotation=True,
        max_weight=True,
    )


def _merge_parameters(
    parameters: dict[str, Any] | None,
    packing_mode: PackingMode,
) -> dict[str, Any]:
    """Offline: no impone sort (el algoritmo aplica volume_desc/weight_desc).
    Online: fuerza ``input_order``.
    """
    merged: dict[str, Any] = {}
    if packing_mode == PackingMode.ONLINE:
        merged["sort_strategy"] = "input_order"
    if parameters:
        merged.update(parameters)
    if packing_mode == PackingMode.ONLINE:
        sort = merged.get("sort_strategy")
        if sort not in (None, "input_order"):
            raise InvalidInputError(
                f"packing_mode=online no permite sort_strategy={sort!r}. "
                "Use input_order o packing_mode=offline."
            )
        merged["sort_strategy"] = "input_order"
    return merged


def _engines_with_sort(
    engines: list[dict[str, Any]],
    sort_strategy: str,
    *,
    overwrite: bool,
) -> list[dict[str, Any]]:
    """Aplica sort_strategy a motores. ``overwrite=False`` no pisa un valor ya puesto."""
    out: list[dict[str, Any]] = []
    for engine in engines:
        params = dict(engine.get("parameters") or {})
        if overwrite or "sort_strategy" not in params:
            params["sort_strategy"] = sort_strategy
        out.append({**engine, "parameters": params})
    return out


def _profile_engines_with_arrival_sort(
    problem_type: ProblemType | str,
    profile: str,
    sort_strategy: str,
) -> list[dict[str, Any]]:
    """Resuelve un perfil y fuerza el orden de llegada BED-BPP."""
    from ..benchmark.profiles import resolve_profile_engines

    configs = resolve_profile_engines(problem_type, profile)
    return [
        {
            "name": engine.name,
            "parameters": {**dict(engine.parameters or {}), "sort_strategy": sort_strategy},
        }
        for engine in configs
    ]


def convert_order_to_pack_input(
    orders: dict[str, Any],
    order_id: str,
    *,
    problem_type: ProblemType | str = ProblemType.PALLETIZATION,
    parameters: dict[str, Any] | None = None,
    constraints: dict[str, Any] | ConstraintFlags | None = None,
    request_id: str | None = None,
    random_seed: int | None = None,
    time_limit_seconds: float | None = None,
    target_override: str | None = None,
    packing_mode: PackingMode | str | None = None,
) -> dict[str, Any]:
    """Convierte un pedido BED-BPP a dict compatible con ``PackAlgorithmInput``."""
    mode = parse_packing_mode(packing_mode)
    if order_id not in orders:
        available = ", ".join(list_order_ids(orders)[:12])
        raise InvalidInputError(
            f"order_id={order_id!r} no está en el dataset BED-BPP. "
            f"Ejemplos: {available}"
        )
    order = orders[order_id]
    if not isinstance(order, dict):
        raise InvalidInputError(f"Pedido {order_id!r} mal formado")

    pt = (
        problem_type
        if isinstance(problem_type, ProblemType)
        else ProblemType(str(problem_type))
    )
    if pt not in BED_BPP_COMPATIBLE_PROBLEM_TYPES:
        raise InvalidInputError(
            f"problem_type={pt.value} no es compatible con BED-BPP. "
            f"Use uno de: {', '.join(sorted(p.value for p in BED_BPP_COMPATIBLE_PROBLEM_TYPES))}."
        )

    props = order.get("properties") or {}
    target = (
        target_override
        if target_override is not None
        else props.get("target", "euro-pallet")
    )
    container = _resolve_target_container(str(target), order_id)
    items = _items_from_sequence(order.get("item_sequence") or {})

    if isinstance(constraints, ConstraintFlags):
        flags = constraints
    elif isinstance(constraints, dict):
        flags = ConstraintFlags(**{**_default_constraints(pt).model_dump(), **constraints})
    else:
        flags = _default_constraints(pt)

    params = _merge_parameters(parameters, mode)
    payload: dict[str, Any] = {
        "problem_type": pt.value,
        "request_id": request_id or f"bed-bpp-{order_id}",
        "containers": [container.model_dump()],
        "items": [it.model_dump() for it in items],
        "constraints": flags.model_dump(),
        "objective": "maximize_volume_utilization",
        "packing_mode": mode.value,
        "parameters": params,
        "details": {
            "input_format": "bed_bpp",
            "order_id": order_id,
            "order_nr": props.get("order_nr"),
            "order_type": props.get("type"),
            "target": target,
            "units": "mm_kg",
            "n_items": len(items),
            "arrival_field": "sequence",
            "packing_mode": mode.value,
            "sort_strategy": params.get("sort_strategy"),
        },
    }
    if random_seed is not None:
        payload["random_seed"] = random_seed
    if time_limit_seconds is not None:
        payload["time_limit_seconds"] = time_limit_seconds
    return payload


def convert_order_to_benchmark_input(
    orders: dict[str, Any],
    order_id: str,
    *,
    problem_type: ProblemType | str = ProblemType.PALLETIZATION,
    engines: list[dict[str, Any]] | None = None,
    profile: str | None = None,
    parameters: dict[str, Any] | None = None,
    constraints: dict[str, Any] | ConstraintFlags | None = None,
    request_id: str | None = None,
    target_override: str | None = None,
    packing_mode: PackingMode | str | None = None,
) -> dict[str, Any]:
    """Convierte un pedido BED-BPP a dict compatible con ``BenchmarkRequest``."""
    mode = parse_packing_mode(packing_mode)
    pack = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=problem_type,
        parameters=parameters,
        constraints=constraints,
        request_id=request_id,
        target_override=target_override,
        packing_mode=mode,
    )
    bench: dict[str, Any] = {
        "problem_type": pack["problem_type"],
        "request_id": pack["request_id"],
        "containers": pack["containers"],
        "items": pack["items"],
        "constraints": pack["constraints"],
        "objective": pack["objective"],
        "packing_mode": mode.value,
        "details": pack.get("details", {}),
    }
    if engines:
        if mode == PackingMode.ONLINE:
            bench["engines"] = _engines_with_sort(
                engines, "input_order", overwrite=False
            )
        else:
            bench["engines"] = engines
    else:
        prof = profile or "constructive"
        bench["profile"] = prof
        if mode == PackingMode.ONLINE:
            bench["engines"] = _profile_engines_with_arrival_sort(
                pack["problem_type"], prof, "input_order"
            )
    return bench


def extract_orders_and_id(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Extrae (orders, order_id) desde un wrapper o dataset crudo+order_id."""
    if payload.get("input_format") == "bed_bpp" or "orders" in payload or "bed_bpp" in payload:
        orders = payload.get("orders") or payload.get("bed_bpp")
        if not isinstance(orders, dict) or not orders:
            raise InvalidInputError(
                "Entrada BED-BPP requiere 'orders' (mapa pedido → item_sequence)"
            )
        if not looks_like_bed_bpp_orders(orders):
            raise InvalidInputError(
                "Campo 'orders' no tiene estructura BED-BPP "
                "(cada pedido necesita item_sequence y properties)"
            )
        order_id = payload.get("order_id")
        if not order_id:
            raise InvalidInputError(
                "Entrada BED-BPP requiere 'order_id' para seleccionar el pedido"
            )
        return orders, str(order_id)

    if looks_like_bed_bpp_orders(payload):
        raise InvalidInputError(
            "Se detectó un dataset BED-BPP crudo. Envíe "
            "{'input_format':'bed_bpp','order_id':'...','orders':{...}} "
            "o use POST /api/v1/datasets/bed-bpp/convert"
        )

    raise InvalidInputError("El payload no es una entrada BED-BPP reconocible")


def normalize_execute_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Si el payload es BED-BPP, lo convierte a PackAlgorithmInput; si no, lo deja."""
    if not isinstance(payload, dict):
        return payload
    if payload.get("input_format") != "bed_bpp" and "orders" not in payload:
        if looks_like_bed_bpp_orders(payload):
            extract_orders_and_id(payload)  # raises with guidance
        return payload

    orders, order_id = extract_orders_and_id(payload)
    converted = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=payload.get("problem_type") or ProblemType.PALLETIZATION,
        parameters=payload.get("parameters"),
        constraints=payload.get("constraints"),
        request_id=payload.get("request_id"),
        random_seed=payload.get("random_seed"),
        time_limit_seconds=payload.get("time_limit_seconds"),
        packing_mode=payload.get("packing_mode"),
    )
    # PackAlgorithmInput forbids extra fields — strip details for validation.
    details = converted.pop("details", None)
    converted["_bed_bpp_details"] = details  # consumed only for logging; strip before validate
    converted.pop("_bed_bpp_details", None)
    return converted


def normalize_benchmark_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Si el payload es BED-BPP, lo convierte a BenchmarkRequest dict."""
    if not isinstance(payload, dict):
        return payload
    if payload.get("input_format") != "bed_bpp" and "orders" not in payload:
        return payload

    orders, order_id = extract_orders_and_id(payload)
    converted = convert_order_to_benchmark_input(
        orders,
        order_id,
        problem_type=payload.get("problem_type") or ProblemType.PALLETIZATION,
        engines=payload.get("engines"),
        profile=payload.get("profile"),
        parameters=payload.get("parameters"),
        constraints=payload.get("constraints"),
        request_id=payload.get("request_id"),
        packing_mode=payload.get("packing_mode"),
    )
    converted.pop("details", None)
    return converted
