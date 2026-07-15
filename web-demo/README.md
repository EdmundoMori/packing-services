# Demo web — simulación de espacio de datos

Interfaz web **adicional** al proyecto `packing-services`. No modifica la API ni
el núcleo existente: consume los endpoints ya implementados mediante un gateway
que sirve la UI y hace proxy al backend.

## Flujo homogéneo (3 pestañas)

En **Catálogo**, **Ejecutar** y **Benchmark** el primer paso es siempre:

1. **Tipo de problema** (3D_BPP, Container Loading, Cartonization, …)
2. Filtrado automático de algoritmos compatibles
3. Acción específica de cada vista

| Pestaña | Qué hace |
|---------|----------|
| Catálogo | Tarjetas de modelo + detalle al seleccionar |
| Ejecutar | Formulario UI o JSON → un solo algoritmo |
| Benchmark | Instancia showcase por tipo + tabla comparativa |

Las instancias showcase viven en `static/assets/data/` (sincronizadas desde `examples/showcase_*`).

```bash
python scripts/sync_web_demo_showcase.py   # tras editar instancias en examples/
```

| Paso | Página | API usada |
|------|--------|-----------|
| Portal | `/` | `/demo/health`, `/api/v1/metadata` |
| Catálogo | `/catalog.html` | `GET /api/v1/algorithms?status=implemented` |
| Ejecutar uno | `/execute.html` | `GET .../input-example`, `POST .../execute` |
| Benchmark | `/benchmark.html` | `GET /benchmark/profiles`, `POST /benchmark` |

**No incluye** contratos, políticas de uso, soberanía ni negociación de acceso.
Solo la funcionalidad de descubrir → ejecutar → comparar.

## Arquitectura en un mismo servidor

```
┌─────────────────────────────────────────────┐
│  Puerto 8080 — Gateway web-demo             │
│  · HTML/CSS/JS estático                     │
│  · Proxy /api/v1/* → API interna            │
└──────────────────┬──────────────────────────┘
                   │ PACKING_API_URL
┌──────────────────▼──────────────────────────┐
│  Puerto 8000 — packing-services API         │
│  (FastAPI existente, sin cambios)           │
└─────────────────────────────────────────────┘
```

## Arranque rápido

Desde la raíz del proyecto:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pip install httpx
chmod +x web-demo/start.sh
./web-demo/start.sh
```

Abre **http://localhost:8080**

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PACKING_API_PORT` | `8000` | Puerto de la API interna |
| `WEB_DEMO_PORT` | `8080` | Puerto de la interfaz web |
| `PACKING_API_URL` | `http://127.0.0.1:8000` | URL del backend (gateway) |

## Docker (todo en un contenedor)

```bash
cd web-demo
docker compose up --build
```

Acceso: http://localhost:8080

## Estructura

```
web-demo/
├── start.sh              # Levanta API + gateway
├── docker-compose.yml
├── Dockerfile
├── server/gateway.py     # FastAPI: estático + proxy
└── static/
    ├── index.html
    ├── catalog.html
    ├── execute.html
    ├── benchmark.html
    └── assets/
        ├── css/app.css
        └── js/*.js
```

## Desarrollo

Solo gateway (si la API ya corre en :8000):

```bash
PACKING_API_URL=http://127.0.0.1:8000 python web-demo/server/gateway.py
```

## Notas

- El catálogo muestra solo algoritmos `implemented`.
- La ejecución carga automáticamente el `input-example` del algoritmo elegido.
- El benchmark permite selección manual (≥2 motores) o perfil estándar (`profile`).
