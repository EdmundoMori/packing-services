#!/usr/bin/env bash
# Despliega packing-services API + demo web en el mismo servidor.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${PACKING_API_PORT:-8000}"
WEB_PORT="${WEB_DEMO_PORT:-8080}"
API_HOST="${PACKING_API_HOST:-127.0.0.1}"

cd "$ROOT"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export PACKING_API_URL="http://${API_HOST}:${API_PORT}"

pip install -q httpx 2>/dev/null || true

echo "==> Iniciando API packing-services en :${API_PORT}"
uvicorn packing_services.api.main:app --host 0.0.0.0 --port "${API_PORT}" &
API_PID=$!

cleanup() {
  echo ""
  echo "==> Deteniendo servicios"
  kill "${API_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 30); do
  if curl -fsS "http://${API_HOST}:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "==> Iniciando demo web en :${WEB_PORT}"
echo "    Abre http://localhost:${WEB_PORT}"
export WEB_DEMO_PORT="${WEB_PORT}"
python web-demo/server/gateway.py
