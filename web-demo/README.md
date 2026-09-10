# Demo web — catálogo, execute y benchmark

Documento hijo de [`../README.md`](../README.md).

Interfaz **adicional**. No modifica la API: gateway estático + proxy al backend.
Sirve para **descubrir algoritmos, ejecutar uno y comparar metodologías** con
entrada BED-BPP. No es un espacio de datos (sin contratos, políticas ni
negociación de acceso).

## Flujo homogéneo (entrada BED-BPP)

En **Ejecutar** y **Benchmark** la instancia de entrada es siempre un dataset
**BED-BPP** (`order_id → { item_sequence, properties }`). El núcleo interno sigue
usando `containers` + `items` (conversión automática).

1. **Tipo de problema** (solo tipos compatibles con BED-BPP)
2. Filtrado de algoritmos compatibles
3. Pedido del dataset + configuración de parámetros (defaults seguros)

| Pestaña | Qué hace |
|---------|----------|
| Catálogo | Tarjetas de modelo + detalle (incluye cartonization) |
| Ejecutar | Pedido BED-BPP + parámetros → un algoritmo |
| Benchmark | Dataset BED-BPP (batch) → un pedido → comparar motores |

| Paso | Página | API usada |
|------|--------|-----------|
| Portal | `/` | `/demo/health`, `/api/v1/metadata` |
| Catálogo | `/catalog.html` | `GET /api/v1/algorithms?status=implemented` |
| Ejecutar uno | `/execute.html` | `GET .../algorithms/{name}`, `POST .../execute` |
| Benchmark | `/benchmark.html` | `GET /benchmark/profiles`, `POST /benchmark` |

Endpoints de dataset:

- `GET /api/v1/datasets/bed-bpp/sample`
- `POST /api/v1/datasets/bed-bpp/convert`
- Execute/benchmark aceptan `{ "input_format": "bed_bpp", "order_id", "orders", "parameters"? }`

### Visualización de layouts

Tras ejecutar un algoritmo o un benchmark, la pestaña/sección visual muestra:

1. **Layout 2D** (canvas): vistas superior (XY) y lateral (XZ) — `layout-viz.js`
2. **Layout 3D** (Plotly.js): cuboides Mesh3d + wireframe del contenedor — `layout-viz-3d.js`

La lógica 3D está adaptada del ejemplo [dwave-examples/3d-bin-packing](https://github.com/dwave-examples/3d-bin-packing)
(Apache-2.0), desacoplada del solver CQM y alimentada con `solution.packed_items`.

**No incluye** espacio de datos (contratos, políticas, soberanía, negociación).
Flujo: descubrir → ejecutar → comparar.

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
