"""Endpoint de ejecución de packing 3D-BPP."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import PackRequest
from ...schemas.responses import PackResponse
from ...services.packing_service import PackingService

router = APIRouter(tags=["pack"])
_service = PackingService()


@router.post("/pack/3d-bpp", response_model=PackResponse)
def pack_3d_bpp(request: PackRequest) -> PackResponse:
    """Ejecuta el algoritmo 3D-BPP indicado en el JSON de entrada."""

    return _service.pack(request)
