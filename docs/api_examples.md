# Ejemplos de Uso de la API

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md).

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas: misma entrada, mismo validador y mismas métricas, tanto en `packing_mode=offline` como en `packing_mode=online`.

## Organización de este Documento

Los archivos JSON de ejemplo se encuentran en el directorio `examples/`. Este documento cubre:

1. Ejecución canónica de algoritmos
2. Formato BED-BPP
3. Packing online con política aprendida
4. Experimento conjunto
5. Endpoints legacy
6. Validación independiente
7. Sistema de benchmark
8. Consulta del catálogo

> **Nota:** El endpoint `GET /api/v1/services` genera descriptores de servicios pero no forma parte del objetivo principal del proyecto.

---

## 1. Ejecución Canónica de Algoritmos

### Endpoint Principal

```
POST /api/v1/algorithms/{algorithm_name}/execute
```

El nombre del algoritmo se especifica en la URL. El cuerpo de la petición contiene el input normalizado por tipo de problema, **sin** el campo `algorithm`.

### Tipos de Problema de Empaquetado

Aplica a: `3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION`, `STACKING_AWARE`.

**Ejemplo de petición** (`examples/algorithm_execute_3d_bpp.json`):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/heuristic_3d_bpp_v1/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json
```

**Estructura del JSON de entrada:**

```json
{
  "problem_type": "3D_BPP",
  "request_id": "example-001",
  "containers": [
    {
      "id": "C1",
      "length": 120,
      "width": 80,
      "height": 100,
      "max_weight": 1000
    }
  ],
  "items": [
    {
      "id": "I1",
      "length": 40,
      "width": 40,
      "height": 40,
      "weight": 10,
      "quantity": 4,
      "allowed_orientations": "all"
    }
  ],
  "constraints": {
    "non_overlap": true,
    "containment": true,
    "allow_rotation": true,
    "max_weight": true
  },
  "objective": "maximize_volume_utilization",
  "parameters": {
    "sort_strategy": "volume_desc",
    "position_strategy": "bottom_left_back"
  }
}
```

> **Nota:** Si el algoritmo soporta varios `problem_type`, el campo es **obligatorio** (estrategia de diseño A3).

**Ejemplo con metaheurística** (requiere `random_seed` e `iterations`):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/simulated_annealing_3d_bpp/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_3d_bpp.json
```

### Ejemplos Adicionales por Tipo

| Tipo de Problema | Archivo de Ejemplo | Algoritmo Recomendado |
|------------------|-------------------|----------------------|
| `CONTAINER_LOADING` | `algorithm_execute_container_loading.json` | `weight_aware_container_loading` |
| `SINGLE_CONTAINER_LOADING` | `algorithm_execute_single_container.json` | `best_fit_decreasing_3d` |
| Mejora local | `algorithm_execute_improvement.json` | `solution_compaction` |

### Estructura de la Respuesta

Todas las ejecuciones retornan **`AlgorithmExecuteResponse`** (salida homogénea):

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
    "metrics": {
      "volume_utilization": 0.7,
      "items_packed": 12
    },
    "validation_report": {
      "is_valid": true,
      "violations": []
    },
    "execution_metadata": {
      "algorithm": "heuristic_3d_bpp_v1"
    }
  },
  "cartonization": null
}
```

Para problemas de cartonization, el campo `cartonization` incluye `selected_box_id` y `evaluated_boxes`; la solución de packing se encuentra en `solution`.

### Consulta de Contratos por Algoritmo

```bash
# Obtener metadatos del algoritmo
GET /api/v1/algorithms/heuristic_3d_bpp_v1

# Obtener ejemplo de entrada
GET /api/v1/algorithms/heuristic_3d_bpp_v1/input-example?problem_type=3D_BPP
```

---

## 2. Formato BED-BPP

El formato BED-BPP permite utilizar datos de pedidos reales. La conversión al formato interno es automática.

### Muestra y Conversión

```bash
# Obtener muestra del dataset
GET /api/v1/datasets/bed-bpp/sample

