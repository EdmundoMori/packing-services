"""Packing Benchmark / Comparison Service.

Ejecuta varios algoritmos/motores sobre la misma instancia, valida cada
resultado y produce un ranking comparable con explicación textual. Es un
servicio propio (no existe una herramienta madura equivalente según el análisis
de repositorios).
"""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.models import Metrics
from ..schemas.requests import BenchmarkRequest
from ..schemas.responses import (
    BenchmarkEngineResult,
    BenchmarkResponse,
)
from ..utils.errors import PackingError
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Ranking: primero soluciones válidas, luego mayor utilización, menos ítems sin
# empacar, menos contenedores usados y por último menor tiempo de ejecución.
RANKING_EXPLANATION = (
    "Ranking: (1) soluciones válidas antes que inválidas; "
    "(2) mayor volume_utilization; (3) menor items_unpacked; "
    "(4) menor containers_used; (5) menor execution_time_seconds."
)


def _ranking_key(result: BenchmarkEngineResult) -> tuple:
    m = result.metrics
    return (
        0 if result.is_valid else 1,
        -m.volume_utilization,
        m.items_unpacked,
        m.containers_used,
        m.execution_time_seconds,
    )


class BenchmarkService:
    """Compara varios motores sobre una misma instancia."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def benchmark(self, request: BenchmarkRequest) -> BenchmarkResponse:
        results: list[BenchmarkEngineResult] = []

        for engine in request.engines:
            results.append(self._run_engine(request, engine))

        ordered = sorted(results, key=_ranking_key)
        ranking = [r.engine for r in ordered]

        return BenchmarkResponse(
            request_id=request.request_id,
            results=results,
            ranking=ranking,
            ranking_explanation=RANKING_EXPLANATION,
            details={
                "engines_total": len(results),
                "engines_valid": sum(1 for r in results if r.is_valid),
                "best_engine": ranking[0] if ranking else None,
            },
        )

    def _run_engine(self, request: BenchmarkRequest, engine) -> BenchmarkEngineResult:
        problem = request.to_problem(engine)
        try:
            solution = self.registry.execute(engine.name, problem)
        except (PackingError, Exception) as exc:  # noqa: BLE001
            # Un motor que falla no debe romper el benchmark completo.
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
