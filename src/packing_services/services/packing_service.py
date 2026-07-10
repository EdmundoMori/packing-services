"""Servicio de ejecución de algoritmos de packing (3D-BPP Offline Service)."""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.models import PackingSolution
from ..schemas.requests import PackRequest
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PackingService:
    """Orquesta la ejecución de un algoritmo sobre una instancia normalizada."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def pack(self, request: PackRequest) -> PackingSolution:
        """Ejecuta el algoritmo indicado en el request y devuelve la solución."""

        problem = request.to_problem()
        algorithm_name = problem.algorithm.name
        logger.info(
            "pack request_id=%s algorithm=%s items=%d containers=%d",
            problem.request_id,
            algorithm_name,
            len(problem.items),
            len(problem.containers),
        )
        solution = self.registry.execute(algorithm_name, problem)
        logger.info(
            "pack done request_id=%s status=%s packed=%d unpacked=%d util=%.3f",
            solution.request_id,
            solution.status,
            solution.metrics.items_packed,
            solution.metrics.items_unpacked,
            solution.metrics.volume_utilization,
        )
        return solution