# Convertir formato
POST /api/v1/datasets/bed-bpp/convert
```

### Ejecución con Wrapper BED-BPP

El servicio normaliza automáticamente hacia `containers` + `items`:

```json
{
  "input_format": "bed_bpp",
  "order_id": "00100001",
  "orders": {},
  "problem_type": "PALLETIZATION",
  "packing_mode": "offline"
}
```

### Holdout de Producto

El archivo `examples/5_bed-bpp.json` contiene el **holdout de producto** (nunca utilizado para entrenamiento).

Identificadores disponibles: `00100001`, `00100002`, `00100003`, `00100004`, `00100408`.

### Uso en la Interfaz Web

- **Ejecutar:** pestaña BED-BPP
- **Benchmark:** bloque "Instancia BED-BPP"

---

## 3. Packing Online con Política Aprendida

### Endpoints Disponibles

| Endpoint | Comportamiento |
|----------|----------------|
| `POST /api/v1/algorithms/drl_policy_3d_bpp/execute` | Ejecución canónica |
| `POST /api/v1/online/learned/execute` | Fuerza `packing_mode=online` |

### Configuración de Modelos

Si no se especifica `model_path`, se utiliza el MLP de producción con configuración **p=1 s=1**.

> **Importante:** Un `model_path` vacío (`""`) no realiza fallback al greedy. Los archivos `.pt` requieren `pip install 'packing-services[torch]'`.

| Régimen | `model_path` | `lookahead_p` | `select_s` |
|---------|--------------|---------------|------------|
| O3DBP (default) | `online_policy_ml/artifacts/models/mlp_v1_p1s1.pt` | 1 | 1 |
| Cinta (receding-horizon) | `online_policy_ml/artifacts/models/mlp_v1_p3s2.pt` | 3 | 2 |
| Linear (sin PyTorch) | `online_policy_ml/artifacts/models/linear_v1.json` | 1 | 1 |
| Placeholder de prueba | `examples/online_policy_linear_v1.json` | 1 | 1 |

### Ejemplo de Petición

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/drl_policy_3d_bpp/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_online_learned.json
```

**Estructura del JSON** (holdout de producto `00100408`):

```json
{
  "input_format": "bed_bpp",
  "order_id": "00100408",
  "orders": {},
  "problem_type": "PALLETIZATION",
  "packing_mode": "online",
  "parameters": {
    "model_path": "online_policy_ml/artifacts/models/mlp_v1_p1s1.pt",
    "lookahead_p": 1,
    "select_s": 1
  }
}
```

**Configuración para cinta:** mismo wrapper con `model_path` apuntando a `mlp_v1_p3s2.pt`, `lookahead_p=3` y `select_s=2`.

### Endpoint Dedicado

```bash
curl -X POST http://localhost:8000/api/v1/online/learned/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_online_learned.json
```

---

## 4. Experimento Conjunto

### Descripción

Compara `3D_BPP`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION` y `STACKING_AWARE` sobre el pedido más pequeño de `examples/5_bed-bpp.json`, forzado a euro-pallet.

- Modo predeterminado: `packing_mode=offline`
- Para modo online: especificar `"packing_mode": "online"`

> **Nota:** Cartonization no participa en este experimento porque selecciona caja del catálogo en lugar de recibir el contenedor fijado.

### Ejecución

```bash
# Mediante API
curl -X POST http://localhost:8000/api/v1/benchmark/joint-single-container \
  -H "Content-Type: application/json" \
  -d '{}'

# Mediante script
PYTHONPATH=src python scripts/run_joint_single_container.py
```

---

## 5. Cartonization

### Descripción

Cartonization selecciona **una** caja de un catálogo para empaquetar un pedido.

**Ejemplo de petición** (`examples/algorithm_execute_cartonization.json`):

```bash
curl -X POST http://localhost:8000/api/v1/algorithms/smallest_feasible_box/execute \
  -H "Content-Type: application/json" \
  -d @examples/algorithm_execute_cartonization.json
