"""Stacking-aware Packing Service."""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.models import PackingSolution
from ..schemas.requests import StackingAwareRequest
from ..utils.logging import get_logger

logger = get_logger(__name__)


class StackingAwareService:
    """Orquesta el empaquetado stacking-aware."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def pack(self, request: StackingAwareRequest) -> PackingSolution:
        problem = request.to_problem()
        logger.info(
            "stacking-aware request_id=%s algorithm=%s items=%d containers=%d",
            problem.request_id,
            problem.algorithm.name,
            len(problem.items),
            len(problem.containers),
        )
        return self.registry.execute(problem.algorithm.name, problem)
