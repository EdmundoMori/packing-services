# Arquitectura del Sistema

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md). Para las prioridades del proyecto, consultar [`roadmap.md`](roadmap.md).

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas:

- **Misma entrada:** formato de datos unificado para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo.
- **Mismas métricas:** indicadores de rendimiento calculados uniformemente.

El código está organizado para **homogeneizar la ejecución, validación y comparación** de algoritmos. El concepto de espacio de datos distribuido no estructura estas capas.

---

## Organización en Capas

El sistema utiliza una arquitectura en capas con **dependencias unidireccionales**: las capas superiores dependen de las inferiores, pero nunca al revés.

```
api ── services ── algorithms ─┬─ validation ─┐
                               ├─ metrics ─────┤
                               ├─ adapters     │
                               ├─ datasets     │
                               └─ online       │
                                               │
              benchmark ── schemas ── domain ──┘
                                     │
                                   utils
```

---

## Descripción de las Capas

### Capa `domain/`

Núcleo del sistema. Contiene los modelos fundamentales sin dependencias de framework.

| Archivo | Contenido |
|---------|-----------|
| `enums.py` | Vocabulario compartido: `ProblemType`, `AlgorithmFamily`, `AlgorithmStatus`, `Constraint`, `Severity`, `SolutionStatus` y estrategias de ordenamiento |
| `geometry.py` | Primitivas geométricas AABB deterministas y sin estado: contención, solapamiento, orientaciones únicas y superficie de soporte. Es el componente central de la lógica de packing y el más testeado |
| `models.py` | Modelos Pydantic canónicos: `Item`, `Container`, `ConstraintFlags`, `PackedItem`, `Metrics`, `Violation`, `ValidationReport`, `PackingProblem`, `PackingSolution`, entre otros |

### Capa `schemas/`

Contratos de la API REST. Reutiliza los modelos de dominio.

| Archivo | Contenido |
|---------|-----------|
| `requests.py` | `PackRequest`, `ValidateRequest`, `BenchmarkRequest`, `PackAlgorithmInput`, `CartonizationAlgorithmInput`. Incluye la expansión de `quantity` en ítems individuales con identificador único (`I1#1`, `I1#2`, etc.) |
| `responses.py` | Respuestas de salud, metadata, validación, benchmark y `AlgorithmExecuteResponse` (salida homogénea por algoritmo) |

### Capa `validation/`

Servicio de validación de soluciones de packing, independiente del algoritmo que las genera.

La clase `PackingValidator` verifica:
- Contención de ítems dentro del contenedor
- Ausencia de solapamiento entre ítems
- Cumplimiento del peso máximo
- Validez de la orientación aplicada
- Ausencia de identificadores duplicados
- Coherencia de ítems no empacados
- Estabilidad básica (opcional)

### Capa `metrics/`

La función `compute_metrics` deriva las métricas comunes desde la solución y la instancia, garantizando que cualquier motor produzca cifras comparables.

### Capa `algorithms/`

Contiene las implementaciones de algoritmos y la infraestructura para su registro y ejecución.

| Archivo | Contenido |
|---------|-----------|
| `metadata.py` | Clase `AlgorithmMetadata` (ficha descriptiva homogénea) |
| `base.py` | Interfaz `PackingAlgorithm` y función `build_solution` (valida, calcula métricas y construye metadata de ejecución) |
| `registry.py` | Clase `AlgorithmRegistry` (listar, filtrar, describir, ejecutar) |

**Motores compartidos generalizables:**

| Archivo | Función |
|---------|---------|
| `_constructive.py`, `_constructive_runner.py` | Colocación constructiva |
| `_extreme_points.py` | Puntos extremos y estrategia best-fit |
| `_maximal_spaces.py` | Espacios vacíos máximos (guillotina) |
| `_compaction.py`, `_improvement_ops.py`, `_improvement_runner.py` | Mejora local |
| `_metaheuristic_core.py`, `_metaheuristic_searches.py` | Metaheurísticas 3D-BPP |

**Inventario de algoritmos:**
- 31 algoritmos implementados (constructivos, mejora, híbridos, metaheurísticas, cartonization, palletization, stacking, heurístico online y política aprendida)
- Registrados en `registry.py`
- Catálogo completo en [`algorithm_catalog.md`](algorithm_catalog.md)
- Metadatos `future` y `adapter` para métodos exactos y adaptadores externos

### Capa `online/`

Implementa el bucle de packing online (`run_online_loop`) con soporte para:
- Presupuesto de información (parámetros p/s)
- Puntos extremos
- Máscara del validador
- Políticas greedy y aprendida

| Archivo | Contenido |
|---------|-----------|
| `loop.py`, `budget.py`, `mask.py`, `policies.py`, `session.py`, `params.py` | Componentes del bucle online |
| `features.py` | Encoder v1 (`FEATURE_VERSION=1`, `FEATURE_DIM=35`) |
| `learned/` | Loader de checkpoints `packing-services-online-policy` v1; arquitectura MLP `Linear(35,64) → ReLU → Linear(64,1)`; defaults de producción en `learned/production.py` (`mlp_v1_p1s1_ppo.pt` con opción API `policy=rl`, p=1 s=1 — pesos vigentes = actor BC, no mejora PPO demostrada; `mlp_v1_p3s2.pt` para cinta) |

> **Nota:** El modo `packing_mode=offline` no utiliza esta capa. El entrenamiento y el cierre del subproyecto están en `online_policy_ml/` ([informe](../online_policy_ml/docs/informe_cierre_rl_online.md)); el código de producción solo carga artefactos.