```

**Estructura del JSON:**

```json
{
  "request_id": "carton-001",
  "items": [
    {
      "id": "SKU1",
      "length": 20,
      "width": 15,
      "height": 10,
      "weight": 2,
      "quantity": 3
    }
  ],
  "boxes": [
    {
      "id": "BOX_M",
      "length": 40,
      "width": 30,
      "height": 20,
      "max_weight": 30
    }
  ],
  "constraints": {
    "non_overlap": true,
    "containment": true,
    "allow_rotation": true,
    "max_weight": true
  },
  "parameters": {
    "sort_strategy": "volume_desc"
  }
}
```

La respuesta utiliza `AlgorithmExecuteResponse`; el campo `cartonization.selected_box_id` indica la caja elegida.

---

## 6. Endpoints Legacy

Los siguientes endpoints permanecen por retrocompatibilidad. Se recomienda utilizar `/algorithms/{name}/execute`.

### `POST /api/v1/pack/3d-bpp`

**Ejemplo de petición** (`examples/3d_bpp_basic_request.json`):

```json
{
  "problem_type": "3D_BPP",
  "request_id": "example-001",
  "containers": [
    {
      "id": "C1",
      "length": 120,
      "width": 80,
      "height": 100,
      "max_weight": 1000
    }
  ],
  "items": [
    {
      "id": "I1",
      "length": 40,
      "width": 40,
      "height": 40,
      "weight": 10,
      "quantity": 4,
      "allowed_orientations": "all"
    }
  ],
  "constraints": {
    "non_overlap": true,
    "containment": true,
    "allow_rotation": true,
    "max_weight": true
  },
  "objective": "maximize_volume_utilization",
  "algorithm": {
    "name": "heuristic_3d_bpp_v1",
    "parameters": {
      "sort_strategy": "volume_desc",
      "position_strategy": "bottom_left_back"
    },
    "random_seed": null,
    "time_limit_seconds": 10
  }
}
```

**Estructura de la respuesta:**

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
  "validation_report": {
    "is_valid": true,
    "violations": []
  },
  "execution_metadata": {
    "algorithm": "heuristic_3d_bpp_v1",
    "algorithm_family": "constructive_heuristic",
    "parameters": { "sort_strategy": "volume_desc" },
    "random_seed": null,
    "service_version": "0.1.0"
  }
}
```

> **Nota:** Los ítems con `quantity > 1` se expanden internamente a identificadores únicos (`I1#1`, `I1#2`, etc.).

### `POST /api/v1/pack/container-loading`

**Ejemplo** (`examples/container_loading_request.json`):

El algoritmo es opcional; por defecto utiliza `weight_aware_container_loading`, que prioriza ítems más pesados respetando el peso máximo del contenedor.

```json
{
  "problem_type": "CONTAINER_LOADING",
  "request_id": "cl-001",
  "containers": [
    {
      "id": "TRUCK1",
      "length": 240,
      "width": 120,
      "height": 120,
      "max_weight": 500
    }
  ],
  "items": [
    {
      "id": "PALLET_A",
      "length": 80,
      "width": 60,
      "height": 100,
      "weight": 120,
      "quantity": 3
    }
  ],
  "algorithm": {
    "name": "weight_aware_container_loading",
    "parameters": { "sort_strategy": "weight_desc" }
  }
}
```

### `POST /api/v1/pack/cartonization`

**Ejemplo** (`examples/cartonization_request.json`):

```json
{
  "request_id": "carton-001",
  "items": [
    {
      "id": "SKU1",
      "length": 20,
      "width": 15,
      "height": 10,
      "weight": 2,
      "quantity": 3
    }
  ],
  "boxes": [
    {
      "id": "BOX_S",
      "length": 30,
      "width": 20,
      "height": 15,
      "max_weight": 20,
      "cost": 0.5
    },
    {
      "id": "BOX_M",
      "length": 40,
      "width": 30,
      "height": 20,
      "max_weight": 30,
      "cost": 0.8
    }
  ],
  "algorithm": { "name": "smallest_feasible_box" }
}
```

**Estructura de la respuesta:**

```json
{
  "request_id": "carton-001",
  "status": "success",
  "selected_box_id": "BOX_M",
  "algorithm_name": "smallest_feasible_box",
  "solution": {
    "packed_items": ["..."],
    "metrics": { "...": "..." },
    "validation_report": { "is_valid": true }
  },
  "evaluated_boxes": [
    {
      "box_id": "BOX_S",
      "fits_all": false,
      "items_packed": 2,
      "volume_utilization": 0.9
    },
    {
      "box_id": "BOX_M",
      "fits_all": true,
      "items_packed": 5,
      "volume_utilization": 0.62
    }
  ]
}
```

---

## 7. Validación Independiente

### `POST /api/v1/validate`

Permite validar soluciones generadas por cualquier motor.

**Ejemplo** (`examples/validation_request_invalid_overlap.json`) — dos ítems que se solapan:

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

