# Catálogo de algoritmos

Este catálogo es descubrible en tiempo de ejecución vía
`GET /api/v1/algorithms` (con filtros `problem_type`, `family`, `status`,
`supported_constraint`). La tabla siguiente refleja el registro por defecto.

## Estados

- **implemented**: implementación local ejecutable.
- **adapter**: adaptador a un motor externo (ejecutable solo si el motor/dep.
  está disponible; si no, devuelve error 503 con instrucciones).
- **stub**: reservado para adaptadores sin implementación (actualmente ninguno;
  los adaptadores externos se modelan como `adapter` no disponibles).
- **future**: contemplado en el roadmap; solo metadatos, no ejecutable.

Resumen: **50 algoritmos** registrados — 8 implementados, 6 adaptadores, 36
futuros.

## Tabla completa

| name | display_name | family | status | problem_types |
|------|--------------|--------|--------|---------------|
| `best_box_volume_utilization` | Best Box by Volume Utilization | constructive_heuristic | implemented | CARTONIZATION |
| `best_fit_decreasing_3d` | Best Fit Decreasing 3D | constructive_heuristic | implemented | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `extreme_points_3d` | Extreme Points Heuristic | constructive_heuristic | implemented | 3D_BPP, CONTAINER_LOADING |
| `first_fit_decreasing_3d` | First Fit Decreasing 3D | constructive_heuristic | implemented | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `heuristic_3d_bpp_v1` | Volume First Candidate Placement | constructive_heuristic | implemented | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `single_container_constructive` | Single Container Constructive Loading | constructive_heuristic | implemented | SINGLE_CONTAINER_LOADING, CONTAINER_LOADING |
| `smallest_feasible_box` | Smallest Feasible Box | constructive_heuristic | implemented | CARTONIZATION |
| `weight_aware_container_loading` | Weight-aware Container Loading | constructive_heuristic | implemented | CONTAINER_LOADING, 3D_BPP |
| `boxpacker_adapter` | BoxPacker Adapter (dvdoug/BoxPacker) | adapter | adapter | CARTONIZATION, 3D_BPP |
| `container_packing_adapter` | 3DContainerPacking Adapter (EB-AFIT) | adapter | adapter | CONTAINER_LOADING, 3D_BPP |
| `dwave_adapter` | D-Wave CQM Adapter | adapter | adapter | 3D_BPP, BENCHMARK |
| `packingsolver_adapter` | PackingSolver Adapter | adapter | adapter | 3D_BPP, STACKING_AWARE, PALLETIZATION, BENCHMARK |
| `py3dbp_adapter` | py3dbp Adapter (enzoruiz/3dbinpacking) | adapter | adapter | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `skjolber_adapter` | skjolber 3d-bin-container-packing Adapter | adapter | adapter | 3D_BPP, CONTAINER_LOADING |
| `aco_3d_bpp` | Ant Colony Optimization 3D-BPP | metaheuristic | future | 3D_BPP |
| `basic_support_surface_validation` | Basic Support Surface Validation | validator | future | STACKING_AWARE, VALIDATION |
| `bin_reduction` | Bin Reduction | improvement_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `bottom_left_back_3d` | Bottom-Left-Back Heuristic | constructive_heuristic | future | 3D_BPP |
| `branch_and_bound_reference` | Branch and Bound (reference) | exact | future | 3D_BPP |
| `branch_and_cut_reference` | Branch and Cut (reference) | exact | future | 3D_BPP |
| `column_generation_cutting_packing` | Branch and Price / Column Generation | exact | future | 3D_BPP |
| `constructive_plus_local_search` | Constructive + Local Improvement | hybrid | future | 3D_BPP |
| `cp_sat_3d_bpp_reference` | Constraint Programming / CP-SAT (reference) | exact | future | 3D_BPP |
| `drl_policy_3d_bpp` | Deep Reinforcement Learning Policy | machine_learning | future | 3D_BPP |
| `extreme_points_plus_sa` | Extreme Points + Simulated Annealing | hybrid | future | 3D_BPP |
| `genetic_algorithm_3d_bpp` | Genetic Algorithm 3D-BPP | metaheuristic | future | 3D_BPP |
| `grasp_3d_bpp` | GRASP 3D-BPP | metaheuristic | future | 3D_BPP |
| `knapsack_layer_selection` | Knapsack-based Layer Selection | hybrid | future | 3D_BPP, PALLETIZATION |
| `layer_based_3d` | Layer-based Packing | constructive_heuristic | future | 3D_BPP, PALLETIZATION |
| `layer_based_palletization` | Layer-based Palletization | constructive_heuristic | future | PALLETIZATION |
| `layer_knapsack_hybrid` | Layer Decomposition + Knapsack | hybrid | future | 3D_BPP, PALLETIZATION |
| `lns_3d_bpp` | Large Neighborhood Search 3D-BPP | metaheuristic | future | 3D_BPP |
| `load_bearing_validator` | Load-bearing Constraint Check | validator | future | STACKING_AWARE, VALIDATION |
| `maximal_spaces_3d` | Maximal Empty Spaces Heuristic | constructive_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `mip_3d_bpp_reference` | Mixed Integer Programming (reference) | exact | future | 3D_BPP |
| `mip_heuristic_hybrid` | MIP for Small Subproblems + Heuristic | hybrid | future | 3D_BPP |
| `multi_box_cartonization` | Multi-box Cartonization | constructive_heuristic | future | CARTONIZATION |
| `online_3d_bpp_heuristic` | Online 3D-BPP Heuristic | constructive_heuristic | future | 3D_BPP |
| `orientation_improvement` | Orientation Improvement | improvement_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `packingsolver_plus_internal_validator` | PackingSolver + Local Validation | hybrid | future | 3D_BPP, STACKING_AWARE, PALLETIZATION |
| `relocation_improvement` | Relocation Improvement | improvement_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `sequence_aware_loading` | Sequence-aware Loading | constructive_heuristic | future | CONTAINER_LOADING |
| `simulated_annealing_3d_bpp` | Simulated Annealing 3D-BPP | metaheuristic | future | 3D_BPP |
| `solution_compaction` | Compaction | improvement_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `stack_based_palletization` | Stack-based Palletization | constructive_heuristic | future | PALLETIZATION, STACKING_AWARE |
| `stacking_aware_constructive` | Stacking-aware Constructive Packing | constructive_heuristic | future | STACKING_AWARE |
| `swap_improvement` | Swap Improvement | improvement_heuristic | future | 3D_BPP, CONTAINER_LOADING |
| `tabu_search_3d_bpp` | Tabu Search 3D-BPP | metaheuristic | future | 3D_BPP |
| `vns_3d_bpp` | Variable Neighborhood Search 3D-BPP | metaheuristic | future | 3D_BPP |
| `wall_building_3d` | Wall-building Heuristic | constructive_heuristic | future | CONTAINER_LOADING |

