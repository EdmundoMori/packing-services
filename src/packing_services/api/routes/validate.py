"""Endpoint de validación de soluciones de packing."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import ValidateRequest
from ...schemas.responses import ValidateResponse
from ...services.validation_service import ValidationService

router = APIRouter(tags=["validate"])
_service = ValidationService()


@router.post("/validate", response_model=ValidateResponse)
def validate(request: ValidateRequest) -> ValidateResponse:
    """Valida una solución de packing y recalcula sus métricas."""

    return _service.validate(request)
