"""Endpoint del Palletization Service."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import PalletizationRequest
from ...schemas.responses import PackResponse
from ...services.palletization_service import PalletizationService

router = APIRouter(tags=["palletization"])
_service = PalletizationService()


@router.post("/pack/palletization", response_model=PackResponse)
def pack_palletization(request: PalletizationRequest) -> PackResponse:
    """Empaqueta ítems en uno o varios pallets (layer-based por defecto)."""

    return _service.palletize(request)
