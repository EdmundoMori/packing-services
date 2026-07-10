"""Endpoint de metadatos del servicio."""

from __future__ import annotations

from fastapi import APIRouter

from ...schemas.responses import ServiceMetadataResponse
from ...services.metadata_service import MetadataService

router = APIRouter(tags=["metadata"])
_service = MetadataService()


@router.get("/metadata", response_model=ServiceMetadataResponse)
def get_metadata() -> ServiceMetadataResponse:
    return _service.get_metadata()
