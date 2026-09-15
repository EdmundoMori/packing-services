"""Comparación de producto offline vs online sobre el holdout BED-BPP.

Los cinco pedidos de ``examples/5_bed-bpp.json`` (``PRODUCT_HOLDOUT_ORDER_IDS``)
nunca se usaron para entrenar ni para ajustar. Este experimento los recorre
completos y ejecuta, sobre la misma entrada, el mismo validador y las mismas
métricas:

- ``packing_mode=offline``: constructivos que ya figuran en el experimento
  conjunto, con el orden por volumen que es su default.
- ``packing_mode=online``: heurístico y política aprendida al mismo presupuesto
  de información ``(p, s)``, de modo que cada par se compare a igual
  información y no a igual nombre.

Las restricciones y el criterio de ranking se importan de
``joint_single_container``: la comparabilidad no depende de este módulo. No
reentrena, no modifica el encoder, el bucle online ni los defaults del execute.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..datasets.bed_bpp import TARGET_SIZES_MM, convert_order_to_pack_input
from ..domain.enums import PackingMode, ProblemType
from ..domain.models import Metrics, PackingProblem
from ..domain.packing_modes import default_sort_for_mode
from ..online.learned.production import (
    CINTA_LOOKAHEAD_P,
    CINTA_MODEL_PATH,
    CINTA_SELECT_S,
    DEFAULT_LOOKAHEAD_P,
    DEFAULT_MODEL_PATH,
    DEFAULT_SELECT_S,
    PRODUCT_HOLDOUT_ORDER_IDS,
)
from ..schemas.requests import PackAlgorithmInput
from ..schemas.responses import BenchmarkEngineResult, BenchmarkResponse
from ..utils.errors import PackingError
from ..utils.logging import get_logger
from .joint_single_container import _constraints_for, _ranking_key

logger = get_logger(__name__)

# Orden estable para que la tabla sea reproducible entre corridas.
HOLDOUT_ORDER_IDS: tuple[str, ...] = tuple(sorted(PRODUCT_HOLDOUT_ORDER_IDS))

RANKING_HOLDOUT = (
    "Ranking por pedido (mismo contenedor, mismo validador, mismas métricas): "
    "(1) soluciones válidas; (2) mayor volume_utilization; "
    "(3) menor items_unpacked; (4) menor tiempo. "
    "Los motores offline ven el pedido completo; los online respetan la "
    "llegada con el presupuesto (p, s) indicado en la etiqueta."
)

RANKING_HOLDOUT_MULTI = (
    "Ranking por pedido con varios contenedores idénticos disponibles: "
    "(1) soluciones válidas; (2) menor items_unpacked; (3) menor containers_used; "
    "(4) mayor volume_utilization; (5) menor tiempo. "
    "Los ítems fuera van antes que el número de pallets porque un pedido que "
    "no sale completo no se despacha; si fuera al revés, dejar carga en el "
    "muelle parecería mejor que abrir el segundo pallet. El cubo va después "
    "porque se divide entre los contenedores efectivamente usados y ya "
    "penaliza por sí solo abrir uno de más."
)


@dataclass(frozen=True)
class HoldoutEngine:
    """Un motor concreto con su modo, tipo de problema y parámetros."""

    mode: PackingMode
    problem_type: ProblemType
    algorithm: str
    variant: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        base = f"{self.mode.value}:{self.problem_type.value}/{self.algorithm}"
        return f"{base}#{self.variant}" if self.variant else base


_ONLINE = PackingMode.ONLINE
_OFFLINE = PackingMode.OFFLINE

# Offline: tres constructivos ya presentes en JOINT_ENGINES, uno por familia de
# construcción (puntos extremos, best-fit decreciente, capas).
# Online: cada política aprendida enfrentada al heurístico en su mismo (p, s).
# consolidate=false fija el menú libre: este script es la medición de Fase 0/1.
# El execute de producto consolida por default si hay 2+ contenedores.
HOLDOUT_ENGINES: tuple[HoldoutEngine, ...] = (
    HoldoutEngine(_OFFLINE, ProblemType.THREE_D_BPP, "extreme_points_3d"),
    HoldoutEngine(_OFFLINE, ProblemType.THREE_D_BPP, "best_fit_decreasing_3d"),
    HoldoutEngine(_OFFLINE, ProblemType.PALLETIZATION, "layer_based_palletization"),
    HoldoutEngine(
        _ONLINE,
        ProblemType.PALLETIZATION,
        "online_3d_bpp_heuristic",
        variant="p1s1",
        parameters={
            "lookahead_p": DEFAULT_LOOKAHEAD_P,
            "select_s": DEFAULT_SELECT_S,
            "consolidate": False,
        },
    ),
    HoldoutEngine(
        _ONLINE,
        ProblemType.PALLETIZATION,
        "drl_policy_3d_bpp",
        variant="mlp_p1s1",
        parameters={
            "lookahead_p": DEFAULT_LOOKAHEAD_P,
            "select_s": DEFAULT_SELECT_S,
            "model_path": DEFAULT_MODEL_PATH,
            "consolidate": False,
        },
    ),
    HoldoutEngine(
        _ONLINE,
        ProblemType.PALLETIZATION,
        "online_3d_bpp_heuristic",
        variant="p3s2",
        parameters={
            "lookahead_p": CINTA_LOOKAHEAD_P,
            "select_s": CINTA_SELECT_S,
            "consolidate": False,
        },
    ),
    HoldoutEngine(
        _ONLINE,
        ProblemType.PALLETIZATION,
        "drl_policy_3d_bpp",
        variant="mlp_p3s2",
        parameters={
            "lookahead_p": CINTA_LOOKAHEAD_P,
            "select_s": CINTA_SELECT_S,
            "model_path": CINTA_MODEL_PATH,
            "consolidate": False,
        },
    ),
)


def _multi_ranking_key(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    return (
        0 if result.is_valid else 1,
        m.items_unpacked,
        m.containers_used,
        -m.volume_utilization,
        -(result.details.get("envelope_utilization") or 0.0),
        m.execution_time_seconds,
        result.engine,
    )


def replicate_containers(payload: dict[str, Any], count: int) -> None:
    """Deja ``count`` contenedores idénticos, con ids distinguibles.

    Con ``count == 1`` no toca nada, de modo que la tabla de un solo
    contenedor sigue siendo bit a bit la misma que antes.
    """

    if count <= 1:
        return
    base = payload["containers"][0]
    payload["containers"] = [
        {**base, "id": f"{base['id']}-{index + 1}"} for index in range(count)
    ]


def _payload_for_mode(
    orders: dict[str, Any],
    order_id: str,
    mode: PackingMode,
    target: str | None,
    containers: int,
) -> dict[str, Any]:
    """Una entrada por modo: mismos ítems y contenedores, sort propio del modo."""

    payload = convert_order_to_pack_input(
        orders,
        order_id,
        problem_type=ProblemType.PALLETIZATION,
        parameters={"sort_strategy": default_sort_for_mode(mode)},
        request_id=f"holdout-offline-online-{order_id}-{mode.value}",
        target_override=target,
        packing_mode=mode,
    )
    replicate_containers(payload, containers)
    return payload


def _to_problem(payload: dict[str, Any], engine: HoldoutEngine) -> PackingProblem:
    parameters: dict[str, Any] = {
        "sort_strategy": default_sort_for_mode(engine.mode),
        **dict(engine.parameters),
    }
    body = {
        "problem_type": engine.problem_type.value,
        "request_id": payload.get("request_id"),
        "containers": payload["containers"],
        "items": payload["items"],
        "constraints": _constraints_for(engine.problem_type).model_dump(),
        "objective": payload.get("objective", "maximize_volume_utilization"),
        "packing_mode": engine.mode.value,
        "parameters": parameters,
    }
    data = PackAlgorithmInput.model_validate(body)
    return data.to_pack_request(engine.algorithm, [engine.problem_type]).to_problem()


def load_envelope(problem: PackingProblem, solution: Any) -> dict[str, float]:
    """Altura de carga alcanzada y cubo medido dentro de esa altura.

    ``volume_utilization`` divide por el contenedor completo, así que cuando el
    pedido entero cabe todos los motores empatan en la misma cifra. La altura
    alcanzada y el cubo dentro del envolvente ocupado sí separan una carga
    compacta de una dispersa. Ambas cifras se derivan de campos que ya existen
    en la solución; no son métricas nuevas del contrato.
    """

    tops: dict[str, float] = {}
    for packed in solution.packed_items:
        top = packed.position.z + packed.orientation.height
        tops[packed.container_id] = max(tops.get(packed.container_id, 0.0), top)
    if not tops:
        return {"load_height_mm": 0.0, "envelope_utilization": 0.0}

    footprints = {c.id: c.length * c.width for c in problem.containers}
    envelope = sum(footprints.get(cid, 0.0) * top for cid, top in tops.items())
    packed_volume = sum(
        p.orientation.length * p.orientation.width * p.orientation.height
        for p in solution.packed_items
    )
    return {
        "load_height_mm": round(max(tops.values()), 3),
        "envelope_utilization": (
            round(packed_volume / envelope, 6) if envelope > 0 else 0.0
        ),
    }


def _engine_details(engine: HoldoutEngine, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "packing_mode": engine.mode.value,
        "problem_type": engine.problem_type.value,
        "algorithm": engine.algorithm,
        "variant": engine.variant,
        "lookahead_p": engine.parameters.get("lookahead_p"),
        "select_s": engine.parameters.get("select_s"),
        "model_path": engine.parameters.get("model_path"),
        **extra,
    }


def _error_result(
    engine: HoldoutEngine,
    message: str,
) -> BenchmarkEngineResult:
    return BenchmarkEngineResult(
        engine=engine.label,
        status="error",
        is_valid=False,
        metrics=Metrics(),
        error=message,
        details=_engine_details(engine, {}),
    )


def _run_one(
    registry: AlgorithmRegistry,
    payload: dict[str, Any],
    engine: HoldoutEngine,
) -> BenchmarkEngineResult:
    if not registry.has(engine.algorithm):
        return _error_result(engine, f"Algoritmo no encontrado: {engine.algorithm}")
    meta = registry.get_metadata(engine.algorithm)
    if engine.problem_type not in meta.problem_types:
        return _error_result(
            engine,
            f"Motor '{engine.algorithm}' no es compatible con "
            f"problem_type={engine.problem_type.value}",
        )

    problem = _to_problem(payload, engine)
    try:
        solution = registry.execute(engine.algorithm, problem)
    except (PackingError, Exception) as exc:  # noqa: BLE001
        logger.warning("holdout engine=%s error=%s", engine.label, exc)
        return _error_result(engine, str(exc))

    is_valid = bool(solution.validation_report and solution.validation_report.is_valid)
    used = solution.execution_metadata.parameters or {}
    return BenchmarkEngineResult(
        engine=engine.label,
        status=solution.status.value,
        is_valid=is_valid,
        metrics=solution.metrics,
        validation_report=solution.validation_report,
        solution=solution,
        details=_engine_details(
            engine,
            {
                "sort_strategy": used.get("sort_strategy"),
                **load_envelope(problem, solution),
            },
        ),
    )


def run_holdout_order(
    orders: dict[str, Any],
    order_id: str,
    *,
    engines: Sequence[HoldoutEngine] = HOLDOUT_ENGINES,
    target: str | None = None,
    containers: int = 1,
    registry: AlgorithmRegistry | None = None,
) -> BenchmarkResponse:
    """Ejecuta todos los motores sobre un pedido del holdout.

    ``target=None`` respeta el destino que declara el pedido en BED-BPP
    (euro-pallet o rollcontainer); dentro de un pedido todos los motores
    reciben los mismos contenedores.

    ``containers`` replica ese destino tal cual: con 2, cada motor decide si
    abre el segundo pallet o no, y el ranking lo penaliza.
    """

    registry = registry or get_default_registry()
    payloads = {
        mode: _payload_for_mode(orders, order_id, mode, target, containers)
        for mode in {engine.mode for engine in engines}
    }
    results = [_run_one(registry, payloads[e.mode], e) for e in engines]
    multi = containers > 1
    ordered = sorted(results, key=_multi_ranking_key if multi else _ranking_key)
    ranking = [r.engine for r in ordered]

    reference = payloads[engines[0].mode]
    details_src = reference.get("details") or {}
    container = reference["containers"][0]
    resolved_target = str(details_src.get("target", target or "euro-pallet"))
    expected = TARGET_SIZES_MM.get(resolved_target.strip().lower())
    return BenchmarkResponse(
        request_id=f"holdout-offline-online-{order_id}",
        results=results,
        ranking=ranking,
        ranking_explanation=RANKING_HOLDOUT_MULTI if multi else RANKING_HOLDOUT,
        details={
            "benchmark_group": (
                "HOLDOUT_OFFLINE_VS_ONLINE_MULTI"
                if multi
                else "HOLDOUT_OFFLINE_VS_ONLINE"
            ),
            "order_id": order_id,
            "is_product_holdout": order_id in PRODUCT_HOLDOUT_ORDER_IDS,
            "n_items": len(reference["items"]),
            "target": resolved_target,
            "units": details_src.get("units", "mm_kg"),
            "containers_available": len(reference["containers"]),
            "container_id": container.get("id"),
            "container_size": [
                container.get("length"),
                container.get("width"),
                container.get("height"),
            ],
            "expected_target_size": list(expected) if expected else None,
            "engines_total": len(results),
            "engines_valid": sum(1 for r in results if r.is_valid),
            "engines_error": sum(1 for r in results if r.status == "error"),
            "best_engine": ranking[0] if ranking else None,
        },
    )


def run_holdout_offline_online(
    orders: dict[str, Any],
    *,
    order_ids: Sequence[str] | None = None,
    engines: Sequence[HoldoutEngine] = HOLDOUT_ENGINES,
    target: str | None = None,
    containers: int = 1,
    registry: AlgorithmRegistry | None = None,
) -> list[BenchmarkResponse]:
    """Recorre el holdout completo y devuelve una respuesta por pedido."""

    registry = registry or get_default_registry()
    ids = tuple(order_ids) if order_ids else HOLDOUT_ORDER_IDS
    return [
        run_holdout_order(
            orders,
            order_id,
            engines=engines,
            target=target,
            containers=containers,
            registry=registry,
        )
        for order_id in ids
    ]


def summarize_holdout(responses: Sequence[BenchmarkResponse]) -> dict[str, Any]:
    """Agrega por motor: validez, cubo medio, ítems fuera, tiempo y victorias."""

    per_engine: dict[str, dict[str, Any]] = {}
    for response in responses:
        winner = response.details.get("best_engine")
        for result in response.results:
            row = per_engine.setdefault(
                result.engine,
                {
                    "engine": result.engine,
                    "packing_mode": result.details.get("packing_mode"),
                    "orders": 0,
                    "orders_valid": 0,
                    "orders_error": 0,
                    "wins": 0,
                    "items_packed": 0,
                    "items_unpacked": 0,
                    "containers_used": 0,
                    "_utilization": 0.0,
                    "_seconds": 0.0,
                    "_load_height": 0.0,
                    "_envelope": 0.0,
                },
            )
            row["orders"] += 1
            row["orders_valid"] += int(result.is_valid)
            row["orders_error"] += int(result.status == "error")
            row["wins"] += int(result.engine == winner)
            row["items_packed"] += result.metrics.items_packed
            row["items_unpacked"] += result.metrics.items_unpacked
            row["containers_used"] += result.metrics.containers_used
            row["_utilization"] += result.metrics.volume_utilization
            row["_seconds"] += result.metrics.execution_time_seconds
            row["_load_height"] += result.details.get("load_height_mm") or 0.0
            row["_envelope"] += result.details.get("envelope_utilization") or 0.0

    rows = []
    for row in per_engine.values():
        n = max(1, row["orders"])
        rows.append(
            {
                **{k: v for k, v in row.items() if not k.startswith("_")},
                "mean_volume_utilization": row["_utilization"] / n,
                "mean_execution_time_seconds": row["_seconds"] / n,
                "mean_load_height_mm": row["_load_height"] / n,
                "mean_envelope_utilization": row["_envelope"] / n,
            }
        )
    multi = any(
        (r.details.get("containers_available") or 1) > 1 for r in responses
    )
    if multi:
        rows.sort(
            key=lambda r: (
                -r["orders_valid"],
                r["items_unpacked"],
                r["containers_used"],
                -r["mean_volume_utilization"],
                r["mean_execution_time_seconds"],
                r["engine"],
            )
        )
    else:
        rows.sort(
            key=lambda r: (
                -r["orders_valid"],
                -r["mean_volume_utilization"],
                r["items_unpacked"],
                -r["mean_envelope_utilization"],
                r["mean_execution_time_seconds"],
                r["engine"],
            )
        )
    return {
        "benchmark_group": (
            "HOLDOUT_OFFLINE_VS_ONLINE_MULTI"
            if multi
            else "HOLDOUT_OFFLINE_VS_ONLINE"
        ),
        "orders": [r.details.get("order_id") for r in responses],
        "orders_total": len(responses),
        "containers_available": max(
            (r.details.get("containers_available") or 1) for r in responses
        )
        if responses
        else 1,
        "ranking_explanation": RANKING_HOLDOUT_MULTI if multi else RANKING_HOLDOUT,
        "engines": rows,
    }
