"""Palletization Service."""

from __future__ import annotations

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.models import PackingSolution
from ..schemas.requests import PalletizationRequest
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PalletizationService:
    """Orquesta la palletización con un algoritmo del registro."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def palletize(self, request: PalletizationRequest) -> PackingSolution:
        problem = request.to_problem()
        logger.info(
            "palletization request_id=%s algorithm=%s items=%d pallets=%d",
            problem.request_id,
            problem.algorithm.name,
            len(problem.items),
            len(problem.containers),
        )
        return self.registry.execute(problem.algorithm.name, problem)
