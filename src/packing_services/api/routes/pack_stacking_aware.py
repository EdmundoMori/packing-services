"""Endpoint del Stacking-aware Packing Service."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import StackingAwareRequest
from ...schemas.responses import PackResponse
from ...services.stacking_aware_service import StackingAwareService

router = APIRouter(tags=["stacking-aware"])
_service = StackingAwareService()


@router.post("/pack/stacking-aware", response_model=PackResponse)
def pack_stacking_aware(request: StackingAwareRequest) -> PackResponse:
    """Empaqueta ítems respetando soporte y carga máxima soportada."""

    return _service.pack(request)
