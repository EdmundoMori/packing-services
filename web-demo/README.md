# Interfaz Web de Demostración

Documento complementario de [`../README.md`](../README.md).

## Propósito

Esta interfaz web proporciona una forma visual de interactuar con el sistema **packing-services**. Permite descubrir algoritmos, ejecutar instancias individuales y comparar metodologías mediante benchmark.

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas:

- **Misma entrada:** formato de datos unificado para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo.
- **Mismas métricas:** indicadores de rendimiento calculados uniformemente.

El sistema soporta tanto el modo `packing_mode=offline` como `packing_mode=online`.

> **Nota:** Esta interfaz no implementa un espacio de datos distribuido (contratos, políticas de acceso, negociación). Su función es exclusivamente la demostración del sistema de comparación.

---

## Características Principales

### Entrada Homogénea (Formato BED-BPP)

En las secciones **Ejecutar** y **Benchmark**, la instancia de entrada es siempre un dataset BED-BPP (`order_id → { item_sequence, properties }`). El núcleo interno realiza la conversión automática hacia `containers` + `items`.

### Flujo de Uso

1. Seleccionar **modo de packing** (`offline` u `online`) y **tipo de problema**
2. El sistema filtra los algoritmos compatibles con el modo seleccionado
3. Seleccionar pedido del dataset y configurar parámetros (valores predeterminados seguros disponibles)

### Funcionalidades por Pestaña

| Pestaña | Funcionalidad |
|---------|---------------|
| Catálogo | Tarjetas descriptivas de algoritmos + detalle completo (incluye cartonization) |
| Ejecutar | Selección de pedido BED-BPP + configuración de parámetros → ejecución de un algoritmo |
| Benchmark | Selección de dataset BED-BPP (batch) → selección de pedido → comparación de múltiples motores |

### Endpoints API Utilizados

| Paso | Página | Endpoint |
|------|--------|----------|
| Portal | `/` | `/demo/health`, `/api/v1/metadata` |
| Catálogo | `/catalog.html` | `GET /api/v1/algorithms?status=implemented` |
| Ejecutar | `/execute.html` | `GET /api/v1/algorithms/{name}`, `POST /api/v1/algorithms/{name}/execute` |
| Benchmark | `/benchmark.html` | `GET /benchmark/profiles`, `POST /benchmark` |

---

## Modo Online con Política Aprendida

En la sección **Ejecutar**, al seleccionar `packing_mode=online` y el algoritmo `drl_policy_3d_bpp`:

- El formulario carga automáticamente los parámetros predeterminados:
  - `model_path=mlp_v1_p1s1.pt`
  - `lookahead_p=1`
  - `select_s=1`

- Para configuración de cinta: cambiar a `mlp_v1_p3s2.pt` con `p=3`, `s=2`

> **Requisito:** Los archivos `.pt` requieren `pip install 'packing-services[torch]'` en el backend.

### Holdout de Producto

El archivo `examples/5_bed-bpp.json` contiene el holdout de producto (por ejemplo, pedido `00100408`).

### Endpoints de Dataset

```bash
GET /api/v1/datasets/bed-bpp/sample
POST /api/v1/datasets/bed-bpp/convert
```

El formato de ejecución y benchmark acepta:
```json
{
  "input_format": "bed_bpp",
  "order_id": "...",
  "orders": {...},
  "packing_mode": "offline|online"
}
```

---

## Visualización de Layouts

Tras ejecutar un algoritmo o un benchmark, la interfaz muestra:

1. **Layout 2D** (canvas): vistas superior (XY) y lateral (XZ)
   - Implementación: `layout-viz.js`

2. **Layout 3D** (Plotly.js): cuboides Mesh3d con wireframe del contenedor
   - Implementación: `layout-viz-3d.js`
   - Adaptado de [dwave-examples/3d-bin-packing](https://github.com/dwave-examples/3d-bin-packing) (Apache-2.0)
   - Desacoplado del solver CQM y alimentado con `solution.packed_items`

---

## Arquitectura del Sistema

La interfaz web funciona como un gateway que sirve contenido estático y hace proxy hacia la API de packing-services:

```
┌─────────────────────────────────────────────┐
│  Puerto 8080 — Gateway web-demo             │
│  · HTML/CSS/JS estático                     │
│  · Proxy /api/v1/* → API interna            │
└──────────────────┬──────────────────────────┘
                   │ PACKING_API_URL
┌──────────────────▼──────────────────────────┐
│  Puerto 8000 — packing-services API         │
│  (FastAPI existente, sin modificaciones)    │
└─────────────────────────────────────────────┘
```

---

## Instalación y Ejecución

### Arranque Rápido

Desde la raíz del proyecto:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
pip install httpx
chmod +x web-demo/start.sh
./web-demo/start.sh
```

Acceder a: **http://localhost:8080**

### Variables de Entorno

| Variable | Valor Predeterminado | Descripción |
|----------|---------------------|-------------|
| `PACKING_API_PORT` | `8000` | Puerto de la API interna |
| `WEB_DEMO_PORT` | `8080` | Puerto de la interfaz web |
| `PACKING_API_URL` | `http://127.0.0.1:8000` | URL del backend (gateway) |

### Ejecución con Docker

```bash
cd web-demo
docker compose up --build
```

Acceder a: **http://localhost:8080**

---

## Estructura del Directorio

```
web-demo/
├── start.sh              # Script de arranque (API + gateway)
├── docker-compose.yml    # Configuración Docker
├── Dockerfile            # Imagen Docker
├── server/
│   └── gateway.py        # FastAPI: contenido estático + proxy
└── static/
    ├── index.html        # Página principal
    ├── catalog.html      # Catálogo de algoritmos
    ├── execute.html      # Ejecución individual
    ├── benchmark.html    # Comparación de motores
    └── assets/
        ├── css/app.css   # Estilos
        └── js/*.js       # JavaScript de la aplicación
```

---

## Desarrollo

### Ejecutar Solo el Gateway

Si la API ya está corriendo en el puerto 8000:

```bash
PACKING_API_URL=http://127.0.0.1:8000 python web-demo/server/gateway.py
```

---

## Notas de Uso

- **Catálogo:** Muestra solo algoritmos con estado `implemented` y filtra por `packing_mode`. Los algoritmos solo-online aparecen al seleccionar modo online.

- **Ejecutar y Benchmark:** Utilizan pedidos BED-BPP (`examples/5_bed-bpp.json`, holdout de producto), no el `input-example` showcase. El endpoint `input-example` permanece disponible en la API para el contrato canónico.

- **Modo Online:** El algoritmo `drl_policy_3d_bpp` rellena automáticamente `model_path=mlp_v1_p1s1.pt` (p=1 s=1).

- **Benchmark:** Permite selección manual de motores (≥2) o uso de perfil estándar (`profile`).
