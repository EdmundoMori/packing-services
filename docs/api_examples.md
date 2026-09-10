# Ejemplos de API

Documento hijo de [`../README.md`](../README.md). Índice: [`README.md`](README.md).
Los JSON están en `examples/`. Prioridad: execute canónico, BED-BPP, benchmark
(por tipo y conjunto). `GET /api/v1/services` es residual.

## `POST /api/v1/algorithms/{algorithm_name}/execute`

Endpoint principal por algoritmo (Opción A3). El nombre del algoritmo va en la URL;
el body es el input normalizado por tipo de problema, **sin** el campo `algorithm`.

### Pack (3D_BPP, CONTAINER_LOADING, SINGLE_CONTAINER_LOADING, PALLETIZATION, STACKING_AWARE)

Request (`examples/algorithm_execute_3d_bpp.json`):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/heuristic_3d_bpp_v1/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json
```

Metaheurística 3D-BPP (requiere `random_seed` / `iterations` en `parameters` o body):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/simulated_annealing_3d_bpp/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json
```

```json
{
  "problem_type": "3D_BPP",
  "request_id": "example-001",
  "containers": [{ "id": "C1", "length": 120, "width": 80, "height": 100, "max_weight": 1000 }],
  "items": [
    { "id": "I1", "length": 40, "width": 40, "height": 40, "weight": 10, "quantity": 4, "allowed_orientations": "all" }
  ],
  "constraints": { "non_overlap": true, "containment": true, "allow_rotation": true, "max_weight": true },
  "objective": "maximize_volume_utilization",
  "parameters": { "sort_strategy": "volume_desc", "position_strategy": "bottom_left_back" }
}
```

Si el algoritmo admite varios `problem_type`, el campo es **obligatorio** (estrategia A3).
Ejemplos adicionales:

| Tipo | Archivo | Algoritmo de ejemplo |
|------|---------|----------------------|
| `CONTAINER_LOADING` | `algorithm_execute_container_loading.json` | `weight_aware_container_loading` |
| `SINGLE_CONTAINER_LOADING` | `algorithm_execute_single_container.json` | `best_fit_decreasing_3d` |
| Mejora local | `algorithm_execute_improvement.json` | `solution_compaction` |

La respuesta es siempre **`AlgorithmExecuteResponse`** (salida homogénea):

```json
{
  "request_id": "example-001",
  "algorithm_name": "heuristic_3d_bpp_v1",
  "problem_type": "3D_BPP",
  "status": "success",
  "solution": {
    "algorithm_name": "heuristic_3d_bpp_v1",
    "problem_type": "3D_BPP",
    "packed_items": [],
    "metrics": { "volume_utilization": 0.7, "items_packed": 12 },
    "validation_report": { "is_valid": true, "violations": [] },
    "execution_metadata": { "algorithm": "heuristic_3d_bpp_v1" }
  },
  "cartonization": null
}
```

Para cartonization, `cartonization` incluye `selected_box_id` y `evaluated_boxes`; la solución de packing va en `solution`.

Consulta el contrato de cada algoritmo:

```bash
GET /api/v1/algorithms/heuristic_3d_bpp_v1
GET /api/v1/algorithms/heuristic_3d_bpp_v1/input-example?problem_type=3D_BPP
```

### Dataset BED-BPP (mismo execute / benchmark)

Muestra: `examples/5_bed-bpp.json`. Conversión y ejecución integradas (no hay flujo aparte):

```bash
GET /api/v1/datasets/bed-bpp/sample
POST /api/v1/datasets/bed-bpp/convert
```

Execute con wrapper (el servicio normaliza a `containers` + `items`):

```json
{
  "input_format": "bed_bpp",
  "order_id": "00100001",
  "orders": { },
  "problem_type": "PALLETIZATION",
  "parameters": { "sort_strategy": "volume_desc" }
}
```

En la demo web: pestaña **BED-BPP** en Ejecutar y bloque **Instancia BED-BPP** en Benchmark.

