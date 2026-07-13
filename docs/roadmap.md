# Roadmap

Orden de evolución alineado con los documentos de contexto. El principio rector
es: **base robusta (heurísticas + validador) como núcleo**; las metaheurísticas
3D-BPP ya están operativas. Métodos exactos e IA siguen planificados.

## Estado por fase

| Fase | Contenido | Estado |
|------|-----------|--------|
| 0 | Setup del proyecto | ✅ |
| 1 | Core común (dominio, schemas, geometría, métricas, errores, logging) | ✅ |
| 2 | Catálogo + `AlgorithmRegistry` + endpoint `/algorithms` | ✅ |
| 3 | Validador geométrico + tests | ✅ |
| 4 | `heuristic_3d_bpp_v1` | ✅ |
| 5 | `first_fit_decreasing_3d` | ✅ |
| 6 | API local (FastAPI) | ✅ |
| 7 | Benchmark básico | ✅ |
| 8 | Interfaz de adaptadores + `py3dbp` + stubs | ✅ |
| 9 | Documentación / roadmap | ✅ |
| 10 | Servicios Container Loading + Cartonization operativos | ✅ |
| 11 | Descriptores para espacio de datos (`/services`) | ✅ |

## Servicios operativos (Prioridad 1)

| Servicio | Endpoint | Estado |
|----------|----------|--------|
| 3D Bin Packing Offline | `POST /pack/3d-bpp` | ✅ operativo |
| Container Loading | `POST /pack/container-loading` | ✅ operativo (baseline weight-aware) |
| Cartonization / Order Packing | `POST /pack/cartonization` | ✅ operativo (selección de caja) |
| Packing Validation | `POST /validate` | ✅ operativo |
| Benchmark / Comparison | `POST /benchmark` | ✅ operativo |
| Descriptores espacio de datos | `GET /services` | ✅ operativo |
| Palletization | `POST /pack/palletization` | ✅ operativo |
| Stacking-aware | `POST /pack/stacking-aware` | ✅ operativo |

## Algoritmos implementados hasta ahora

Constructivos (todos ejecutables, validables y comparables):
- **3D-BPP**: `heuristic_3d_bpp_v1`, `first_fit_decreasing_3d`,
  `extreme_points_3d`, `best_fit_decreasing_3d`, `maximal_spaces_3d`.
- **Mejora / híbrido 3D-BPP**: `solution_compaction`,
  `constructive_plus_local_search`, `relocation_improvement`, `swap_improvement`,
  `orientation_improvement`, `bin_reduction`.
- **Container Loading**: `single_container_constructive`,
  `weight_aware_container_loading`.
- **Cartonization**: `smallest_feasible_box`, `best_box_volume_utilization`,
  `first_fit_box`, `largest_feasible_box`, `multi_box_cartonization`.
- **Container Loading (Fase B)**: `wall_building_3d`.

- **3D-BPP metaheurísticas**: `simulated_annealing_3d_bpp`, `genetic_algorithm_3d_bpp`,
  `grasp_3d_bpp`, `tabu_search_3d_bpp`, `lns_3d_bpp`, `vns_3d_bpp`, `aco_3d_bpp`.

- **Palletization**: `layer_based_palletization`, `stack_based_palletization`.
- **Stacking-aware**: `stacking_aware_constructive`.

**29 algoritmos implementados** — cada uno expone
`POST /api/v1/algorithms/{algorithm_name}/execute` con contrato homogéneo
(`PackAlgorithmInput` / `CartonizationAlgorithmInput` → `AlgorithmExecuteResponse`).

**Adaptador activo**: `py3dbp_adapter` (ejecutable con `pip install py3dbp`).

Ver checklist de trazabilidad: `docs/algorithm_implementation_traceability.md`.

## Próximos pasos recomendados

### Corto plazo (mejorar calidad 3D-BPP)
1. ✅ `extreme_points_3d` — hecho.
2. ✅ `best_fit_decreasing_3d` — hecho.
3. ✅ `solution_compaction` + `constructive_plus_local_search` — hecho (mejora local).
4. ✅ `maximal_spaces_3d` — hecho.
5. ✅ Heurísticas de mejora adicionales (`relocation_improvement`,
   `orientation_improvement`, `swap_improvement`, `bin_reduction`) — hecho.
