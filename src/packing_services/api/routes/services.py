"""Endpoint del catálogo de servicios para espacio de datos."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.responses import DataspaceCatalogResponse
from ...services.dataspace_service import DataspaceService

router = APIRouter(tags=["dataspace"])
_service = DataspaceService()


@router.get("/services", response_model=DataspaceCatalogResponse)
def list_services() -> DataspaceCatalogResponse:
    """Descriptores de servicios listos para publicación en un espacio de datos."""

    return _service.catalog()