### Experimento conjunto (un euro-pallet, cuatro tipos)

Compara `3D_BPP`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION` y `STACKING_AWARE`
sobre el pedido más pequeño de `examples/5_bed-bpp.json`, forzado a euro-pallet,
con `sort_strategy=input_order`. Mismo validador y mismas métricas.

```bash
curl -X POST http://localhost:8000/api/v1/benchmark/joint-single-container \
  -H "Content-Type: application/json" \
  -d '{}'

PYTHONPATH=src python scripts/run_joint_single_container.py
```

Cartonization no entra: elige caja del catálogo, no recibe el contenedor fijado.

Request (`examples/algorithm_execute_cartonization.json`):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/smallest_feasible_box/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_cartonization.json
```

```json
{
  "request_id": "carton-001",
  "items": [{ "id": "SKU1", "length": 20, "width": 15, "height": 10, "weight": 2, "quantity": 3 }],
  "boxes": [{ "id": "BOX_M", "length": 40, "width": 30, "height": 20, "max_weight": 30 }],
  "constraints": { "non_overlap": true, "containment": true, "allow_rotation": true, "max_weight": true },
  "parameters": { "sort_strategy": "volume_desc" }
}
```

La respuesta usa la misma envoltura `AlgorithmExecuteResponse`; `cartonization.selected_box_id` indica la caja elegida.

---

## `POST /api/v1/pack/3d-bpp` (legacy)

Request (`examples/3d_bpp_basic_request.json`):

```json
{
  "problem_type": "3D_BPP",
  "request_id": "example-001",
  "containers": [
    { "id": "C1", "length": 120, "width": 80, "height": 100, "max_weight": 1000 }
  ],
  "items": [
    { "id": "I1", "length": 40, "width": 40, "height": 40, "weight": 10, "quantity": 4, "allowed_orientations": "all" }
  ],
  "constraints": { "non_overlap": true, "containment": true, "allow_rotation": true, "max_weight": true },
  "objective": "maximize_volume_utilization",
  "algorithm": {
    "name": "heuristic_3d_bpp_v1",
    "parameters": { "sort_strategy": "volume_desc", "position_strategy": "bottom_left_back" },
    "random_seed": null,
    "time_limit_seconds": 10
  }
}
```

Response (estructura):

```json
{
  "request_id": "example-001",
  "status": "success",
  "problem_type": "3D_BPP",
  "algorithm_name": "heuristic_3d_bpp_v1",
  "packed_items": [
    {
      "item_id": "I1#1",
      "container_id": "C1",
      "position": { "x": 0, "y": 0, "z": 0 },
      "orientation": { "length": 40, "width": 40, "height": 40 },
      "weight": 10
    }
  ],
  "unpacked_items": [],
  "metrics": {
    "volume_utilization": 0.7,
    "waste_volume": 0.3,
    "containers_used": 1,
    "items_packed": 12,
    "items_unpacked": 0,
    "packed_volume": 0,
    "unpacked_volume": 0,
    "total_item_volume": 0,
    "loaded_weight": 0,
    "execution_time_seconds": 0.001,
    "constraint_violations": 0
  },
  "validation_report": { "is_valid": true, "violations": [] },
  "execution_metadata": {
    "algorithm": "heuristic_3d_bpp_v1",
    "algorithm_family": "constructive_heuristic",
    "parameters": { "sort_strategy": "volume_desc" },
    "random_seed": null,
    "service_version": "0.1.0"
  }
}
```

> Nota: los ítems con `quantity > 1` se expanden internamente a ids únicos
> (`I1#1`, `I1#2`, ...).

## `POST /api/v1/pack/container-loading`

Request (`examples/container_loading_request.json`). El algoritmo es opcional; por
defecto usa `weight_aware_container_loading`, que prioriza los ítems más pesados y
respeta el peso máximo del contenedor. La respuesta tiene la misma forma que
`/pack/3d-bpp` (una `PackingSolution`), por lo que es comparable vía benchmark.

