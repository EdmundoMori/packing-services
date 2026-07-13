# Trazabilidad: implementar un algoritmo de extremo a extremo

Cada algoritmo nuevo debe quedar **publicable como servicio** vía
`POST /api/v1/algorithms/{algorithm_name}/execute`, con contrato homogéneo por
tipo de problema y **sin valores hardcodeados** de instancia (dimensiones, ids,
cantidades): todo debe derivarse del input normalizado.

## Contratos homogéneos por tipo de problema

| Tipo | Input (body) | Output | Validación / métricas |
|------|--------------|--------|------------------------|
| `3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING` | `PackAlgorithmInput` | `AlgorithmExecuteResponse.solution` (`PackingSolution`) | `validation_report`, `metrics` (DEFAULT_METRICS) |
| `CARTONIZATION` | `CartonizationAlgorithmInput` | `AlgorithmExecuteResponse` + `cartonization.*` | `solution.validation_report`, `solution.metrics` |

Parámetros del algoritmo van en `parameters` del body (no en la URL). Si el
algoritmo admite varios `problem_type`, el campo `problem_type` es obligatorio (A3).

## Checklist por algoritmo nuevo

Marca cada ítem al añadir un algoritmo `{name}`:

### 1. Núcleo del algoritmo

| # | Archivo | Acción |
|---|---------|--------|
| 1.1 | `src/packing_services/algorithms/{name}.py` | Clase `{Name}` + `METADATA` + `run(problem)` |
| 1.2 | `src/packing_services/algorithms/_*.py` | Motor reutilizable (sin ids/dimensiones fijos) |
| 1.3 | `src/packing_services/algorithms/registry.py` | `register_algorithm({Name}())` |
| 1.4 | Catálogo `future` duplicado | Quitar entrada en `improvement.py`, `layer_based_3d.py`, etc. si pasa a `implemented` |

### 2. API y ejecución

| # | Archivo | Acción |
|---|---------|--------|
| 2.1 | `src/packing_services/services/algorithm_execution_service.py` | Sin cambio si usa pack o cartonization estándar |
| 2.2 | `src/packing_services/services/algorithm_input_service.py` | Parámetros por defecto en `_ALGORITHM_PARAMETERS` / `_IMPROVEMENT_ALGORITHMS` |
| 2.3 | `src/packing_services/api/routes/algorithm_execute.py` | Sin cambio (path genérico) |
| 2.4 | `src/packing_services/services/metadata_service.py` | Verificar `ENDPOINTS` (ya genérico) |

### 3. Espacio de datos / descubrimiento

| # | Archivo | Acción |
|---|---------|--------|
| 3.1 | `src/packing_services/services/dataspace_service.py` | Descriptor auto vía `_algorithm_service_descriptors()` |
| 3.2 | `GET /api/v1/algorithms/{name}` | Auto vía `AlgorithmInputService.enrich_metadata()` |
| 3.3 | `GET /api/v1/algorithms/{name}/input-example` | Auto si hay ejemplo en `examples/` o builder |

### 4. Ejemplos y tests

| # | Archivo | Acción |
|---|---------|--------|
| 4.1 | `examples/algorithm_execute_*.json` | Reutilizar por tipo o añadir `{name}_execute.json` si hace falta |
| 4.2 | `tests/test_{name}.py` o ampliar familia | Validez, determinismo, parámetros desde input |
| 4.3 | `tests/test_algorithm_execute_api.py` | Caso parametrizado por algoritmo + `problem_type` |
| 4.4 | `tests/test_algorithm_registry.py` | Presencia y `is_executable` |

### 5. Benchmark y comparación

| # | Archivo | Acción |
|---|---------|--------|
| 5.1 | `src/packing_services/benchmark/profiles.py` | Añadir a perfil `constructive` / `hybrid` / `improvement` |
| 5.2 | `examples/benchmark_*_request.json` | Actualizar si el notebook usa engines explícitos |
| 5.3 | `tests/test_benchmark_profiles.py` | Perfil con ≥2 motores ejecutables |

