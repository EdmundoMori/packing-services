"""Packing Benchmark / Comparison Service.

Ejecuta varios algoritmos/motores sobre la misma instancia, valida cada
resultado y produce un ranking comparable con explicación textual. Soporta
benchmarks por tipo de problema y perfiles estándar de motores.
"""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..benchmark.profiles import DEFAULT_PROFILE_BY_PROBLEM
from ..domain.enums import ProblemType
from ..domain.models import Metrics
from ..schemas.requests import BenchmarkRequest
from ..schemas.responses import (
    BenchmarkEngineResult,
    BenchmarkResponse,
)
from ..services.cartonization_service import CartonizationService
from ..services.container_loading_service import ContainerLoadingService
from ..utils.errors import PackingError
from ..utils.logging import get_logger

logger = get_logger(__name__)

RANKING_3D_BPP = (
    "Ranking 3D-BPP: (1) soluciones válidas; (2) mayor volume_utilization; "
    "(3) menor items_unpacked; (4) menor containers_used; (5) menor tiempo."
)
RANKING_SINGLE_CONTAINER = (
    "Ranking Single Container Loading: (1) válidas; (2) mayor volume_utilization; "
    "(3) menor items_unpacked; (4) menor tiempo."
)
RANKING_CONTAINER_LOADING = (
    "Ranking Container Loading: (1) válidas; (2) menor items_unpacked; "
    "(3) mayor volume_utilization; (4) menor tiempo."
)
RANKING_CARTONIZATION = (
    "Ranking Cartonization: (1) válidas; (2) todos los ítems empacados; "
    "(3) mayor volume_utilization; (4) menor tiempo."
)


