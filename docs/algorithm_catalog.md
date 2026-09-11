# Catálogo de Algoritmos

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md).

Este catálogo se genera automáticamente mediante el script `python scripts/regenerate_algorithm_catalog.py`.

## Propósito

Los algoritmos de este catálogo sirven al objetivo del proyecto: comparar metodologías de empaquetado bajo condiciones homogéneas (misma entrada, mismo validador, mismas métricas) en los modos `packing_mode=offline` y `packing_mode=online`.

## Resumen del Inventario

| Categoría | Cantidad |
|-----------|:--------:|
| Implementados | 31 |
| Adaptadores | 6 |
| Futuros | 15 |
| **Total** | **52** |

---

## Tabla de Algoritmos

| Nombre | Nombre para Mostrar | Familia | Estado | Modos de Packing | Tipos de Problema |
|--------|---------------------|---------|--------|------------------|-------------------|
| `boxpacker_adapter` | BoxPacker Adapter (dvdoug/BoxPacker) | adapter | adapter | offline, online | CARTONIZATION, 3D_BPP |
| `container_packing_adapter` | 3DContainerPacking Adapter (EB-AFIT) | adapter | adapter | offline, online | CONTAINER_LOADING, 3D_BPP |
| `dwave_adapter` | D-Wave CQM Adapter (dwave-examples/3d-bin-packing) | adapter | adapter | offline, online | 3D_BPP, BENCHMARK |
| `packingsolver_adapter` | PackingSolver Adapter (fontanf/packingsolver) | adapter | adapter | offline, online | 3D_BPP, STACKING_AWARE, PALLETIZATION, BENCHMARK |
| `py3dbp_adapter` | py3dbp Adapter (enzoruiz/3dbinpacking) | adapter | adapter | offline, online | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `skjolber_adapter` | skjolber 3d-bin-container-packing Adapter | adapter | adapter | offline, online | 3D_BPP, CONTAINER_LOADING |
| `basic_support_surface_validation` | Basic Support Surface Validation | validator | future | offline, online | STACKING_AWARE, VALIDATION |
| `bottom_left_back_3d` | Bottom-Left-Back Heuristic | constructive_heuristic | future | offline, online | 3D_BPP |
| `branch_and_bound_reference` | Branch and Bound (reference) | exact | future | offline | 3D_BPP |
| `branch_and_cut_reference` | Branch and Cut (reference) | exact | future | offline | 3D_BPP |
| `column_generation_cutting_packing` | Branch and Price / Column Generation | exact | future | offline | 3D_BPP |
| `cp_sat_3d_bpp_reference` | Constraint Programming / CP-SAT (reference) | exact | future | offline | 3D_BPP |
| `extreme_points_plus_sa` | Extreme Points + Simulated Annealing | hybrid | future | offline | 3D_BPP |
| `knapsack_layer_selection` | Knapsack-based Layer Selection | hybrid | future | offline | 3D_BPP, PALLETIZATION |
| `layer_based_3d` | Layer-based Packing | constructive_heuristic | future | offline, online | 3D_BPP, PALLETIZATION |
| `layer_knapsack_hybrid` | Layer Decomposition + Knapsack | hybrid | future | offline | 3D_BPP, PALLETIZATION |
| `load_bearing_validator` | Load-bearing Constraint Check | validator | future | offline, online | STACKING_AWARE, VALIDATION |
| `mip_3d_bpp_reference` | Mixed Integer Programming (reference) | exact | future | offline | 3D_BPP |
| `mip_heuristic_hybrid` | MIP for Small Subproblems + Heuristic Packing | hybrid | future | offline | 3D_BPP |
| `packingsolver_plus_internal_validator` | PackingSolver Adapter + Local Validation | hybrid | future | offline | 3D_BPP, STACKING_AWARE, PALLETIZATION |
| `sequence_aware_loading` | Sequence-aware Loading | constructive_heuristic | future | offline, online | CONTAINER_LOADING |
| `aco_3d_bpp` | Ant Colony Optimization 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `best_box_volume_utilization` | Best Box by Volume Utilization | constructive_heuristic | implemented | offline | CARTONIZATION |
| `best_fit_decreasing_3d` | Best Fit Decreasing 3D | constructive_heuristic | implemented | offline, online | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `bin_reduction` | Bin Reduction | improvement_heuristic | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `constructive_plus_local_search` | Constructive Heuristic + Local Improvement | hybrid | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `drl_policy_3d_bpp` | Deep Reinforcement Learning Policy | machine_learning | implemented | online | 3D_BPP, CONTAINER_LOADING, SINGLE_CONTAINER_LOADING, PALLETIZATION, STACKING_AWARE |
| `extreme_points_3d` | Extreme Points Heuristic | constructive_heuristic | implemented | offline, online | 3D_BPP, CONTAINER_LOADING |
| `first_fit_box` | First Fit Box | constructive_heuristic | implemented | offline | CARTONIZATION |
| `first_fit_decreasing_3d` | First Fit Decreasing 3D | constructive_heuristic | implemented | offline, online | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `genetic_algorithm_3d_bpp` | Genetic Algorithm 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `grasp_3d_bpp` | GRASP 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `heuristic_3d_bpp_v1` | Volume First Candidate Placement | constructive_heuristic | implemented | offline, online | 3D_BPP, SINGLE_CONTAINER_LOADING |
| `largest_feasible_box` | Largest Feasible Box | constructive_heuristic | implemented | offline | CARTONIZATION |
| `layer_based_palletization` | Layer-based Palletization | constructive_heuristic | implemented | offline, online | PALLETIZATION |
| `lns_3d_bpp` | Large Neighborhood Search 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `maximal_spaces_3d` | Maximal Empty Spaces Heuristic | constructive_heuristic | implemented | offline, online | 3D_BPP, CONTAINER_LOADING |
| `multi_box_cartonization` | Multi-box Cartonization | constructive_heuristic | implemented | offline | CARTONIZATION |
| `online_3d_bpp_heuristic` | Online 3D-BPP Heuristic | constructive_heuristic | implemented | online | 3D_BPP, CONTAINER_LOADING, SINGLE_CONTAINER_LOADING, PALLETIZATION, STACKING_AWARE |
| `orientation_improvement` | Orientation Improvement | improvement_heuristic | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `relocation_improvement` | Relocation Improvement | improvement_heuristic | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `simulated_annealing_3d_bpp` | Simulated Annealing 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `single_container_constructive` | Single Container Constructive Loading | constructive_heuristic | implemented | offline, online | SINGLE_CONTAINER_LOADING, CONTAINER_LOADING |
| `smallest_feasible_box` | Smallest Feasible Box | constructive_heuristic | implemented | offline | CARTONIZATION |
| `solution_compaction` | Compaction | improvement_heuristic | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `stack_based_palletization` | Stack-based Palletization | constructive_heuristic | implemented | offline, online | PALLETIZATION, STACKING_AWARE |
| `stacking_aware_constructive` | Stacking-aware Constructive Packing | constructive_heuristic | implemented | offline, online | STACKING_AWARE |
| `swap_improvement` | Swap Improvement | improvement_heuristic | implemented | offline | 3D_BPP, CONTAINER_LOADING |
| `tabu_search_3d_bpp` | Tabu Search 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `vns_3d_bpp` | Variable Neighborhood Search 3D-BPP | metaheuristic | implemented | offline | 3D_BPP |
| `wall_building_3d` | Wall-building Heuristic | constructive_heuristic | implemented | offline, online | CONTAINER_LOADING |
| `weight_aware_container_loading` | Weight-aware Container Loading | constructive_heuristic | implemented | offline, online | CONTAINER_LOADING, 3D_BPP |