### 6. Notebooks didácticos

| # | Archivo | Acción |
|---|---------|--------|
| 6.1 | `notebooks/_shared/loaders.py` | `COMPARABLE_*_ENGINES`, builders si aplica |
| 6.2 | `notebooks/_build_notebooks.py` | Narrativa / demo opcional |
| 6.3 | Regenerar | `python notebooks/_build_notebooks.py` |
| 6.4 | Validar | `MPLBACKEND=Agg python notebooks/_execute_all.py` |

### 7. Documentación

| # | Archivo | Acción |
|---|---------|--------|
| 7.1 | `docs/algorithm_catalog.md` | Fila en tabla + detalle (`python scripts/regenerate_algorithm_catalog.py`) |
| 7.2 | `docs/roadmap.md` | Marcar ✅ |
| 7.3 | `docs/api_examples.md` | curl + JSON si el flujo es nuevo |
| 7.4 | `README.md` | Conteo de algoritmos si cambia |

## Fase A (este batch)

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `maximal_spaces_3d` | `_maximal_spaces.py` | Constructivo |
| `relocation_improvement` | `_compaction.relocation_pass` | Mejora |
| `swap_improvement` | `_improvement_ops.py` | Mejora |
| `orientation_improvement` | `_improvement_ops.py` | Mejora |
| `bin_reduction` | `_improvement_ops.py` | Mejora |

## Fase B (este batch)

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `multi_box_cartonization` | greedy multi-caja + `ExtremePointPacker` | Cartonization |
| `wall_building_3d` | `_wall_building.py` | Container Loading |
| `py3dbp_adapter` | adaptador externo (dependencia opcional) | 3D-BPP baseline |

## Fase C (este batch)

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `layer_based_palletization` | `_layer_pallet.py` | Palletization |
| `stack_based_palletization` | `_stack_pallet.py` | Palletization / Stacking-aware |
| `stacking_aware_constructive` | `_stack_pallet.py` (estabilidad + load_bearing) | Stacking-aware |

Servicios nuevos: `POST /api/v1/pack/palletization`, `POST /api/v1/pack/stacking-aware`.
Validador ampliado: comprobación `LOAD_BEARING` cuando `constraints.load_bearing=true`.

## Fase D (este batch)

| Algoritmo | Motor | Tipo |
|-----------|-------|------|
| `simulated_annealing_3d_bpp` | `_metaheuristic_searches.run_simulated_annealing` | Metaheurística |
| `genetic_algorithm_3d_bpp` | `_metaheuristic_searches.run_genetic_algorithm` | Metaheurística |
| `grasp_3d_bpp` | `_metaheuristic_searches.run_grasp` | Metaheurística |
| `tabu_search_3d_bpp` | `_metaheuristic_searches.run_tabu_search` | Metaheurística |
| `lns_3d_bpp` | `_metaheuristic_searches.run_lns` | Metaheurística |
| `vns_3d_bpp` | `_metaheuristic_searches.run_vns` | Metaheurística |
| `aco_3d_bpp` | `_metaheuristic_searches.run_aco` | Metaheurística |

Motor compartido: `_metaheuristic_core.py` (codificación por permutación + `sort_strategy=input_order`).
Perfil benchmark: `3D_BPP/metaheuristic`.

## Principios (no hardcode)

- Orden de ítems: `parameters.sort_strategy` → `SortStrategy`.
- Constructivo base en híbridos: `parameters.base_algorithm` o default por `problem_type` (`_constructive_runner.default_base_algorithm`).
- Pases / límites: `parameters.compaction_passes`, `relocation_passes`, `max_swap_attempts`, etc., con defaults razonables.
- Contenedores e ítems: siempre `problem.containers`, `problem.items` expandidos.
- Validación: `build_solution` + validador geométrico existente; mismas `Metrics` para todos.
