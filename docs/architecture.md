# Arquitectura

Documento hijo de [`../README.md`](../README.md). Índice: [`README.md`](README.md).
Prioridades: [`roadmap.md`](roadmap.md).

El código está organizado para **homogeneizar ejecución, validación y
comparación**. El espacio de datos no estructura estas capas.

`packing-services` usa capas con dependencias unidireccionales
(las superiores dependen de las inferiores, nunca al revés).

```
api ── services ── algorithms ─┬─ validation ─┐
                               ├─ metrics ─────┤
                               ├─ adapters     │
                               └─ datasets     │
                                               │
              benchmark ── schemas ── domain ──┘
                                     │
                                   utils
```

## Capas

### `domain/`
Núcleo común, sin dependencias de framework.

- `enums.py`: vocabulario compartido (`ProblemType`, `AlgorithmFamily`,
  `AlgorithmStatus`, `Constraint`, `Severity`, `SolutionStatus`, estrategias).
- `geometry.py`: primitivas AABB deterministas y sin estado (contención,
  solapamiento, orientaciones únicas, superficie de soporte). Es el corazón de
  la lógica de packing y el punto más testeado.
- `models.py`: modelos Pydantic canónicos (`Item`, `Container`,
  `ConstraintFlags`, `PackedItem`, `Metrics`, `Violation`, `ValidationReport`,
  `PackingProblem`, `PackingSolution`, ...).

### `schemas/`
Contratos de la API. Reutilizan los modelos de dominio.

- `requests.py`: `PackRequest`, `ValidateRequest`, `BenchmarkRequest`,
  `PackAlgorithmInput`, `CartonizationAlgorithmInput`. Incluye la expansión de
  `quantity` en ítems individuales con id único (`I1#1`, `I1#2`...).
- `responses.py`: respuestas de salud, metadata, validación, benchmark y
  `AlgorithmExecuteResponse` (salida homogénea por algoritmo).

### `validation/`
Packing Validation Service propio. `PackingValidator` comprueba contención,
no solapamiento, peso máximo, orientación válida, duplicados, coherencia de
ítems no empacados y (opcional) estabilidad básica.

### `metrics/`
`compute_metrics` deriva las métricas comunes desde la solución y la instancia,
de forma que cualquier motor produce cifras comparables.

### `algorithms/`
- `metadata.py`: `AlgorithmMetadata` (ficha homogénea).
- `base.py`: interfaz `PackingAlgorithm` + `build_solution` (valida, calcula
  métricas y construye la metadata de ejecución para todos los algoritmos).
- `registry.py`: `AlgorithmRegistry` (listar, filtrar, describir, ejecutar).
- Motores compartidos generalizables:
  - `_constructive.py`, `_constructive_runner.py`: colocación constructiva.
  - `_extreme_points.py`: puntos extremos y best-fit.
  - `_maximal_spaces.py`: espacios vacíos máximos (guillotina).
  - `_compaction.py`, `_improvement_ops.py`, `_improvement_runner.py`: mejora local.
  - `_metaheuristic_core.py`, `_metaheuristic_searches.py`: metaheurísticas 3D-BPP.
- **29 algoritmos implementados** (constructivos, mejora, híbridos, metaheurísticas, cartonization, palletization, stacking),
  registrados en `registry.py`. Catálogo completo en `docs/algorithm_catalog.md`.
- Metadatos `future` / `adapter`: métodos exactos, online/DRL, adaptadores externos, etc.

### `adapters/`
Adaptadores a motores externos. `ExternalAdapter` comparte interfaz con los
algoritmos locales pero su ejecución depende de una dependencia/motor externo.
Si no está disponible, `run` lanza `AdapterUnavailableError` con instrucciones.
Solo `py3dbp_adapter` es ejecutable si se instala `py3dbp`; el resto son stubs.

### `datasets/`
Conversión de entradas externas al contrato interno. `bed_bpp.py` traduce
pedidos BED-BPP (`item_sequence` + target) a `PackAlgorithmInput` /
`BenchmarkRequest` sin cambiar los algoritmos.

### `benchmark/`
Perfiles por `problem_type` y el experimento conjunto
`joint_single_container.py` (un euro-pallet, secuencia `input_order`,
varios tipos de servicio, mismo validador).

### `services/`
Orquestan registro + validador + métricas:

| Servicio | Rol |
|----------|-----|
| `AlgorithmExecutionService` | Ejecuta un algoritmo por nombre (`/algorithms/{name}/execute`); normaliza BED-BPP si aplica |
| `AlgorithmInputService` | Esquemas de entrada, ejemplos y endpoint por algoritmo |
| `AlgorithmCatalogService` | Listado y detalle del catálogo |
| `PackingService` | Endpoints legacy `/pack/*` |
| `CartonizationService` / `PalletizationService` / `StackingAwareService` | Orquestación por tipo |
| `ValidationService` | Validación independiente |
| `BenchmarkService` | Comparación multi-algoritmo por `problem_type` |
| `MetadataService` | Metadatos del servicio |
| `DataspaceService` | Descriptores `GET /services` (despriorizado; no es línea crítica) |

### `api/`
FastAPI: `main.py` (app + manejadores de errores de dominio → HTTP) y routers en
`routes/`. Patrón canónico de ejecución: `algorithm_execute.py`. Datasets:
`routes/datasets.py`. Benchmark conjunto: `POST /benchmark/joint-single-container`.

### `utils/`
`logging.py`, `timing.py` (incluye `Deadline` para futuros límites de tiempo),
`errors.py` (jerarquía de errores mapeada a códigos HTTP).

## Flujo de ejecución por algoritmo (canónico)

```
PackAlgorithmInput | CartonizationAlgorithmInput | wrapper BED-BPP (JSON)
  → AlgorithmExecutionService.execute(name, input)
  → (si BED-BPP) datasets.bed_bpp.normalize_execute_payload
  → schemas → PackingProblem (expande quantity, normaliza)
  → AlgorithmRegistry.execute(name, problem)
  → PackingAlgorithm.run()
  → build_solution()                      # valida + métricas + metadata
  → AlgorithmExecuteResponse (JSON)
```

## Flujo legacy (`/pack/*`)

```
PackRequest (JSON)
  → schemas.PackRequest.to_problem()
  → PackingService.pack()
  → AlgorithmRegistry.execute(name, problem)
  → build_solution()
  → PackingSolution (JSON)
```

Los endpoints `/pack/3d-bpp`, `/pack/container-loading`, `/pack/cartonization`,
`/pack/palletization` y `/pack/stacking-aware` permanecen por retrocompatibilidad;
el patrón preferido es `/algorithms/{name}/execute`.

## Principios de diseño

- **Separación optimización / validación / comparación** (brecha del estado del
  arte): el validador es independiente del algoritmo que generó la solución.
- **Homogeneidad**: toda salida pasa por `build_solution`, de modo que motores
  internos y externos son directamente comparables.
- **Generalización**: motores compartidos (`_constructive_runner`, `_improvement_runner`,
  `_maximal_spaces`) parametrizados por instancia arbitraria; sin acoplamiento a
  casos demo concretos.
- **Extensibilidad sin sobreingeniería**: añadir un algoritmo = crear una clase
  con su `metadata` y registrarla; añadir un motor externo = un adaptador.
- **Trazabilidad**: cada solución incluye `execution_metadata` (algoritmo,
  familia, parámetros, semilla, versión del servicio).
