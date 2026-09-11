"""Endpoint de ejecución por algoritmo (un path por nombre de algoritmo)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body

from ...schemas.responses import AlgorithmExecuteResponse
from ...services.algorithm_execution_service import AlgorithmExecutionService

router = APIRouter(tags=["algorithm-execute"])
_service = AlgorithmExecutionService()


@router.post(
    "/algorithms/{algorithm_name}/execute",
    response_model=AlgorithmExecuteResponse,
    summary="Ejecutar un algoritmo por nombre",
    description=(
        "Ejecuta el algoritmo indicado en la URL. El JSON de entrada está "
        "normalizado por tipo de problema: "
        "**PackAlgorithmInput** (3D_BPP, CONTAINER_LOADING, SINGLE_CONTAINER_LOADING, "
        "PALLETIZATION, STACKING_AWARE) "
        "o **CartonizationAlgorithmInput** (CARTONIZATION). "
        "Campo packing_mode: offline (default) u online. "
        "La salida es siempre **AlgorithmExecuteResponse** con la solución en "
        "``solution`` y metadatos de cartonization opcionales. "
        "No incluye el campo `algorithm` en el body."
    ),
)
def execute_algorithm(
    algorithm_name: str,
    payload: dict[str, Any] = Body(
        ...,
        examples={
            "3d_bpp": {
                "summary": "Pack — 3D Bin Packing",
                "value": {
                    "problem_type": "3D_BPP",
                    "request_id": "run-001",
                    "containers": [
                        {"id": "C1", "length": 120, "width": 80, "height": 100, "max_weight": 1000}
                    ],
                    "items": [
                        {
                            "id": "I1",
                            "length": 40,
                            "width": 40,
                            "height": 40,
                            "weight": 10,
                            "quantity": 4,
                        }
                    ],
                    "constraints": {
                        "non_overlap": True,
                        "containment": True,
                        "allow_rotation": True,
                        "max_weight": True,
                    },
                    "parameters": {"sort_strategy": "volume_desc"},
                },
            },
            "cartonization": {
                "summary": "Cartonization",
                "value": {
                    "request_id": "carton-001",
                    "items": [
                        {"id": "SKU1", "length": 20, "width": 15, "height": 10, "weight": 2, "quantity": 3}
                    ],
                    "boxes": [
                        {"id": "BOX_M", "length": 40, "width": 30, "height": 20, "max_weight": 30}
                    ],
                    "constraints": {
                        "non_overlap": True,
                        "containment": True,
                        "allow_rotation": True,
                        "max_weight": True,
                    },
                    "parameters": {"sort_strategy": "volume_desc"},
                },
            },
        },
    ),
) -> AlgorithmExecuteResponse:
    """Ejecuta el algoritmo ``algorithm_name`` sobre la instancia del body."""

    return _service.execute(algorithm_name, payload)
