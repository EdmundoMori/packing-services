"""Experimento conjunto: un contenedor, varios tipos de servicio, misma secuencia.

Compara ``3D_BPP``, ``SINGLE_CONTAINER_LOADING``, ``PALLETIZATION`` y
``STACKING_AWARE`` sobre el mismo pedido BED-BPP forzado a un euro-pallet,
con ``sort_strategy=input_order`` (sin reordenar la llegada). Todas las
ejecuciones pasan por ``build_solution``: mismo validador y mismas métricas.
"""

from __future__ import annotations

from typing import Any

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..datasets.bed_bpp import (
    TARGET_SIZES_MM,
    convert_order_to_pack_input,
    smallest_order_id,
)
from ..domain.enums import ProblemType, SortStrategy
from ..domain.models import ConstraintFlags, Metrics, PackingProblem
from ..schemas.requests import PackAlgorithmInput
from ..schemas.responses import BenchmarkEngineResult, BenchmarkResponse
from ..utils.errors import PackingError
from ..utils.logging import get_logger

logger = get_logger(__name__)

JOINT_PROBLEM_TYPES: tuple[ProblemType, ...] = (
    ProblemType.THREE_D_BPP,
    ProblemType.SINGLE_CONTAINER_LOADING,
    ProblemType.PALLETIZATION,
    ProblemType.STACKING_AWARE,
)

# Motores constructivos comparables por tipo. Un mismo algoritmo puede aparecer
# en dos tipos si el registro lo declara compatible (p. ej. BFD en 3D-BPP y SCL).
JOINT_ENGINES: tuple[tuple[ProblemType, str], ...] = (
    (ProblemType.THREE_D_BPP, "heuristic_3d_bpp_v1"),
    (ProblemType.THREE_D_BPP, "first_fit_decreasing_3d"),
    (ProblemType.THREE_D_BPP, "best_fit_decreasing_3d"),
    (ProblemType.THREE_D_BPP, "extreme_points_3d"),
    (ProblemType.THREE_D_BPP, "maximal_spaces_3d"),
    (ProblemType.SINGLE_CONTAINER_LOADING, "single_container_constructive"),
    (ProblemType.SINGLE_CONTAINER_LOADING, "best_fit_decreasing_3d"),
    (ProblemType.SINGLE_CONTAINER_LOADING, "first_fit_decreasing_3d"),
    (ProblemType.PALLETIZATION, "layer_based_palletization"),
    (ProblemType.PALLETIZATION, "stack_based_palletization"),
    (ProblemType.STACKING_AWARE, "stacking_aware_constructive"),
    (ProblemType.STACKING_AWARE, "stack_based_palletization"),
)

DEFAULT_TARGET = "euro-pallet"
DEFAULT_SORT = SortStrategy.INPUT_ORDER.value

RANKING_JOINT = (
    "Ranking conjunto (un contenedor, secuencia de llegada): "
    "(1) soluciones válidas; (2) mayor volume_utilization; "
    "(3) menor items_unpacked; (4) menor tiempo. "
    "Mismo validador geométrico y mismas métricas en todos los tipos."
)


def engine_label(problem_type: ProblemType | str, algorithm_name: str) -> str:
    pt = problem_type.value if isinstance(problem_type, ProblemType) else problem_type
    return f"{pt}/{algorithm_name}"