## Algoritmos implementados (detalle)

### `heuristic_3d_bpp_v1` — Volume First Candidate Placement
Heurística constructiva base. Ordena ítems por volumen descendente, genera
posiciones candidatas a partir de los ítems colocados (`x+l`, `y+w`, `z+h`) y
elige la posición **bottom-left-back** factible entre todos los contenedores.
Prueba rotaciones permitidas y valida contención, no solapamiento y peso.
Determinista. Parámetros: `sort_strategy`, `position_strategy`.

### `first_fit_decreasing_3d` — First Fit Decreasing 3D
Ordena ítems de forma decreciente y coloca cada uno en el **primer** contenedor
y primera posición factible (first-fit), llenando un contenedor antes de abrir
el siguiente. Comparte validador, métricas y formato de salida con la heurística
base, por lo que ambos son comparables. Parámetro: `sort_strategy`.

### `extreme_points_3d` — Extreme Points Heuristic
Mantiene una **lista persistente de puntos extremos** por contenedor: tras
colocar un ítem genera nuevos puntos proyectando sus caras sobre las superficies
existentes (proyección vertical) y elimina los puntos que quedan cubiertos.
Coloca cada ítem en el punto extremo factible más bottom-left-back. Suele mejorar
la calidad frente a `heuristic_3d_bpp_v1`. Parámetro: `sort_strategy`.

### `best_fit_decreasing_3d` — Best Fit Decreasing 3D
Usa el mismo motor de puntos extremos, pero elige la colocación que **maximiza el
área de contacto** con las paredes del contenedor y las cajas vecinas (mejor
encaje / menor espacio residual) en lugar del criterio bottom-left-back.
Parámetro: `sort_strategy`.

### `single_container_constructive` — Single Container Constructive Loading
Baseline de Container Loading: maximiza el volumen cargado en **un único
contenedor** (usa solo el primero si se pasan varios), reutilizando el motor de
puntos extremos con best-fit. Reporta ítems cargados, no cargados, coordenadas y
utilización. Parámetro: `sort_strategy`.

### `weight_aware_container_loading` — Weight-aware Container Loading
Carga **multi-contenedor** que prioriza los ítems más pesados (orden por peso
descendente por defecto) y respeta el peso máximo de cada contenedor además de la
geometría. Reutiliza el motor de puntos extremos con best-fit y reporta el peso
cargado. La distribución fina de peso y el centro de gravedad son fase posterior.
Parámetro: `sort_strategy` (por defecto `weight_desc`).

### `smallest_feasible_box` — Smallest Feasible Box (Cartonization)
Trata `containers` como **catálogo de cajas candidatas** y selecciona la caja de
**menor volumen** donde caben todos los ítems del pedido. Si ninguna caja aloja
todo, elige la que empaca más ítems. Parámetro: `sort_strategy`.

### `best_box_volume_utilization` — Best Box by Volume Utilization (Cartonization)
Evalúa todas las cajas candidatas y, entre las que alojan **todos** los ítems,
selecciona la de **mayor utilización volumétrica**. Produce una solución estándar
(comparable y validable). Parámetro: `sort_strategy`.

## Ficha de metadatos

Cada algoritmo expone: `name`, `display_name`, `problem_types`,
`algorithm_family`, `status`, `deterministic`, `supports_random_seed`,
`supports_time_limit`, `supports_rotation`, `supports_multi_container`,
`supported_constraints`, `unsupported_constraints`, `parameters`, `metrics`,
`limitations` y, para adaptadores, `external_engine` / `external_language` /
`external_repository`.
