# Guía de Implementación de Algoritmos

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md).

## Propósito

Esta guía establece el proceso para implementar y registrar nuevos algoritmos en el sistema. Cada algoritmo nuevo debe quedar ejecutable mediante:

```
POST /api/v1/algorithms/{algorithm_name}/execute
```

El algoritmo debe cumplir con el contrato homogéneo correspondiente a su tipo de problema y **no debe contener valores hardcodeados** de instancia: toda la información deriva del input normalizado.

Este diseño alimenta el **sistema de benchmark** (misma entrada, mismo validador, mismas métricas, modos offline y online), no un espacio de datos distribuido.

---

## Contratos Homogéneos por Tipo de Problema

| Tipo de Problema | Esquema de Entrada | Esquema de Salida | Validación y Métricas |
|------------------|-------------------|-------------------|----------------------|
| `3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION`, `STACKING_AWARE` | `PackAlgorithmInput` | `AlgorithmExecuteResponse.solution` (`PackingSolution`) | `validation_report`, `metrics` (DEFAULT_METRICS) |
| `CARTONIZATION` | `CartonizationAlgorithmInput` | `AlgorithmExecuteResponse` + `cartonization.*` | `solution.validation_report`, `solution.metrics` |

### Consideraciones

- Los parámetros del algoritmo se especifican en el campo `parameters` del cuerpo de la petición (no en la URL).
- Si el algoritmo soporta múltiples `problem_type`, el campo `problem_type` es **obligatorio** (estrategia de diseño A3).

---

## Checklist de Implementación

Al añadir un algoritmo con nombre `{name}`, verificar cada uno de los siguientes ítems:

### 1. Núcleo del Algoritmo

| # | Archivo | Acción |
|:-:|---------|--------|
| 1.1 | `src/packing_services/algorithms/{name}.py` | Crear clase `{Name}` con `METADATA` y método `run(problem)` |
| 1.2 | `src/packing_services/algorithms/_*.py` | Implementar motor reutilizable (sin IDs ni dimensiones fijas) |
| 1.3 | `src/packing_services/algorithms/registry.py` | Añadir `register_algorithm({Name}())` |
| 1.4 | Catálogo `future` | Eliminar entrada duplicada en `improvement.py`, `layer_based_3d.py`, etc. si pasa a `implemented` |

### 2. API y Ejecución

| # | Archivo | Acción |
|:-:|---------|--------|
| 2.1 | `src/packing_services/services/algorithm_execution_service.py` | Sin cambio si utiliza pack o cartonization estándar |
| 2.2 | `src/packing_services/services/algorithm_input_service.py` | Añadir parámetros por defecto en `_ALGORITHM_PARAMETERS` o `_IMPROVEMENT_ALGORITHMS` |
| 2.3 | `src/packing_services/api/routes/algorithm_execute.py` | Sin cambio (path genérico) |
| 2.4 | `src/packing_services/services/metadata_service.py` | Verificar `ENDPOINTS` (ya genérico) |

### 3. Descubrimiento (Catálogo API)

| # | Archivo | Acción |
|:-:|---------|--------|
| 3.1 | `GET /api/v1/algorithms/{name}` | Automático vía `AlgorithmInputService.enrich_metadata()` |
| 3.2 | `GET /api/v1/algorithms/{name}/input-example` | Automático si existe ejemplo en `examples/` o builder |
| 3.3 | `DataspaceService` | No modificar salvo solicitud explícita (despriorizado) |

### 4. Ejemplos y Tests

| # | Archivo | Acción |
|:-:|---------|--------|
| 4.1 | `examples/algorithm_execute_*.json` | Reutilizar por tipo o añadir `{name}_execute.json` si es necesario |
| 4.2 | `tests/test_{name}.py` | Crear o ampliar familia existente: validez, determinismo, parámetros desde input |
| 4.3 | `tests/test_algorithm_execute_api.py` | Añadir caso parametrizado por algoritmo + `problem_type` |
| 4.4 | `tests/test_algorithm_registry.py` | Verificar presencia e `is_executable` |

### 5. Benchmark y Comparación

| # | Archivo | Acción |
|:-:|---------|--------|
| 5.1 | `src/packing_services/benchmark/profiles.py` | Añadir a perfil `constructive`, `hybrid` o `improvement` según corresponda |
| 5.2 | `examples/benchmark_*_request.json` | Actualizar si el notebook utiliza engines explícitos |
| 5.3 | `tests/test_benchmark_profiles.py` | Verificar que el perfil contenga ≥2 motores ejecutables |

### 6. Notebooks Didácticos

