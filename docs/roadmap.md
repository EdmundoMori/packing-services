# Hoja de Ruta del Proyecto

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md).

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas:

- **Misma entrada:** formato de datos unificado para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo.
- **Mismas métricas:** indicadores de rendimiento calculados uniformemente.

El sistema soporta tanto el modo `packing_mode=offline` (pedido completo conocido de antemano) como `packing_mode=online` (ítems que llegan en secuencia).

---

## Resumen de Prioridades

El desarrollo del proyecto sigue un orden de prioridades establecido. **Los objetivos 1–3 ya están operativos.** El siguiente paso es el objetivo 4.

| # | Prioridad | Estado |
|:-:|-----------|--------|
| 1 | Homogeneizar entradas | **Completado** |
| 2 | Benchmark de metodologías | **Completado** |
| 3 | Empaquetado online | **Completado** |
| 4 | Mejoras de calidad | **Siguiente** |
| 5 | Espacio de datos | Despriorizado |

---

## Base Operativa Actual

La siguiente tabla resume los componentes que ya están implementados y funcionando:

| Componente | Descripción |
|------------|-------------|
| Core | Modelos de dominio, esquemas, geometría AABB, métricas, logging y API FastAPI |
| Catálogo | `AlgorithmRegistry` con 31 algoritmos implementados, 6 adaptadores y 15 futuros |
| Validador | Servicio de validación independiente del algoritmo (`POST /validate`) |
| Ejecución | Endpoint canónico `POST /api/v1/algorithms/{name}/execute` |
| Tipos de problema | 3D-BPP, Container Loading, Single Container Loading, Cartonization, Palletization, Stacking-aware |
| Metaheurísticas | Simulated Annealing, Genetic Algorithm, GRASP, Tabu Search, LNS, VNS, ACO |
| Entradas | Contrato canónico y conversión BED-BPP (`examples/5_bed-bpp.json` es holdout de producto) |
| Benchmark | Perfiles por tipo de problema y endpoint `POST /benchmark/joint-single-container` |
| Online | Bucle `run_online_loop`, heurístico y política RL de producción (`mlp_v1_p1s1_ppo.pt`, `mlp_v1_p3s2.pt`) |
| Interfaz web | `web-demo/` con catálogo, ejecución y benchmark en modos offline y online |

> **Nota:** Los endpoints legacy `/pack/*` permanecen operativos, pero el patrón recomendado es `/algorithms/{name}/execute`.

---

## 1. Homogeneización de Entradas

**Estado: Completado**

### Funcionalidad Implementada

- Conversión de `PackAlgorithmInput` y `CartonizationAlgorithmInput` hacia `PackingProblem`.
- Transformación de formato BED-BPP (`item_sequence`) hacia `containers` + `items` mediante `datasets/bed_bpp.py`.
- Preservación del campo `sequence` como `Item.arrival_index` para mantener el orden de llegada.
- Modo offline (predeterminado): el solver puede reordenar ítems según estrategias como `volume_desc` o `weight_desc`.
- Modo online: los algoritmos constructivos, el heurístico online y `drl_policy_3d_bpp` respetan el orden de llegada (`input_order`).

### Trabajo Pendiente (No Bloqueante)

- **Normalización de unidades:** las instancias showcase utilizan unidades abstractas, mientras que BED-BPP emplea mm/kg.
- **Catálogo maestro:** `showcase_master_catalog` no incluye la geometría específica para palletization, stacking y cartonization.
- **Restricciones adicionales:** BED-BPP no mapea actualmente `max_load_on_top` ni indicadores de fragilidad, y no convierte hacia CARTONIZATION.

---

## 2. Benchmark de Metodologías

**Estado: Completado**

### Funcionalidad Implementada

- Endpoint `POST /api/v1/benchmark` con soporte para perfiles predefinidos.
- Consulta de perfiles disponibles mediante `GET /benchmark/profiles` (un `problem_type` por perfil).
- Experimento conjunto: un euro-pallet evaluado con cuatro tipos de problema mediante `scripts/run_joint_single_container.py` (modo offline por defecto).

### Trabajo Pendiente (Opcional)

