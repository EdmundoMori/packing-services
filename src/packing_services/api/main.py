"""Punto de entrada de la API local (FastAPI).

Levantar con::

    uvicorn packing_services.api.main:app --reload

Mapea los errores de dominio a códigos HTTP claros y monta los routers mínimos
descritos en los requisitos.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .. import SERVICE_VERSION
from ..utils.errors import (
    AdapterUnavailableError,
    AlgorithmNotExecutableError,
    AlgorithmNotFoundError,
    ExecutionError,
    InvalidInputError,
)
from ..utils.logging import configure_logging
from .routes import (
    algorithms,
    benchmark,
    health,
    metadata,
    pack_3d_bpp,
    pack_cartonization,
    pack_container_loading,
    services,
    validate,
)

configure_logging()

app = FastAPI(
    title="packing-services",
    version=SERVICE_VERSION,
    description=(
        "Servicios modulares de Cutting and Packing (3D-BPP offline, validación "
        "y benchmark) con catálogo homogéneo de algoritmos."
    ),
)


def _error_response(status_code: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": error_type, "message": message}},
    )


@app.exception_handler(AlgorithmNotFoundError)
async def _handle_not_found(_: Request, exc: AlgorithmNotFoundError) -> JSONResponse:
    return _error_response(404, "AlgorithmNotFound", str(exc))


@app.exception_handler(AlgorithmNotExecutableError)
async def _handle_not_executable(
    _: Request, exc: AlgorithmNotExecutableError
) -> JSONResponse:
    return _error_response(400, "AlgorithmNotExecutable", str(exc))


@app.exception_handler(AdapterUnavailableError)
async def _handle_adapter_unavailable(
    _: Request, exc: AdapterUnavailableError
) -> JSONResponse:
    return _error_response(503, "AdapterUnavailable", str(exc))


@app.exception_handler(InvalidInputError)
async def _handle_invalid_input(_: Request, exc: InvalidInputError) -> JSONResponse:
    return _error_response(422, "InvalidInput", str(exc))


@app.exception_handler(ExecutionError)
async def _handle_execution_error(_: Request, exc: ExecutionError) -> JSONResponse:
    return _error_response(500, "ExecutionError", str(exc))


app.include_router(health.router)
app.include_router(metadata.router, prefix="/api/v1")
app.include_router(services.router, prefix="/api/v1")
app.include_router(algorithms.router, prefix="/api/v1")
app.include_router(pack_3d_bpp.router, prefix="/api/v1")
app.include_router(pack_container_loading.router, prefix="/api/v1")
app.include_router(pack_cartonization.router, prefix="/api/v1")
app.include_router(validate.router, prefix="/api/v1")
app.include_router(benchmark.router, prefix="/api/v1")
