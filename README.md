# packing-services

Arquitectura local, modular y extensible de **servicios independientes para
problemas de Cutting and Packing** (3D Bin Packing, Container Loading,
Cartonization, Palletization, Stacking-aware, Validación y Benchmark).

El objetivo **no** es implementar un único algoritmo, sino una **base robusta y
generalizable** donde cada algoritmo pueda registrarse, ejecutarse, validarse,
compararse y documentarse de forma homogénea, para integrarse en un espacio de
datos.

Esta versión prioriza **heurísticas constructivas + mejora local + validador
geométrico propio** como base; las **metaheurísticas 3D-BPP** ya están
implementadas. Métodos exactos e IA siguen en roadmap (ver `docs/roadmap.md`).

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
| Registro homogéneo de algoritmos (52 en catálogo) | ✅ |
| **29 algoritmos implementados** (ejecutables vía `/algorithms/{name}/execute`) | ✅ |
| **6 adaptadores** externos (`py3dbp` activo con `pip install py3dbp`) | ✅ |
| **Packing Validation Service** (`/validate`) | ✅ operativo |
| **Packing Benchmark / Comparison Service** (`/benchmark`) | ✅ operativo |
| **Preparación espacio de datos** (`/services`) | ✅ descriptores publicables |
| Endpoints legacy `/pack/*` | ✅ retrocompatibilidad |
| API local (FastAPI) | ✅ |
| Tests (pytest) | ✅ 215 tests |
| Notebooks didácticos (00–09) | ✅ 10 notebooks |
| Palletization / Stacking-aware | ✅ operativos |
| Metaheurísticas 3D-BPP (7) | ✅ SA, GA, GRASP, Tabu, LNS, VNS, ACO |
| Métodos exactos, online, DRL | 🔜 registrados como `future` |

### Algoritmos implementados (29)

| Grupo | Algoritmos |
|-------|------------|
| **3D-BPP constructivos** | `heuristic_3d_bpp_v1`, `first_fit_decreasing_3d`, `best_fit_decreasing_3d`, `extreme_points_3d`, `maximal_spaces_3d` |
| **3D-BPP mejora / híbrido** | `solution_compaction`, `constructive_plus_local_search`, `relocation_improvement`, `swap_improvement`, `orientation_improvement`, `bin_reduction` |
| **3D-BPP metaheurísticas** | `simulated_annealing_3d_bpp`, `genetic_algorithm_3d_bpp`, `grasp_3d_bpp`, `tabu_search_3d_bpp`, `lns_3d_bpp`, `vns_3d_bpp`, `aco_3d_bpp` |
| **Container Loading** | `single_container_constructive`, `weight_aware_container_loading`, `wall_building_3d` |
| **Cartonization** | `smallest_feasible_box`, `best_box_volume_utilization`, `first_fit_box`, `largest_feasible_box`, `multi_box_cartonization` |
| **Palletization** | `layer_based_palletization`, `stack_based_palletization` |
| **Stacking-aware** | `stacking_aware_constructive` (+ `stack_based_palletization` comparable) |

Detalle, estados y tabla completa: `docs/algorithm_catalog.md`.
Checklist de trazabilidad: `docs/algorithm_implementation_traceability.md`.

---

## Patrón de ejecución canónico

Cada algoritmo implementado expone **un endpoint propio** con contrato homogéneo:

```
POST /api/v1/algorithms/{algorithm_name}/execute
```

- **Entrada pack** (`3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION`, `STACKING_AWARE`):
  `PackAlgorithmInput` — sin campo `algorithm` en el body (el nombre va en la URL).
- **Entrada cartonization**: `CartonizationAlgorithmInput`.
- **Salida**: `AlgorithmExecuteResponse` con `solution` (`PackingSolution`) y
  `cartonization` opcional.

Metadatos enriquecidos por algoritmo:

- `GET /api/v1/algorithms/{name}` — esquemas de entrada/salida y endpoint de ejecución.
- `GET /api/v1/algorithms/{name}/input-example` — ejemplo JSON listo para ejecutar.

