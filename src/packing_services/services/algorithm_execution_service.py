"""Ejecución de un algoritmo concreto vía endpoint dedicado (nombre en la URL)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import ProblemType
from ..domain.models import PackingSolution
from ..schemas.requests import CartonizationAlgorithmInput, PackAlgorithmInput
from ..schemas.responses import CartonizationResponse
from ..utils.errors import (
    AlgorithmNotExecutableError,
    AlgorithmNotFoundError,
    InvalidInputError,
)
from ..utils.logging import get_logger
from .cartonization_service import CartonizationService
from .packing_service import PackingService

logger = get_logger(__name__)


class AlgorithmExecutionService:
    """Ejecuta un algoritmo identificado por nombre en el path de la API."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._packing = PackingService(self.registry)
        self._cartonization = CartonizationService(self.registry)

    @staticmethod
    def _is_cartonization_only(problem_types: list[ProblemType]) -> bool:
        return problem_types == [ProblemType.CARTONIZATION]

    def _pack_compatible_types(self, problem_types: list[ProblemType]) -> list[ProblemType]:
        return [pt for pt in problem_types if pt != ProblemType.CARTONIZATION]

    def execute(
        self, algorithm_name: str, payload: dict[str, Any]
    ) -> PackingSolution | CartonizationResponse:
        if not self.registry.has(algorithm_name):
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {algorithm_name}")
        if not self.registry.is_executable(algorithm_name):
            status = self.registry.get_metadata(algorithm_name).status.value
            raise AlgorithmNotExecutableError(
                f"El algoritmo '{algorithm_name}' no es ejecutable en esta versión "
                f"(estado: {status})."
            )

        meta = self.registry.get_metadata(algorithm_name)
        if self._is_cartonization_only(meta.problem_types):
            return self._execute_cartonization(algorithm_name, payload)

        allowed = self._pack_compatible_types(meta.problem_types)
        if not allowed:
            raise InvalidInputError(
                f"El algoritmo '{algorithm_name}' no tiene tipos de problema ejecutables."
            )
        return self._execute_pack(algorithm_name, payload, allowed)

    def _execute_pack(
        self,
        algorithm_name: str,
        payload: dict[str, Any],
        allowed: list[ProblemType],
    ) -> PackingSolution:
        try:
            data = PackAlgorithmInput.model_validate(payload)
        except ValidationError as exc:
            raise InvalidInputError(str(exc)) from exc

        try:
            pack_request = data.to_pack_request(algorithm_name, allowed)
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc

        logger.info(
            "algorithm-execute name=%s problem_type=%s request_id=%s",
            algorithm_name,
            pack_request.problem_type.value,
            pack_request.request_id,
        )
        return self._packing.pack(pack_request)

    def _execute_cartonization(
        self, algorithm_name: str, payload: dict[str, Any]
    ) -> CartonizationResponse:
        try:
            data = CartonizationAlgorithmInput.model_validate(payload)
        except ValidationError as exc:
            raise InvalidInputError(str(exc)) from exc

        logger.info(
            "algorithm-execute name=%s problem_type=CARTONIZATION request_id=%s",
            algorithm_name,
            data.request_id,
        )
        return self._cartonization.cartonize(
            data.to_cartonization_request(algorithm_name)
        )