```json
{
  "problem_type": "CONTAINER_LOADING",
  "request_id": "cl-001",
  "containers": [{ "id": "TRUCK1", "length": 240, "width": 120, "height": 120, "max_weight": 500 }],
  "items": [{ "id": "PALLET_A", "length": 80, "width": 60, "height": 100, "weight": 120, "quantity": 3 }],
  "algorithm": { "name": "weight_aware_container_loading", "parameters": { "sort_strategy": "weight_desc" } }
}
```

## `POST /api/v1/pack/cartonization`

Request (`examples/cartonization_request.json`): un pedido (`items`) + un catálogo
de cajas candidatas (`boxes`). El servicio selecciona **una** caja según la
estrategia (`smallest_feasible_box` o `best_box_volume_utilization`).

```json
{
  "request_id": "carton-001",
  "items": [{ "id": "SKU1", "length": 20, "width": 15, "height": 10, "weight": 2, "quantity": 3 }],
  "boxes": [
    { "id": "BOX_S", "length": 30, "width": 20, "height": 15, "max_weight": 20, "cost": 0.5 },
    { "id": "BOX_M", "length": 40, "width": 30, "height": 20, "max_weight": 30, "cost": 0.8 }
  ],
  "algorithm": { "name": "smallest_feasible_box" }
}
```

Response (estructura):

```json
{
  "request_id": "carton-001",
  "status": "success",
  "selected_box_id": "BOX_M",
  "algorithm_name": "smallest_feasible_box",
  "solution": { "packed_items": ["..."], "metrics": { "...": "..." }, "validation_report": { "is_valid": true } },
  "evaluated_boxes": [
    { "box_id": "BOX_S", "fits_all": false, "items_packed": 2, "volume_utilization": 0.9 },
    { "box_id": "BOX_M", "fits_all": true, "items_packed": 5, "volume_utilization": 0.62 }
  ]
}
```

## `POST /api/v1/validate`

Request (`examples/validation_request_invalid_overlap.json`) — dos ítems que se
solapan. Response:

```json
{
  "request_id": "invalid-overlap-001",
  "validation_report": {
    "is_valid": false,
    "violations": [
      {
        "type": "OVERLAP",
        "message": "Los ítems I1 y I2 se solapan en el contenedor C1",
        "container_id": "C1",
        "item_ids": ["I1", "I2"],
        "severity": "error"
      }
    ]
  },
  "recomputed_metrics": { "...": "..." }
}
```

## `POST /api/v1/benchmark`

Compara varios motores sobre la **misma instancia**. Hay dos formas de indicar los motores:

1. **`profile`** (recomendado): conjunto estándar predefinido (≥2 motores comparables).
2. **`engines`** explícito: lista manual (tiene prioridad si ambos están presentes).

Descubre perfiles disponibles:

```bash
curl http://localhost:8000/api/v1/benchmark/profiles
curl "http://localhost:8000/api/v1/benchmark/profiles?problem_type=CARTONIZATION"
```

### Perfiles estándar por tipo de problema

| `problem_type` | Perfil | Motores comparados |
|----------------|--------|-------------------|
| `3D_BPP` | `constructive` | 4 heurísticas + `py3dbp_adapter` (opcional) |
| `3D_BPP` | `hybrid` | `best_fit` → `solution_compaction` → `constructive_plus_local_search` |
| `CONTAINER_LOADING` | `constructive` | `single_container_constructive`, `weight_aware`, `extreme_points_3d` |
| `CONTAINER_LOADING` | `improvement` | `weight_aware` + compactación + híbrido |
| `CARTONIZATION` | `box_selection` | `smallest_feasible_box`, `best_box_volume_utilization`, `first_fit_box`, `largest_feasible_box` |
| `SINGLE_CONTAINER_LOADING` | `constructive` | `single_container_constructive`, `best_fit`, `first_fit` |

Ejemplo mínimo con perfil (sin listar motores a mano):