Los endpoints `/pack/3d-bpp`, `/pack/container-loading`, `/pack/cartonization`,
`/pack/palletization` y `/pack/stacking-aware` siguen activos por retrocompatibilidad.

---

## Arquitectura

```
packing-services/
├── src/packing_services/
│   ├── domain/         # models, enums, geometry (primitivas AABB)
│   ├── schemas/        # requests / responses (contratos API, Pydantic)
│   ├── validation/     # validador geométrico propio + violations
│   ├── metrics/        # métricas comunes
│   ├── algorithms/     # base, metadata, registry + motores compartidos
│   ├── adapters/       # base + py3dbp + stubs de motores externos
│   ├── services/       # execution, catalog, benchmark, dataspace, ...
│   ├── api/            # FastAPI app + routers
│   └── utils/          # logging, timing, errors
├── examples/           # requests JSON ejecutables
├── notebooks/          # 10 notebooks didácticos (00–09)
├── tests/              # pytest
└── docs/               # architecture, algorithm_catalog, api_examples, roadmap
```

Detalles en `docs/architecture.md`.

---

## Instalación

Requiere **Python 3.10+** (recomendado 3.11+).

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
pip install -e .               # layout src/ en modo editable
```

> Si prefieres no instalar el paquete, antepón `PYTHONPATH=src` a los comandos.

Adaptador opcional `py3dbp` (baseline externo):

```bash
pip install py3dbp
```

---

## Tests

```bash
pytest
# o con PYTHONPATH explícito:
PYTHONPATH=src pytest tests/ -q
```

### Scripts de mantenimiento

| Script | Uso |
|--------|-----|
| `scripts/regenerate_algorithm_catalog.py` | Regenera `docs/algorithm_catalog.md` desde el registry |
| `scripts/sync_web_demo_showcase.py` | Sincroniza `examples/showcase_*` → `web-demo/static/assets/data/` |

---

## Notebooks didácticos

**10 notebooks** (00–09) en `notebooks/` para explicar el avance de forma visual
(layouts, benchmarks, catálogo, espacio de datos).

```bash
pip install -e ".[notebooks]"
cd notebooks
jupyter notebook
```

Validación de todos los notebooks:

```bash
MPLBACKEND=Agg python notebooks/_build_notebooks.py   # regenerar desde fuentes
MPLBACKEND=Agg python notebooks/_execute_all.py       # ejecutar 00→09
```

Guía: `notebooks/README.md`.

### Demo web (simulación de espacio de datos)

Interfaz adicional en `web-demo/` — catálogo, ejecución individual y benchmark
sin modificar la API existente. Ver `web-demo/README.md`.

```bash
./web-demo/start.sh   # API :8000 + UI :8080
```

---

## Levantar la API local

```bash
uvicorn packing_services.api.main:app --reload
# sin pip install -e .:
PYTHONPATH=src uvicorn packing_services.api.main:app --reload
```

Docs interactivas: `http://localhost:8000/docs`

### Ejemplos con curl

```bash
curl -X GET http://localhost:8000/health

curl -X GET http://localhost:8000/api/v1/algorithms

curl -X GET "http://localhost:8000/api/v1/algorithms?status=implemented"

# Ejecución canónica por algoritmo
curl -X POST http://localhost:8000/api/v1/algorithms/heuristic_3d_bpp_v1/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json

curl -X POST http://localhost:8000/api/v1/algorithms/weight_aware_container_loading/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_container_loading.json

curl -X POST http://localhost:8000/api/v1/algorithms/smallest_feasible_box/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_cartonization.json

curl -X POST http://localhost:8000/api/v1/algorithms/solution_compaction/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_improvement.json

curl -X POST http://localhost:8000/api/v1/algorithms/multi_box_cartonization/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_cartonization.json

curl -X POST http://localhost:8000/api/v1/algorithms/wall_building_3d/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_container_loading.json

curl -X POST http://localhost:8000/api/v1/pack/palletization \
  -H "Content-Type: application/json" \
  -d @examples/palletization_request.json

curl -X POST http://localhost:8000/api/v1/pack/stacking-aware \
  -H "Content-Type: application/json" \
  -d @examples/stacking_aware_request.json

curl -X POST http://localhost:8000/api/v1/algorithms/layer_based_palletization/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_palletization.json

curl -X POST http://localhost:8000/api/v1/algorithms/stacking_aware_constructive/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_stacking_aware.json

curl -X POST http://localhost:8000/api/v1/algorithms/simulated_annealing_3d_bpp/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json

# Validación y benchmark
curl -X POST http://localhost:8000/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @examples/validation_request_invalid_overlap.json

curl -X POST http://localhost:8000/api/v1/benchmark \
  -H "Content-Type: application/json" \
  -d @examples/benchmark_metaheuristic_request.json

# Descriptores para espacio de datos
curl -X GET http://localhost:8000/api/v1/services
```