| # | Archivo | Acción |
|:-:|---------|--------|
| 6.1 | `notebooks/_shared/loaders.py` | Actualizar `COMPARABLE_*_ENGINES` y builders si aplica |
| 6.2 | `notebooks/_build_notebooks.py` | Añadir narrativa o demo opcional |
| 6.3 | Regenerar | Ejecutar `python notebooks/_build_notebooks.py` |
| 6.4 | Validar | Ejecutar `MPLBACKEND=Agg python notebooks/_execute_all.py` |

### 7. Documentación

| # | Archivo | Acción |
|:-:|---------|--------|
| 7.1 | `docs/algorithm_catalog.md` | Añadir fila en tabla ejecutando `python scripts/regenerate_algorithm_catalog.py` |
| 7.2 | `docs/roadmap.md` | Marcar como completado (✅) si corresponde |
| 7.3 | `docs/api_examples.md` | Añadir curl + JSON si el flujo es nuevo |
| 7.4 | `README.md` | Actualizar solo si cambia el objetivo, el conteo o los endpoints canónicos |

---

## Historial de Implementación por Fases

### Fase A

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `maximal_spaces_3d` | `_maximal_spaces.py` | Constructivo |
| `relocation_improvement` | `_compaction.relocation_pass` | Mejora |
| `swap_improvement` | `_improvement_ops.py` | Mejora |
| `orientation_improvement` | `_improvement_ops.py` | Mejora |
| `bin_reduction` | `_improvement_ops.py` | Mejora |

### Fase B

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `multi_box_cartonization` | greedy multi-caja + `ExtremePointPacker` | Cartonization |
| `wall_building_3d` | `_wall_building.py` | Container Loading |
| `py3dbp_adapter` | adaptador externo (dependencia opcional) | 3D-BPP baseline |

### Fase C

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `layer_based_palletization` | `_layer_pallet.py` | Palletization |
| `stack_based_palletization` | `_stack_pallet.py` | Palletization / Stacking-aware |
| `stacking_aware_constructive` | `_stack_pallet.py` (estabilidad + load_bearing) | Stacking-aware |

**Servicios añadidos:** `POST /api/v1/pack/palletization`, `POST /api/v1/pack/stacking-aware`

**Validador ampliado:** comprobación `LOAD_BEARING` cuando `constraints.load_bearing=true`

### Fase D

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `simulated_annealing_3d_bpp` | `_metaheuristic_searches.run_simulated_annealing` | Metaheurística |
| `genetic_algorithm_3d_bpp` | `_metaheuristic_searches.run_genetic_algorithm` | Metaheurística |
| `grasp_3d_bpp` | `_metaheuristic_searches.run_grasp` | Metaheurística |
| `tabu_search_3d_bpp` | `_metaheuristic_searches.run_tabu_search` | Metaheurística |
| `lns_3d_bpp` | `_metaheuristic_searches.run_lns` | Metaheurística |
| `vns_3d_bpp` | `_metaheuristic_searches.run_vns` | Metaheurística |
| `aco_3d_bpp` | `_metaheuristic_searches.run_aco` | Metaheurística |

**Motor compartido:** `_metaheuristic_core.py` (codificación por permutación + `sort_strategy=input_order`)

**Perfil de benchmark:** `3D_BPP/metaheuristic`

---

## Packing Online

**Estado: Operativo**

### Algoritmos Solo-Online

- `online_3d_bpp_heuristic`
- `drl_policy_3d_bpp`

### Características

- Utilizan el mismo `PackAlgorithmInput` o wrapper BED-BPP
- Campo `packing_modes` en metadata
- Bucle de ejecución en `src/packing_services/online/`
- Parámetro `parameters.model_path` para política aprendida
- Defaults de producción: `mlp_v1_p1s1.pt` con p=1 s=1

> **Importante:** No modificar el encoder v1 ni el bucle para el execute de producto.

---

## Principios de Diseño (Evitar Hardcoding)

| Aspecto | Implementación Correcta |
|---------|------------------------|
| Orden de ítems | Utilizar `parameters.sort_strategy` → `SortStrategy` |
| Constructivo base en híbridos | Utilizar `parameters.base_algorithm` o default por `problem_type` (`_constructive_runner.default_base_algorithm`) |
| Pases y límites | Utilizar `parameters.compaction_passes`, `relocation_passes`, `max_swap_attempts`, etc. con defaults razonables |
| Contenedores e ítems | Siempre utilizar `problem.containers`, `problem.items` expandidos |
| Validación | Utilizar `build_solution` + validador geométrico existente; mismas `Metrics` para todos |
