"""Endpoint del Cartonization Service."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import CartonizationRequest
from ...schemas.responses import CartonizationResponse
from ...services.cartonization_service import CartonizationService

router = APIRouter(tags=["cartonization"])
_service = CartonizationService()


@router.post("/pack/cartonization", response_model=CartonizationResponse)
def pack_cartonization(request: CartonizationRequest) -> CartonizationResponse:
    """Selecciona la mejor caja del catálogo para un pedido."""

    return _service.cartonize(request)