```bash
curl -X POST http://localhost:8000/api/v1/benchmark \
  -H "Content-Type: application/json" \
  -d @examples/benchmark_cartonization_request.json
```

El JSON solo necesita `problem_type`, `profile`, `items`/`containers`/`boxes` según el tipo.

| Grupo | Ejemplo JSON |
|-------|--------------|
| `3D_BPP` constructivo | `examples/benchmark_3d_bpp_profile_request.json` |
| `3D_BPP` híbrido | `examples/benchmark_hybrid_request.json` |
| `3D_BPP` mejora | `examples/benchmark_improvement_request.json` |
| `3D_BPP` metaheurísticas | `examples/benchmark_metaheuristic_request.json` |
| `CONTAINER_LOADING` | `examples/benchmark_container_loading_request.json` |
| `CARTONIZATION` | `examples/benchmark_cartonization_request.json` |
| `SINGLE_CONTAINER_LOADING` | `examples/benchmark_single_container_request.json` |

El ejemplo 3D-BPP usa **30 piezas** y **2 contenedores**, diseñado para mostrar
diferencias claras de utilización y piezas empacadas. Response:

```json
{
  "request_id": "benchmark-001",
  "results": [
    {
      "engine": "heuristic_3d_bpp_v1",
      "status": "partial",
      "is_valid": true,
      "metrics": { "...": "..." },
      "details": {}
    },
    {
      "engine": "smallest_feasible_box",
      "status": "partial",
      "is_valid": true,
      "metrics": { "...": "..." },
      "details": { "selected_box_id": "BOX_L", "evaluated_boxes": [] }
    }
  ],
  "ranking": ["best_fit_decreasing_3d", "first_fit_decreasing_3d"],
  "ranking_explanation": "Ranking 3D-BPP: (1) soluciones válidas; (2) mayor volume_utilization; ...",
  "details": {
    "benchmark_group": "3D_BPP",
    "engines_total": 5,
    "engines_valid": 5,
    "best_engine": "best_fit_decreasing_3d"
  }
}
```

## `GET /api/v1/services` (despriorizado)

Catálogo de descriptores residual. **No** forma parte de la línea de trabajo
(inputs, benchmark, online). Ver [`roadmap.md`](roadmap.md) apartado 5.

```json
{
  "service_version": "0.1.0",
  "dataspace_ready": true,
  "services": [
    {
      "service_name": "Cartonization Service",
      "problem_type": "CARTONIZATION",
      "algorithms": ["smallest_feasible_box", "best_box_volume_utilization"],
      "engine": "internal (box selection + extreme points)",
      "license": "MIT",
      "input_schema": "CartonizationRequest",
      "output_schema": "CartonizationResponse",
      "execution_endpoint": "POST /api/v1/pack/cartonization",
      "validation_endpoint": "POST /api/v1/validate",
      "traceability": ["execution_metadata (...)", "validation_report por ejecución"],
      "limitations": ["Selecciona una sola caja; motor principal futuro: BoxPacker"]
    }
  ],
  "notes": ["Servicios preparados para publicación; aún NO integrados en un espacio de datos real."]
}
```

## `GET /api/v1/algorithms`

Filtros combinables:

```bash
# Solo implementados
curl "http://localhost:8000/api/v1/algorithms?status=implemented"

# Por tipo de problema
curl "http://localhost:8000/api/v1/algorithms?problem_type=3D_BPP"

# Por familia
curl "http://localhost:8000/api/v1/algorithms?family=metaheuristic"

# Por restricción soportada
curl "http://localhost:8000/api/v1/algorithms?supported_constraint=max_weight"
```

## Códigos de error

| Código | Situación |
|--------|-----------|
| 422 | Entrada inválida (validación Pydantic o `InvalidInputError`) |
| 404 | Algoritmo inexistente |
| 400 | Algoritmo no ejecutable (estado `future`) |
| 503 | Adaptador externo no disponible (dependencia/motor ausente) |
| 500 | Error inesperado de ejecución |
