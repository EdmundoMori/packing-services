# Ejemplos de API

Los archivos JSON referenciados están en `examples/`.

## `POST /api/v1/pack/3d-bpp`

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

Request (`examples/benchmark_request.json`) compara `heuristic_3d_bpp_v1` y
`first_fit_decreasing_3d`. Response:

```json
{
  "request_id": "benchmark-001",
  "results": [
    { "engine": "heuristic_3d_bpp_v1", "status": "partial", "is_valid": true, "metrics": { "...": "..." } },
    { "engine": "first_fit_decreasing_3d", "status": "partial", "is_valid": true, "metrics": { "...": "..." } }
  ],
  "ranking": ["heuristic_3d_bpp_v1", "first_fit_decreasing_3d"],
  "ranking_explanation": "Ranking: (1) soluciones válidas antes que inválidas; (2) mayor volume_utilization; (3) menor items_unpacked; (4) menor containers_used; (5) menor execution_time_seconds.",
  "details": { "engines_total": 2, "engines_valid": 2, "best_engine": "heuristic_3d_bpp_v1" }
}
```

## `GET /api/v1/services`

Devuelve los **descriptores publicables** de cada servicio operativo, listos para
un espacio de datos (tipo de problema, algoritmos, motor, licencia, formatos I/O,
restricciones soportadas/no soportadas, métricas, endpoints, trazabilidad y
limitaciones).

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