def _ranking_key_packing(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    return (
        0 if result.is_valid else 1,
        -m.volume_utilization,
        m.items_unpacked,
        m.containers_used,
        m.execution_time_seconds,
    )


def _ranking_key_container_loading(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    return (
        0 if result.is_valid else 1,
        m.items_unpacked,
        -m.volume_utilization,
        m.execution_time_seconds,
    )


def _ranking_key_cartonization(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    fits_all = 0 if m.items_unpacked == 0 else 1
    return (
        0 if result.is_valid else 1,
        fits_all,
        -m.volume_utilization,
        m.execution_time_seconds,
    )


class BenchmarkService:
    """Compara varios motores sobre una misma instancia."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._cartonization = CartonizationService(self.registry)
        self._container_loading = ContainerLoadingService(self.registry)

    def benchmark(self, request: BenchmarkRequest) -> BenchmarkResponse:
        if request.problem_type == ProblemType.CARTONIZATION:
            return self._benchmark_cartonization(request)
        if request.problem_type == ProblemType.CONTAINER_LOADING:
            return self._benchmark_container_loading(request)
        if request.problem_type == ProblemType.SINGLE_CONTAINER_LOADING:
            return self._benchmark_single_container(request)
        return self._benchmark_packing(request)

    def _benchmark_packing(self, request: BenchmarkRequest) -> BenchmarkResponse:
        results = [self._run_engine(request, e) for e in request.engines]
        return self._build_response(
            request,
            results,
            _ranking_key_packing,
            RANKING_3D_BPP,
            benchmark_group="3D_BPP",
        )

    def _benchmark_single_container(
        self, request: BenchmarkRequest
    ) -> BenchmarkResponse:
        results = [self._run_engine(request, e) for e in request.engines]
        return self._build_response(
            request,
            results,
            _ranking_key_packing,
            RANKING_SINGLE_CONTAINER,
            benchmark_group="SINGLE_CONTAINER_LOADING",
        )

    def _benchmark_container_loading(
        self, request: BenchmarkRequest
    ) -> BenchmarkResponse:
        results = [self._run_engine(request, e) for e in request.engines]
        return self._build_response(
            request,
            results,
            _ranking_key_container_loading,
            RANKING_CONTAINER_LOADING,
            benchmark_group="CONTAINER_LOADING",
        )

    def _benchmark_cartonization(self, request: BenchmarkRequest) -> BenchmarkResponse:
        results = [self._run_engine(request, e) for e in request.engines]
        return self._build_response(
            request,
            results,
            _ranking_key_cartonization,
            RANKING_CARTONIZATION,
            benchmark_group="CARTONIZATION",
        )

    def _build_response(
        self,
        request: BenchmarkRequest,
        results: list[BenchmarkEngineResult],
        key_fn,
        explanation: str,
        *,
        benchmark_group: str,
    ) -> BenchmarkResponse:
        ordered = sorted(results, key=key_fn)
        ranking = [r.engine for r in ordered]
        profile = request.profile or DEFAULT_PROFILE_BY_PROBLEM.get(
            request.problem_type.value
        )
        return BenchmarkResponse(
            request_id=request.request_id,
            results=results,
            ranking=ranking,
            ranking_explanation=explanation,
            details={
                "benchmark_group": benchmark_group,
                "benchmark_profile": profile,
                "problem_type": request.problem_type.value,
                "engines_total": len(results),
                "engines_valid": sum(1 for r in results if r.is_valid),
                "engines_error": sum(1 for r in results if r.status == "error"),
                "best_engine": ranking[0] if ranking else None,
            },
        )

    def _engine_compatible(self, engine_name: str, problem_type: ProblemType) -> bool:
        if not self.registry.has(engine_name):
            return False
        meta = self.registry.get_metadata(engine_name)
        return problem_type in meta.problem_types

    def _run_engine(
        self, request: BenchmarkRequest, engine
    ) -> BenchmarkEngineResult:
        if not self._engine_compatible(engine.name, request.problem_type):
            return BenchmarkEngineResult(
                engine=engine.name,
                status="error",
                is_valid=False,
                metrics=Metrics(),
                error=(
                    f"Motor '{engine.name}' no es compatible con "
                    f"problem_type={request.problem_type.value}"
                ),
            )
        if request.problem_type == ProblemType.CARTONIZATION:
            return self._run_cartonization_engine(request, engine)
        if request.problem_type == ProblemType.CONTAINER_LOADING:
            return self._run_container_loading_engine(request, engine)
        return self._run_packing_engine(request, engine)

    def _run_packing_engine(
        self, request: BenchmarkRequest, engine
    ) -> BenchmarkEngineResult:
        problem = request.to_problem(engine)
        try:
            solution = self.registry.execute(engine.name, problem)
        except (PackingError, Exception) as exc:  # noqa: BLE001
            logger.warning("benchmark engine=%s error=%s", engine.name, exc)
            return BenchmarkEngineResult(
                engine=engine.name,
                status="error",
                is_valid=False,
                metrics=Metrics(),
                error=str(exc),
            )

        is_valid = bool(
            solution.validation_report and solution.validation_report.is_valid
        )
        return BenchmarkEngineResult(
            engine=engine.name,
            status=solution.status.value,
            is_valid=is_valid,
            metrics=solution.metrics,
            validation_report=solution.validation_report,
            solution=solution,
        )

    def _run_container_loading_engine(
        self, request: BenchmarkRequest, engine
    ) -> BenchmarkEngineResult:
        try:
            solution = self._container_loading.load(
                request.to_container_loading_request(engine)
            )
        except (PackingError, Exception) as exc:  # noqa: BLE001
            logger.warning("benchmark CL engine=%s error=%s", engine.name, exc)
            return BenchmarkEngineResult(
                engine=engine.name,
                status="error",
                is_valid=False,
                metrics=Metrics(),
                error=str(exc),
            )

        is_valid = bool(
            solution.validation_report and solution.validation_report.is_valid
        )
        return BenchmarkEngineResult(
            engine=engine.name,
            status=solution.status.value,
            is_valid=is_valid,
            metrics=solution.metrics,
            validation_report=solution.validation_report,
            solution=solution,
        )

    def _run_cartonization_engine(
        self, request: BenchmarkRequest, engine
    ) -> BenchmarkEngineResult:
        try:
            response = self._cartonization.cartonize(
                request.to_cartonization_request(engine)
            )
            solution = response.solution
        except (PackingError, Exception) as exc:  # noqa: BLE001
            logger.warning("benchmark carton engine=%s error=%s", engine.name, exc)
            return BenchmarkEngineResult(
                engine=engine.name,
                status="error",
                is_valid=False,
                metrics=Metrics(),
                error=str(exc),
            )

        is_valid = bool(
            solution.validation_report and solution.validation_report.is_valid
        )
        return BenchmarkEngineResult(
            engine=engine.name,
            status=response.status,
            is_valid=is_valid,
            metrics=solution.metrics,
            validation_report=solution.validation_report,
            solution=solution,
            details={
                "selected_box_id": response.selected_box_id,
                "evaluated_boxes": response.evaluated_boxes,
            },
        )

    def list_profiles(self, problem_type: ProblemType | None = None):
        from ..benchmark.profiles import list_profiles

        return list_profiles(problem_type)
