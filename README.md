# packing-services

Arquitectura local, modular y extensible de **servicios independientes para
problemas de Cutting and Packing** (3D Bin Packing, Container Loading,
Cartonization, Palletization, Stacking-aware, Validación y Benchmark).

El objetivo **no** es implementar un único algoritmo, sino una **base robusta**
donde cada algoritmo pueda registrarse, ejecutarse, validarse, compararse y
documentarse de forma homogénea, para poder integrarse más adelante en un
espacio de datos.

Esta primera versión prioriza **heurísticas constructivas 3D-BPP + un validador
geométrico propio** antes que metaheurísticas, métodos exactos o IA (ver
`docs/roadmap.md`).

> Fuentes de requisitos: los dos documentos de contexto
> *"Resumen del estado del arte sobre Packing Management Algorithms orientados a
> servicios"* y *"Resumen del análisis de repositorios para servicios de Packing
> Management"*.

---

## Estado actual (v0.1.0)

| Capacidad | Estado |
|-----------|--------|
| Modelos de dominio comunes | ✅ |
| Entrada/salida JSON estandarizada | ✅ |
| Validador geométrico propio | ✅ |
| Métricas comunes | ✅ |
| Logs de ejecución + trazabilidad | ✅ |
| Registro homogéneo de algoritmos (catálogo completo) | ✅ |
| `heuristic_3d_bpp_v1` (Volume First Candidate Placement) | ✅ implementado |
| `first_fit_decreasing_3d` (First Fit Decreasing 3D) | ✅ implementado |
| `extreme_points_3d` (Extreme Points Heuristic) | ✅ implementado |
| `best_fit_decreasing_3d` (Best Fit Decreasing 3D) | ✅ implementado |
| **3D Bin Packing Offline Service** (`/pack/3d-bpp`) | ✅ operativo |
| **Container Loading Service** (`/pack/container-loading`) | ✅ operativo (baseline weight-aware) |
| **Cartonization Service** (`/pack/cartonization`) | ✅ operativo (selección de caja) |
| **Packing Validation Service** (`/validate`) | ✅ operativo |
| **Packing Benchmark / Comparison Service** (`/benchmark`) | ✅ operativo |
| **Preparación espacio de datos** (`/services`) | ✅ descriptores publicables |
| API local (FastAPI) | ✅ |
| Tests (pytest) | ✅ 80 tests |
| Adaptador `py3dbp` | ✅ (ejecutable si se instala `py3dbp`) |
| Adaptadores skjolber / BoxPacker / 3DContainerPacking / PackingSolver / D-Wave | 🟡 stubs documentados |
| Palletization / Stacking-aware Services | 🔜 fase posterior (PackingSolver) |
| Metaheurísticas, métodos exactos, híbridos, DRL | 🔜 registrados como `future` |

---

## Arquitectura

```
packing-services/
├── src/packing_services/
│   ├── domain/         # models, enums, geometry (primitivas AABB)
│   ├── schemas/        # requests / responses (contratos API, Pydantic)
│   ├── validation/     # validador geométrico propio + violations
│   ├── metrics/        # métricas comunes
│   ├── algorithms/     # base, metadata, registry + catálogo completo
│   ├── adapters/       # base + py3dbp + stubs de motores externos
│   ├── services/       # packing / container-loading / cartonization / validation / benchmark / dataspace / metadata / catalog
│   ├── api/            # FastAPI app + routers
│   └── utils/          # logging, timing, errors
├── examples/           # requests JSON ejecutables
├── tests/              # pytest
└── docs/               # architecture, algorithm_catalog, api_examples, roadmap, external_adapters
```

Detalles en `docs/architecture.md`.

---

## Instalación

Requiere **Python 3.10+** (recomendado 3.11+; el entorno de desarrollo usó
3.10.12).

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
pip install -e .               # instala el paquete (layout src/) en modo editable
```

> El proyecto usa **layout `src/`**. El `pip install -e .` es necesario para que
> `packing_services` sea importable por `uvicorn` desde cualquier directorio. Si
> prefieres no instalarlo, antepón `PYTHONPATH=src` a los comandos.

Adaptador opcional `py3dbp` (baseline externo):

```bash
pip install py3dbp
```

---

## Tests

```bash
pytest
```

---

## Levantar la API local

Deja este proceso **corriendo en una terminal** (no lo cierres) y usa `curl`
desde **otra** terminal.

```bash
# Si hiciste `pip install -e .`:
uvicorn packing_services.api.main:app --reload

# Si NO instalaste el paquete:
PYTHONPATH=src uvicorn packing_services.api.main:app --reload
```

Verás una línea como `Uvicorn running on http://127.0.0.1:8000`. Mientras no
aparezca, `curl` a `localhost:8000` dará `Connection refused`.

Docs interactivas en `http://localhost:8000/docs` (usa `http://`, no `https://`).

### Ejemplos con curl