### Capa `adapters/`

Adaptadores a motores de empaquetado externos.

La clase `ExternalAdapter` comparte interfaz con los algoritmos locales (`PackingAlgorithm`), pero su ejecución depende de una dependencia o motor externo. Si el motor no está disponible, el método `run()` lanza `AdapterUnavailableError` con instrucciones (mapeado a HTTP 503).

Actualmente solo `py3dbp_adapter` es ejecutable (si se instala `py3dbp`); el resto son stubs documentados.

### Capa `datasets/`

Conversión de entradas externas al contrato interno.

El módulo `bed_bpp.py` traduce pedidos BED-BPP (`item_sequence` + target) hacia `PackAlgorithmInput` o `BenchmarkRequest`, mapeando `sequence` hacia `arrival_index`. El campo `packing_mode` determina si se permite reordenar (offline) o se respeta el orden de llegada (online).

### Capa `benchmark/`

Sistema de comparación de algoritmos.

Incluye perfiles por `problem_type` y el experimento conjunto `joint_single_container.py` (un euro-pallet, `packing_mode` offline u online, varios tipos de servicio, mismo validador).

### Capa `services/`

Orquestación de registro, validador y métricas.

| Servicio | Responsabilidad |
|----------|-----------------|
| `AlgorithmExecutionService` | Ejecuta algoritmo por nombre (`/algorithms/{name}/execute`); normaliza BED-BPP si aplica |
| `AlgorithmInputService` | Proporciona esquemas de entrada, ejemplos y endpoint por algoritmo |
| `AlgorithmCatalogService` | Listado y detalle del catálogo |
| `PackingService` | Endpoints legacy `/pack/*` |
| `CartonizationService`, `PalletizationService`, `StackingAwareService` | Orquestación por tipo de problema |
| `ValidationService` | Validación independiente |
| `BenchmarkService` | Comparación multi-algoritmo por `problem_type` |
| `MetadataService` | Metadatos globales del servicio |
| `DataspaceService` | Descriptores `GET /services` (despriorizado) |

### Capa `api/`

Capa de presentación REST con FastAPI.

- `main.py`: aplicación FastAPI y manejadores de errores de dominio → HTTP
- `routes/`: routers modulares
  - `algorithm_execute.py`: patrón canónico de ejecución
  - `datasets.py`: operaciones con datasets
  - `benchmark.py`: incluye `POST /benchmark/joint-single-container`

### Capa `utils/`

Utilidades transversales.

| Archivo | Contenido |
|---------|-----------|
| `logging.py` | Configuración de logging |
| `timing.py` | Medición de tiempos (incluye `Deadline` para futuros límites de tiempo) |
| `errors.py` | Jerarquía de errores mapeada a códigos HTTP |

---

## Flujos de Ejecución

### Flujo Canónico por Algoritmo

```
PackAlgorithmInput | CartonizationAlgorithmInput | wrapper BED-BPP (JSON)
    │
    ▼
AlgorithmExecutionService.execute(name, input)
    │
    ▼ (si BED-BPP)
datasets.bed_bpp.normalize_execute_payload
    │
    ▼
schemas → PackingProblem (expande quantity, normaliza)
    │
    ▼
AlgorithmRegistry.execute(name, problem)
    │
    ▼
PackingAlgorithm.run()
    │
    ▼
build_solution()  ←── valida + métricas + metadata
    │
    ▼
AlgorithmExecuteResponse (JSON)
```

### Flujo para Packing Online

Cuando `packing_mode=online` y el algoritmo es `drl_policy_3d_bpp` (o se utiliza `POST /api/v1/online/learned/execute`), el método `run()` del algoritmo invoca `run_online_loop` con la política del checkpoint.

El heurístico `online_3d_bpp_heuristic` utiliza el mismo bucle pero con política greedy.

La salida pasa por el mismo `build_solution` (validador + métricas), garantizando homogeneidad.

### Flujo Legacy (`/pack/*`)

```
PackRequest (JSON)
    │
    ▼
schemas.PackRequest.to_problem()
    │
    ▼
PackingService.pack()
    │
    ▼
AlgorithmRegistry.execute(name, problem)
    │
    ▼
build_solution()
    │
    ▼
PackingSolution (JSON)
```

Los endpoints `/pack/3d-bpp`, `/pack/container-loading`, `/pack/cartonization`, `/pack/palletization` y `/pack/stacking-aware` permanecen por retrocompatibilidad. El patrón preferido es `/algorithms/{name}/execute`.

---

## Principios de Diseño

### Separación de Responsabilidades

**Optimización / Validación / Comparación:** El validador es independiente del algoritmo que genera la solución. Esto permite comparar metodologías de forma objetiva.

### Homogeneidad

Toda salida pasa por `build_solution`, de modo que tanto motores internos como externos producen resultados directamente comparables.

### Generalización

Los motores compartidos (`_constructive_runner`, `_improvement_runner`, `_maximal_spaces`) están parametrizados por instancia arbitraria, sin acoplamiento a casos de demostración concretos.

### Extensibilidad sin Sobreingeniería

- Añadir un algoritmo = crear una clase con su `metadata` y registrarla
- Añadir un motor externo = implementar un adaptador

### Trazabilidad

Cada solución incluye `execution_metadata` con información del algoritmo, familia, parámetros, semilla y versión del servicio.