6. ✅ Fase B: `multi_box_cartonization`, `wall_building_3d`, `py3dbp_adapter` activo — hecho.
7. ✅ Fase C: `layer_based_palletization`, `stack_based_palletization`, `stacking_aware_constructive` + endpoints `/pack/palletization` y `/pack/stacking-aware` — hecho.
8. ✅ Fase D: metaheurísticas 3D-BPP (7) + perfil benchmark `metaheuristic` — hecho.
9. `bottom_left_back_3d` como servicio dedicado (opcional; ya existe como estrategia interna).
10. Activar `packingsolver_adapter` u otros adaptadores externos reales.

### Servicios por grupo (según análisis de repositorios)

| Servicio | Motor principal (futuro) | Adaptador |
|----------|--------------------------|-----------|
| 3D Bin Packing Offline | skjolber/3d-bin-container-packing (Java) | `skjolber_adapter` |
| Container Loading | davidmchapman/3DContainerPacking (C#, EB-AFIT) | `container_packing_adapter` |
| Cartonization / Order Packing | dvdoug/BoxPacker (PHP) | `boxpacker_adapter` |
| Palletization | fontanf/packingsolver `boxstacks` (C++) | `packingsolver_adapter` |
| Stacking-aware Packing | fontanf/packingsolver `boxstacks` (C++) | `packingsolver_adapter` |
| Benchmark / Comparison | servicio propio | — (integra todos) |
| Validation | servicio propio | — |

Baseline en Python puro: `py3dbp_adapter` (enzoruiz/3dbinpacking), ejecutable si
se instala `py3dbp`.

### Endpoints
- ✅ `POST /api/v1/pack/container-loading`
- ✅ `POST /api/v1/pack/cartonization`
- ✅ `GET /api/v1/services` (descriptores para espacio de datos)
- 🔜 `POST /api/v1/pack/palletization` → ✅ operativo
- 🔜 `POST /api/v1/pack/stacking-aware` → ✅ operativo

### Restricciones avanzadas (fases posteriores)
- Peso: distribución, centro de gravedad, estabilidad avanzada.
- `load_bearing` (requiere poblar `max_load_on_top` en los ítems).
- Fragilidad, compatibilidad entre ítems, secuencia de carga/descarga.
- Estabilidad por superficie de soporte ya tiene una comprobación básica en el
  validador (`basic_stability`).

### Optimización avanzada
- ✅ Metaheurísticas 3D-BPP: GA, Tabu Search, SA, GRASP, VNS, LNS, ACO
  (`metaheuristic_3d_bpp.py`, perfil benchmark `3D_BPP/metaheuristic`).
- Métodos exactos / referencia: MIP, CP-SAT (OR-Tools), Branch&Bound/Cut/Price,
  generación de columnas. Para instancias pequeñas y benchmarking.
- Enfoques híbridos adicionales: extreme points + SA (`extreme_points_plus_sa`),
  descomposición por capas + knapsack, MIP para subproblemas + heurística.

### Investigación (línea avanzada)
- Online 3D-BPP heurístico (ítems secuenciales).
- DRL (`drl_policy_3d_bpp`, alexfrom0815/Online-3D-BPP-PCT): requiere dataset,
  simulador, modelo entrenado y validación estricta.

## Integración futura en espacio de datos

El proyecto queda **preparado** (no integrado) mediante:
- entradas/salidas JSON estandarizadas,
- metadatos por algoritmo y por servicio (`/api/v1/metadata`, `/api/v1/algorithms`),
- **descriptores publicables por servicio** (`GET /api/v1/services`) con tipo de
  problema, motor, licencia, formatos I/O, restricciones, métricas, endpoints,
  trazabilidad y limitaciones,
- trazabilidad de ejecución (`execution_metadata`),
- separación de servicios (optimización / validación / comparación).

Lógica prevista: publicar → descubrir → negociar acceso → ejecutar → validar →
comparar → registrar evidencias.

## Nota de entorno
- Docker: no incluido aún; queda como documentación futura (un contenedor por la
  API Python y microservicios separados por motor externo).
- Sin base de datos en la primera versión.
