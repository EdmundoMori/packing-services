"""Smoke tests del demo web (gateway + proxy)."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web-demo" / "server"))

from gateway import app  # noqa: E402


@pytest.fixture
def api_server():
    """Levanta la API real en un puerto libre para probar el proxy."""

    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "packing_services.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(40):
        try:
            if httpx.get(f"{url}/health", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("API no arrancó a tiempo")
    yield url
    proc.terminate()
    proc.wait(timeout=5)


def test_gateway_serves_static_pages():
    client = TestClient(app)
    for path in ("/", "/catalog.html", "/execute.html", "/benchmark.html"):
        response = client.get(path)
        assert response.status_code == 200
        assert "packing-services" in response.text
    execute = client.get("/execute.html")
    assert "BED-BPP" in execute.text
    assert 'id="bedbpp-order-select"' in execute.text
    assert 'id="params-form"' in execute.text
    assert 'id="algorithm-input-json"' in execute.text
    assert "mlp_v1_p1s1.pt" in execute.text
    assert "Entrada del algoritmo" in execute.text
    assert 'id="input-json"' not in execute.text
    bench = client.get("/benchmark.html")
    assert "Dataset BED-BPP" in bench.text
    assert "Recargar instancia showcase" not in bench.text
    catalog = client.get("/catalog.html")
    assert catalog.status_code == 200
    assert "solo-online" in catalog.text
    js = client.get("/assets/js/catalog.js")
    assert js.status_code == 200
    assert "default_parameters" in js.text
    ctx = client.get("/assets/js/problem-context.js")
    assert ctx.status_code == 200
    assert "fromUrl" in ctx.text
    data = client.get("/assets/data/showcase_3d_bpp_instance.json")
    assert data.status_code == 200
    assert data.json()["problem_type"] == "3D_BPP"


def test_gateway_proxies_algorithms(api_server, monkeypatch):
    monkeypatch.setenv("PACKING_API_URL", api_server)
    import gateway as gw

    monkeypatch.setattr(gw, "API_BASE", api_server)
    client = TestClient(app)
    response = client.get("/api/v1/algorithms", params={"status": "implemented"})
    assert response.status_code == 200
    data = response.json()
    names = {row["name"] for row in data}
    assert "drl_policy_3d_bpp" in names
    detail = client.get("/api/v1/algorithms/drl_policy_3d_bpp")
    assert detail.status_code == 200
    body = detail.json()
    assert body["default_parameters"]["model_path"].endswith("mlp_v1_p1s1.pt")
