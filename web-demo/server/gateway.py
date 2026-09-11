"""Gateway del demo web: sirve la UI y hace proxy a packing-services API.

No modifica la API existente. Expone un único puerto (8080 por defecto) que
reenvía ``/api/v1/*`` y ``/health`` al backend configurado en ``PACKING_API_URL``.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
API_BASE = os.environ.get("PACKING_API_URL", "http://127.0.0.1:8000").rstrip("/")
GATEWAY_PORT = int(os.environ.get("WEB_DEMO_PORT", "8080"))

app = FastAPI(
    title="packing-services Web Demo",
    version="0.1.0",
    description=(
        "Catálogo, execute y benchmark: misma entrada, validador y métricas "
        "en packing_mode=offline y packing_mode=online. No es un espacio de datos."
    ),
)


async def _proxy(request: Request, target_url: str) -> Response:
    """Reenvía la petición al backend de packing-services."""

    body = await request.body()
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in {"host", "content-length", "connection"}
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        upstream = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body if body else None,
            params=request.query_params,
        )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        },
        media_type=upstream.headers.get("content-type"),
    )


@app.get("/demo/health")
async def demo_health() -> JSONResponse:
    """Estado del demo: gateway + API de packing-services."""

    payload: dict = {
        "status": "ok",
        "gateway": "ok",
        "api_base": API_BASE,
        "api_reachable": False,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_BASE}/health")
        payload["api_reachable"] = response.status_code == 200
        if response.status_code == 200:
            payload["api"] = response.json()
        else:
            payload["status"] = "degraded"
            payload["api_error"] = response.text
    except Exception as exc:  # noqa: BLE001 — health debe ser informativo
        payload["status"] = "degraded"
        payload["api_error"] = str(exc)
    status_code = 200 if payload["api_reachable"] else 503
    return JSONResponse(payload, status_code=status_code)


@app.api_route("/health", methods=["GET"])
async def proxy_health(request: Request) -> Response:
    return await _proxy(request, f"{API_BASE}/health")


@app.api_route("/api/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_api(request: Request, full_path: str) -> Response:
    return await _proxy(request, f"{API_BASE}/api/{full_path}")


@app.get("/")
async def index_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/catalog.html")
async def catalog_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "catalog.html")


@app.get("/execute.html")
async def execute_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "execute.html")


@app.get("/benchmark.html")
async def benchmark_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "benchmark.html")


app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)


if __name__ == "__main__":
    main()