```bash
curl -X GET http://localhost:8000/health

curl -X GET http://localhost:8000/api/v1/algorithms

curl -X GET "http://localhost:8000/api/v1/algorithms?status=implemented"

curl -X POST http://localhost:8000/api/v1/pack/3d-bpp \
  -H "Content-Type: application/json" \
  -d @examples/3d_bpp_basic_request.json

curl -X POST http://localhost:8000/api/v1/pack/container-loading \
  -H "Content-Type: application/json" \
  -d @examples/container_loading_request.json

curl -X POST http://localhost:8000/api/v1/pack/cartonization \
  -H "Content-Type: application/json" \
  -d @examples/cartonization_request.json

curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @examples/validation_request_invalid_overlap.json

curl -X POST http://localhost:8000/api/v1/benchmark \
  -H "Content-Type: application/json" \
  -d @examples/benchmark_request.json

# Descriptores de servicios listos para un espacio de datos
curl -X GET http://localhost:8000/api/v1/services
```

Más ejemplos en `docs/api_examples.md`.

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servicio |
| GET | `/api/v1/metadata` | Metadatos del servicio |
| GET | `/api/v1/services` | Descriptores de servicios para espacio de datos |
| GET | `/api/v1/algorithms` | Catálogo de algoritmos (filtros: `problem_type`, `family`, `status`, `supported_constraint`) |
| GET | `/api/v1/algorithms/{name}` | Metadatos de un algoritmo |
| POST | `/api/v1/pack/3d-bpp` | Ejecuta un algoritmo 3D-BPP |
| POST | `/api/v1/pack/container-loading` | Carga de contenedores/camiones (weight-aware) |
| POST | `/api/v1/pack/cartonization` | Selección de caja para un pedido |
| POST | `/api/v1/validate` | Valida una solución |
| POST | `/api/v1/benchmark` | Compara varios algoritmos |

Los endpoints de Palletization y Stacking-aware están en el roadmap
(`docs/roadmap.md`), previstos vía el adaptador PackingSolver.

---

## Convenciones geométricas

- Cajas alineadas a los ejes (AABB). `length`→X, `width`→Y, `height`→Z.
- Origen del contenedor en `(0,0,0)`; la posición de un ítem es su esquina de
  menor coordenada (min-corner).
- `allowed_orientations`: `"all"` (6 rotaciones) o `"none"`.

---

## Limitaciones actuales

- Los algoritmos iniciales son **heurísticos, no óptimos**.
- La **estabilidad física avanzada** no está completamente soportada (hay una
  comprobación básica de superficie de soporte en el validador).
- **Fragilidad, compatibilidad, secuencia de descarga, load-bearing y centro de
  gravedad** quedan para fases posteriores.
- **Container Loading** y **Cartonization** ya están operativos como baseline
  local; **Palletization y Stacking-aware** se implementarán después mediante
  adaptadores o motores específicos.
- **Cartonization** selecciona por ahora **una sola caja** (no multi-caja).
- Los **repositorios externos** se integran mediante adaptadores, **sin
  modificar** su código.
- **Métodos exactos, metaheurísticas, híbridos y DRL** quedan como fases futuras.
- El proyecto **aún no está integrado en un espacio de datos**; solo queda
  preparado mediante metadatos, entradas/salidas estandarizadas y trazabilidad.

---

## Próximos pasos (resumen)

Detalle completo en `docs/roadmap.md`.

**Corto plazo — mejorar calidad y cerrar grupos de servicio**
- `maximal_spaces_3d` (espacios vacíos máximos) para mayor calidad 3D-BPP.
- Heurísticas de mejora (`relocation_improvement`, `swap_improvement`,
  `solution_compaction`, `bin_reduction`) e híbrido constructivo + búsqueda local.
- **Palletization** y **Stacking-aware** como servicios operativos (reglas de
  soporte, carga máxima y capas), previstos vía `packingsolver_adapter`.
- Cartonization **multi-caja** (usar más de una caja por pedido).

**Medio plazo — motores externos y restricciones avanzadas**
- Activar adaptadores reales: `skjolber`, `BoxPacker`, `3DContainerPacking`
  (EB-AFIT), `PackingSolver`, `D-Wave`, sin modificar sus repositorios.
- Restricciones avanzadas: distribución de peso, centro de gravedad, estabilidad
  avanzada, `load_bearing`, fragilidad y secuencia de carga/descarga.

**Largo plazo — optimización avanzada e integración**
- Metaheurísticas (GA, Tabu, SA, GRASP, VNS, LNS), métodos exactos (MIP, CP-SAT)
  y enfoques híbridos, con trazabilidad de parámetros/semilla/tiempo.
- Online 3D-BPP y DRL (`drl_policy_3d_bpp`).
- **Integración real en un espacio de datos**: publicar → descubrir → negociar →
  ejecutar → validar → comparar → registrar evidencias (hoy solo *preparado* vía
  `GET /api/v1/services`).
- Empaquetado con **Docker** y despliegue por microservicios.

---

## Documentación

- `docs/architecture.md` — arquitectura y flujo de datos.
- `docs/algorithm_catalog.md` — catálogo completo de algoritmos y estados.
- `docs/api_examples.md` — ejemplos de request/response.
- `docs/roadmap.md` — fases y evolución por servicio.
- `docs/external_adapters.md` — estrategia de integración de motores externos.
