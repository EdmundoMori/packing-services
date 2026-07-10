"""Endpoint de salud."""

from __future__ import annotations

from fastapi import APIRouter

from ... import SERVICE_VERSION
from ...schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service_version=SERVICE_VERSION)