---

## 8. Sistema de Benchmark

### `POST /api/v1/benchmark`

Compara varios motores sobre la **misma instancia**. Existen dos formas de especificar los motores:

1. **`profile`** (recomendado): conjunto estándar predefinido con ≥2 motores comparables.
2. **`engines`** explícito: lista manual (tiene prioridad si ambos están presentes).

### Consulta de Perfiles Disponibles

```bash
# Todos los perfiles
curl http://localhost:8000/api/v1/benchmark/profiles

# Filtrar por tipo de problema
curl "http://localhost:8000/api/v1/benchmark/profiles?problem_type=CARTONIZATION"
```

### Perfiles Estándar por Tipo de Problema

| `problem_type` | Perfil | Motores Comparados |
|----------------|--------|-------------------|
| `3D_BPP` | `constructive` | 4 heurísticas + `py3dbp_adapter` (opcional) |
| `3D_BPP` | `hybrid` | `best_fit` → `solution_compaction` → `constructive_plus_local_search` |
| `CONTAINER_LOADING` | `constructive` | `single_container_constructive`, `weight_aware`, `extreme_points_3d` |
| `CONTAINER_LOADING` | `improvement` | `weight_aware` + compactación + híbrido |
| `CARTONIZATION` | `box_selection` | `smallest_feasible_box`, `best_box_volume_utilization`, `first_fit_box`, `largest_feasible_box` |
| `SINGLE_CONTAINER_LOADING` | `constructive` | `single_container_constructive`, `best_fit`, `first_fit` |

### Ejemplo de Petición con Perfil

```bash
curl -X POST http://localhost:8000/api/v1/benchmark \
  -H "Content-Type: application/json" \
  -d @examples/benchmark_cartonization_request.json
```

El JSON solo requiere `problem_type`, `profile` y los datos correspondientes (`items`/`containers`/`boxes` según el tipo).

### Archivos de Ejemplo por Grupo

| Grupo | Archivo |
|-------|---------|
| `3D_BPP` constructivo | `examples/benchmark_3d_bpp_profile_request.json` |
| `3D_BPP` híbrido | `examples/benchmark_hybrid_request.json` |
| `3D_BPP` mejora | `examples/benchmark_improvement_request.json` |
| `3D_BPP` metaheurísticas | `examples/benchmark_metaheuristic_request.json` |
| `CONTAINER_LOADING` | `examples/benchmark_container_loading_request.json` |
| `CARTONIZATION` | `examples/benchmark_cartonization_request.json` |
| `SINGLE_CONTAINER_LOADING` | `examples/benchmark_single_container_request.json` |

> **Nota:** El ejemplo 3D-BPP utiliza 30 piezas y 2 contenedores, diseñado para mostrar diferencias claras de utilización.

### Estructura de la Respuesta

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
      "details": {
        "selected_box_id": "BOX_L",
        "evaluated_boxes": []
      }
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

---

## 9. Consulta del Catálogo de Algoritmos

### `GET /api/v1/algorithms`

Soporta múltiples filtros combinables:

```bash
# Solo algoritmos implementados
curl "http://localhost:8000/api/v1/algorithms?status=implemented"

# Por tipo de problema
curl "http://localhost:8000/api/v1/algorithms?problem_type=3D_BPP"

# Por familia de algoritmo
curl "http://localhost:8000/api/v1/algorithms?family=metaheuristic"

# Por modo de packing (offline oculta los solo-online)
curl "http://localhost:8000/api/v1/algorithms?packing_mode=online"

# Por restricción soportada
curl "http://localhost:8000/api/v1/algorithms?supported_constraint=max_weight"
```

---

## 10. Descriptores de Servicios (Despriorizado)

### `GET /api/v1/services`

Genera un catálogo de descriptores. **No forma parte del objetivo principal** del proyecto. Para más información, consultar [`roadmap.md`](roadmap.md) §5.

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

---

## Códigos de Error HTTP

| Código | Situación |
|--------|-----------|
| 422 | Entrada inválida (validación Pydantic o `InvalidInputError`) |
| 404 | Algoritmo inexistente |
| 400 | Algoritmo no ejecutable (estado `future`) |
| 503 | Adaptador externo no disponible (dependencia o motor ausente) |
| 500 | Error inesperado de ejecución |