- Ampliar el conjunto de pedidos BED-BPP utilizados en las pruebas (actualmente solo el pedido más pequeño).
- Realizar comparaciones explícitas entre `packing_mode=offline` y `packing_mode=online` para los 5 pedidos de producto.
- Excluir cartonization del experimento conjunto, ya que este tipo selecciona caja del catálogo en lugar de recibir un contenedor fijo.

---

## 3. Empaquetado Online

**Estado: Completado**

### Funcionalidad Implementada

El heurístico online y la política aprendida están operativos sobre el mismo bucle de decisión:

- **Algoritmos:** `drl_policy_3d_bpp` y `online_3d_bpp_heuristic`
- **Endpoints:** `POST /api/v1/algorithms/drl_policy_3d_bpp/execute` y `POST /api/v1/online/learned/execute`
- **Modelo por defecto:** `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` (`lookahead_p=1`, `select_s=1`, `policy=rl`)
- **Modelo de cinta:** `mlp_v1_p3s2.pt` (`lookahead_p=3`, `select_s=2`)
- **Modelo lineal (sin PyTorch):** `linear_v1.json`
- **Placeholder de prueba:** `examples/online_policy_linear_v1.json` (no es el modelo de producción)

### Especificaciones Técnicas

- **Contrato de checkpoint:** `packing-services-online-policy` v1
- **Versión de características:** `feature_version=1`
- **Arquitectura del MLP:** `Linear(35, 64) → ReLU → Linear(64, 1)`

### Consideraciones Importantes

- El entrenamiento (metodología P2O y splits) se realiza en `online_policy_ml/` y **no utiliza** los 5 pedidos de `examples/5_bed-bpp.json`.
- Las metaheurísticas permanecen exclusivamente en modo **offline**; el modo online las rechaza.

### Lectura de producto

La política aprendida (`mlp_v1_p1s1_ppo.pt`) es un **empate estadístico** con `online_3d_bpp_heuristic`. El fine-tuning PPO sobre el encoder v1 está cerrado. STEP y shaping no se promocionan. En el pedido `00100408`, bin cerrado 2000 mm, **supera** a PCT (Zhao ICLR 2022) por factibilidad, no por Uti. de Table 1 ni ranking BED-BPP. Relato: [`../online_policy_ml/docs/informe_cierre_rl_online.md`](../online_policy_ml/docs/informe_cierre_rl_online.md).

### Trabajo Pendiente (Opcional)

- Pista multi-pallet cerrada (`07`/`08`): first-fit 30→24 palés; el execute consolida si hay 2+ contenedores.
- No se plantea RL desde cero ni cambiar el encoder v1 (`FEATURE_VERSION=2` / heightmap queda fuera de este ciclo).

> **Nota:** El execute de producción no reentrena. El encoder v1 y el bucle `run_online_loop` no se tocan.

---

## 4. Mejoras de Calidad

**Estado: Siguiente Paso**

Esta fase incluye las siguientes mejoras planificadas:

- **Activación de adaptadores externos:** integración de `skjolber`, BoxPacker, 3DContainerPacking y PackingSolver cuando los motores estén disponibles en el entorno. Actualmente solo `py3dbp` puede activarse.

- **Restricciones avanzadas:** implementación de centro de gravedad (CoG), fragilidad, restricción de carga soportada (`load_bearing`) y secuencia de descarga.

- **Métodos exactos de referencia:** implementación de MIP y CP-SAT para instancias pequeñas que sirvan como referencia de optimalidad.

- **Servicio `bottom_left_back_3d`:** consideración de exponerlo como servicio propio (actualmente es estrategia interna).

---

## 5. Espacio de Datos

**Estado: Despriorizado**

### Funcionalidad Actual

- El endpoint `GET /api/v1/services` y el servicio `DataspaceService` generan descriptores de servicios.
- **No hay** integración real con un espacio de datos distribuido (publicar → descubrir → negociar → ejecutar).

### Decisión de Diseño

Los objetivos 1–3 ya están cubiertos. El espacio de datos distribuido **no es el objetivo** del proyecto ni el siguiente paso en la hoja de ruta.

---

## Configuración del Entorno

### Contenedorización

- **Interfaz web:** `web-demo/Dockerfile` y `web-demo/docker-compose.yml`
- **Base de datos:** no requerida
- **Motores externos en contenedores:** no implementado en esta versión
