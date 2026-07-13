"""Ejecución de un algoritmo concreto vía endpoint dedicado (nombre en la URL)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import ProblemType
from ..schemas.requests import CartonizationAlgorithmInput, PackAlgorithmInput
from ..schemas.responses import AlgorithmExecuteResponse, CartonizationResponse
from ..utils.errors import (
    AlgorithmNotExecutableError,
    AlgorithmNotFoundError,
    InvalidInputError,
)
from ..utils.logging import get_logger
from .algorithm_input_service import AlgorithmInputService
from .cartonization_service import CartonizationService
from .packing_service import PackingService

logger = get_logger(__name__)


class AlgorithmExecutionService:
    """Ejecuta un algoritmo identificado por nombre en el path de la API."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._input = AlgorithmInputService(self.registry)
        self._packing = PackingService(self.registry)
        self._cartonization = CartonizationService(self.registry)

    def _resolve_branch(self, algorithm_name: str, payload: dict[str, Any]) -> str:
        meta = self.registry.get_metadata(algorithm_name)
        pack_types = self._input.pack_compatible_types(meta)
        has_carton = self._input.supports_cartonization(meta)

        if has_carton and not pack_types:
            return "cartonization"
        if not has_carton:
            return "pack"

        explicit = payload.get("problem_type")
        if explicit == ProblemType.CARTONIZATION.value:
            return "cartonization"
        if explicit in {pt.value for pt in pack_types}:
            return "pack"
        if "boxes" in payload and "containers" not in payload:
            return "cartonization"
        return "pack"

    def execute(self, algorithm_name: str, payload: dict[str, Any]) -> AlgorithmExecuteResponse:
        if not self.registry.has(algorithm_name):
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {algorithm_name}")
        if not self.registry.is_executable(algorithm_name):
            status = self.registry.get_metadata(algorithm_name).status.value
            raise AlgorithmNotExecutableError(
                f"El algoritmo '{algorithm_name}' no es ejecutable en esta versión "
                f"(estado: {status})."
            )

        branch = self._resolve_branch(algorithm_name, payload)
        if branch == "cartonization":
            return self._execute_cartonization(algorithm_name, payload)
        return self._execute_pack(algorithm_name, payload)

    def _execute_pack(
        self,
        algorithm_name: str,
        payload: dict[str, Any],
    ) -> AlgorithmExecuteResponse:
        meta = self.registry.get_metadata(algorithm_name)
        allowed = self._input.pack_compatible_types(meta)
        if not allowed:
            raise InvalidInputError(
                f"El algoritmo '{algorithm_name}' no admite entrada de packing."
            )

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
        solution = self._packing.pack(pack_request)
        return AlgorithmExecuteResponse.from_pack(solution)

    def _execute_cartonization(
        self,
        algorithm_name: str,
        payload: dict[str, Any],
    ) -> AlgorithmExecuteResponse:
        try:
            data = CartonizationAlgorithmInput.model_validate(payload)
        except ValidationError as exc:
            raise InvalidInputError(str(exc)) from exc

        logger.info(
            "algorithm-execute name=%s problem_type=CARTONIZATION request_id=%s",
            algorithm_name,
            data.request_id,
        )
        response = self._cartonization.cartonize(
            data.to_cartonization_request(algorithm_name)
        )
        return AlgorithmExecuteResponse.from_cartonization(response)
