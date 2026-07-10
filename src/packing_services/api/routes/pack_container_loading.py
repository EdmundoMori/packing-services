"""Endpoint del Container Loading Service."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.requests import ContainerLoadingRequest
from ...schemas.responses import PackResponse
from ...services.container_loading_service import ContainerLoadingService

router = APIRouter(tags=["container-loading"])
_service = ContainerLoadingService()


@router.post("/pack/container-loading", response_model=PackResponse)
def pack_container_loading(request: ContainerLoadingRequest) -> PackResponse:
    """Carga ítems en contenedores/camiones (weight-aware por defecto)."""

    return _service.load(request)