def _ranking_key(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    return (
        0 if result.is_valid else 1,
        -m.volume_utilization,
        m.items_unpacked,
        m.execution_time_seconds,
        result.engine,
    )


def _constraints_for(problem_type: ProblemType) -> ConstraintFlags:
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


def _parameters_for(algorithm_name: str, sort_strategy: str) -> dict[str, Any]:
    params: dict[str, Any] = {"sort_strategy": sort_strategy}
    if algorithm_name in {"stack_based_palletization", "stacking_aware_constructive"}:
        params["min_support_ratio"] = 0.6
    return params


def build_joint_instance(
    orders: dict[str, Any],
    *,
    order_id: str | None = None,
    target: str = DEFAULT_TARGET,
    sort_strategy: str = DEFAULT_SORT,
    request_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Convierte un pedido BED-BPP a un único contenedor (euro-pallet por defecto)."""

    resolved_id = order_id or smallest_order_id(orders)
    payload = convert_order_to_pack_input(
        orders,
        resolved_id,
        problem_type=ProblemType.THREE_D_BPP,
        parameters={"sort_strategy": sort_strategy},
        request_id=request_id or f"joint-single-container-{resolved_id}",
        target_override=target,
    )
    return resolved_id, payload


def _to_problem(
    payload: dict[str, Any],
    problem_type: ProblemType,
    algorithm_name: str,
    sort_strategy: str,
) -> PackingProblem:
    body = {
        "problem_type": problem_type.value,
        "request_id": payload.get("request_id"),
        "containers": payload["containers"],
        "items": payload["items"],
        "constraints": _constraints_for(problem_type).model_dump(),
        "objective": payload.get("objective", "maximize_volume_utilization"),
        "parameters": _parameters_for(algorithm_name, sort_strategy),
    }
    data = PackAlgorithmInput.model_validate(body)
    return data.to_pack_request(algorithm_name, [problem_type]).to_problem()


def _run_one(
    registry: AlgorithmRegistry,
    payload: dict[str, Any],
    problem_type: ProblemType,
    algorithm_name: str,
    sort_strategy: str,
) -> BenchmarkEngineResult:
    label = engine_label(problem_type, algorithm_name)
    if not registry.has(algorithm_name):
        return BenchmarkEngineResult(
            engine=label,
            status="error",
            is_valid=False,
            metrics=Metrics(),
            error=f"Algoritmo no encontrado: {algorithm_name}",
            details={"problem_type": problem_type.value, "algorithm": algorithm_name},
        )
    meta = registry.get_metadata(algorithm_name)
    if problem_type not in meta.problem_types:
        return BenchmarkEngineResult(
            engine=label,
            status="error",
            is_valid=False,
            metrics=Metrics(),
            error=(
                f"Motor '{algorithm_name}' no es compatible con "
                f"problem_type={problem_type.value}"
            ),
            details={"problem_type": problem_type.value, "algorithm": algorithm_name},
        )

    problem = _to_problem(payload, problem_type, algorithm_name, sort_strategy)
    try:
        solution = registry.execute(algorithm_name, problem)
    except (PackingError, Exception) as exc:  # noqa: BLE001
        logger.warning("joint engine=%s error=%s", label, exc)
        return BenchmarkEngineResult(
            engine=label,
            status="error",
            is_valid=False,
            metrics=Metrics(),
            error=str(exc),
            details={"problem_type": problem_type.value, "algorithm": algorithm_name},
        )

    is_valid = bool(solution.validation_report and solution.validation_report.is_valid)
    used_sort = (solution.execution_metadata.parameters or {}).get("sort_strategy")
    return BenchmarkEngineResult(
        engine=label,
        status=solution.status.value,
        is_valid=is_valid,
        metrics=solution.metrics,
        validation_report=solution.validation_report,
        solution=solution,
        details={
            "problem_type": problem_type.value,
            "algorithm": algorithm_name,
            "sort_strategy": used_sort,
        },
    )


def run_joint_single_container(
    orders: dict[str, Any],
    *,
    order_id: str | None = None,
    target: str = DEFAULT_TARGET,
    sort_strategy: str = DEFAULT_SORT,
    request_id: str | None = None,
    registry: AlgorithmRegistry | None = None,
) -> BenchmarkResponse:
    """Ejecuta el experimento conjunto sobre un pedido BED-BPP."""

    registry = registry or get_default_registry()
    resolved_id, payload = build_joint_instance(
        orders,
        order_id=order_id,
        target=target,
        sort_strategy=sort_strategy,
        request_id=request_id,
    )
    details_src = payload.pop("details", {}) or {}
    results = [
        _run_one(registry, payload, pt, name, sort_strategy)
        for pt, name in JOINT_ENGINES
    ]
    ordered = sorted(results, key=_ranking_key)
    ranking = [r.engine for r in ordered]
    container = payload["containers"][0]
    expected = TARGET_SIZES_MM.get(target.strip().lower())
    return BenchmarkResponse(
        request_id=payload.get("request_id"),
        results=results,
        ranking=ranking,
        ranking_explanation=RANKING_JOINT,
        details={
            "benchmark_group": "JOINT_SINGLE_CONTAINER",
            "benchmark_profile": "input_order",
            "problem_types": [p.value for p in JOINT_PROBLEM_TYPES],
            "order_id": resolved_id,
            "n_items": len(payload["items"]),
            "target": details_src.get("target", target),
            "units": details_src.get("units", "mm_kg"),
            "sort_strategy": sort_strategy,
            "container_id": container.get("id"),
            "container_size": [
                container.get("length"),
                container.get("width"),
                container.get("height"),
            ],
            "expected_euro_pallet": list(expected) if expected else None,
            "engines_total": len(results),
            "engines_valid": sum(1 for r in results if r.is_valid),
            "engines_error": sum(1 for r in results if r.status == "error"),
            "best_engine": ranking[0] if ranking else None,
        },
    )
