# Arquitectura

`packing-services` está organizado en capas con dependencias unidireccionales
(las capas superiores dependen de las inferiores, nunca al revés).

```
api ── services ── algorithms ─┬─ validation ─┐
                               ├─ metrics ─────┤
                               └─ adapters     │
                                               │
                        schemas ── domain ─────┘
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

- `requests.py`: `PackRequest`, `ValidateRequest`, `BenchmarkRequest`. Incluye la
  expansión de `quantity` en ítems individuales con id único (`I1#1`, `I1#2`...).
- `responses.py`: respuestas de salud, metadata, validación y benchmark.

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
- `_constructive.py`: motor constructivo compartido por las heurísticas.
- Implementados: `heuristic_3d_bpp.py`, `first_fit_decreasing_3d.py`.
- Catálogo (metadatos `future`/`stub`): `best_fit_decreasing_3d.py`,
  `extreme_points_3d.py`, `layer_based_3d.py`, `improvement.py`,
  `exact_reference.py`, `metaheuristics.py`.

### `adapters/`
Adaptadores a motores externos. `ExternalAdapter` comparte interfaz con los
algoritmos locales pero su ejecución depende de una dependencia/motor externo.
Si no está disponible, `run` lanza `AdapterUnavailableError` con instrucciones.

### `services/`
Orquestan registro + validador + métricas: `PackingService`,
`ValidationService`, `BenchmarkService`, `MetadataService`,
`AlgorithmCatalogService`.

### `api/`
FastAPI: `main.py` (app + manejadores de errores de dominio → HTTP) y routers en
`routes/`.

### `utils/`
`logging.py`, `timing.py` (incluye `Deadline` para futuros límites de tiempo),
`errors.py` (jerarquía de errores mapeada a códigos HTTP).

## Flujo de una petición de packing

```
PackRequest (JSON)
  → schemas.PackRequest.to_problem()      # expande quantity, normaliza
  → PackingService.pack()
  → AlgorithmRegistry.execute(name, problem)
  → PackingAlgorithm.run()                # heurística constructiva
  → build_solution()                      # valida + métricas + metadata
  → PackingSolution (JSON)
```

## Principios de diseño

- **Separación optimización / validación / comparación** (brecha del estado del
  arte): el validador es independiente del algoritmo que generó la solución.
- **Homogeneidad**: toda salida pasa por `build_solution`, de modo que motores
  internos y externos son directamente comparables.
- **Extensibilidad sin sobreingeniería**: añadir un algoritmo = crear una clase
  con su `metadata` y registrarla; añadir un motor externo = un adaptador.
- **Trazabilidad**: cada solución incluye `execution_metadata` (algoritmo,
  familia, parámetros, semilla, versión del servicio).