Más ejemplos en `docs/api_examples.md`.

---

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado del servicio |
| GET | `/api/v1/metadata` | Metadatos del servicio |
| GET | `/api/v1/services` | Descriptores para espacio de datos |
| GET | `/api/v1/algorithms` | Catálogo (filtros: `problem_type`, `family`, `status`, …) |
| GET | `/api/v1/algorithms/{name}` | Metadatos + esquemas + endpoint de ejecución |
| GET | `/api/v1/algorithms/{name}/input-example` | Ejemplo de entrada JSON |
| **POST** | **`/api/v1/algorithms/{name}/execute`** | **Ejecución canónica por algoritmo** |
| POST | `/api/v1/pack/3d-bpp` | Legacy: 3D-BPP |
| POST | `/api/v1/pack/container-loading` | Legacy: Container Loading |
| POST | `/api/v1/pack/palletization` | Legacy: Palletization |
| POST | `/api/v1/pack/stacking-aware` | Legacy: Stacking-aware |
| POST | `/api/v1/validate` | Valida una solución |
| POST | `/api/v1/benchmark` | Compara varios algoritmos |

Palletization y Stacking-aware operativos con heurísticas locales (`docs/roadmap.md`).

---

## Convenciones geométricas

- Cajas alineadas a los ejes (AABB). `length`→X, `width`→Y, `height`→Z.
- Origen del contenedor en `(0,0,0)`; la posición de un ítem es su esquina de
  menor coordenada (min-corner).
- `allowed_orientations`: `"all"` (6 rotaciones) o `"none"`.

---

## Limitaciones actuales

- Los algoritmos iniciales son **heurísticos, no óptimos**.
- Estabilidad física avanzada, fragilidad, load-bearing y centro de gravedad:
  fases posteriores.
- **Cartonization** selecciona una sola caja en algoritmos single-box; `multi_box_cartonization` permite varias cajas por pedido.
- Motores externos vía adaptadores, **sin modificar** sus repositorios.
- Integración real en espacio de datos: preparada vía metadatos y `/services`.

---

## Próximos pasos (resumen)

Detalle en `docs/roadmap.md`.

**Corto plazo**
- Activar adaptadores externos reales (PackingSolver, skjolber, BoxPacker, EB-AFIT).

**Medio / largo plazo**
- Restricciones avanzadas (peso, secuencia, fragilidad).
- Metaheurísticas, métodos exactos, DRL.
- Integración en espacio de datos y despliegue Docker.

---

## Documentación

| Documento | Contenido |
|-----------|-----------|
| `docs/architecture.md` | Capas, flujos, principios de diseño |
| `docs/algorithm_catalog.md` | Catálogo completo (52 algoritmos, 29 implementados) |
| `docs/algorithm_implementation_traceability.md` | Checklist por algoritmo |
| `docs/api_examples.md` | Ejemplos request/response (incl. `/execute`) |
| `docs/roadmap.md` | Fases y evolución |
| `docs/external_adapters.md` | Integración de motores externos |
| `notebooks/README.md` | Guía de presentación didáctica |
