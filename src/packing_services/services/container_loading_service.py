"""Container Loading Service.

Carga de mercancía en contenedores/camiones. Reutiliza el registro de algoritmos
(motores locales weight-aware / single-container) y el mismo formato de salida
que el 3D-BPP, de modo que los resultados son comparables por el Benchmark.
"""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.models import PackingSolution
from ..schemas.requests import ContainerLoadingRequest
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ContainerLoadingService:
    """Orquesta la carga de contenedores con un algoritmo del registro."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def load(self, request: ContainerLoadingRequest) -> PackingSolution:
        problem = request.to_problem()
        logger.info(
            "container-loading request_id=%s algorithm=%s items=%d containers=%d",
            problem.request_id,
            problem.algorithm.name,
            len(problem.items),
            len(problem.containers),
        )
        return self.registry.execute(problem.algorithm.name, problem)
