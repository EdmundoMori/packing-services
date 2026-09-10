# packing-services

Plataforma local para **empaquetar, validar y comparar** metodologías de
Cutting and Packing (3D-BPP, Container Loading, Cartonization, Palletization,
Stacking-aware) sobre **entradas homogéneas**.

El objetivo único **no** es un algoritmo óptimo ni publicar un espacio de datos.
Es poder decir, con el mismo contrato, el mismo validador y las mismas métricas:
*esta metodología empaca mejor que esta otra, en esta instancia, con esta
regla de orden* — incluyendo el caso en que los paquetes **llegan en secuencia**.

Versión: **0.1.0** · Python 3.10+ · API FastAPI.

---

## Cómo leer la documentación (cascada)

Este README es el documento principal. El resto son hijos: bajar solo el nivel
que haga falta.

| Nivel | Documento | Qué responde |
|------|-----------|--------------|
| 0 | **Este README** | Objetivo, prioridades, estado, cómo ejecutar |
| 1 | [`docs/README.md`](docs/README.md) | Índice de `docs/` y orden de lectura |
| 1 | [`docs/roadmap.md`](docs/roadmap.md) | Qué está hecho y **qué sigue**, en orden de prioridad |
| 2 | [`docs/architecture.md`](docs/architecture.md) | Capas, flujos, contratos internos |
| 2 | [`docs/algorithm_catalog.md`](docs/algorithm_catalog.md) | 52 algoritmos: implemented / adapter / future |
| 2 | [`docs/api_examples.md`](docs/api_examples.md) | Contratos HTTP, curl, BED-BPP, benchmark conjunto |
| 3 | [`docs/algorithm_implementation_traceability.md`](docs/algorithm_implementation_traceability.md) | Checklist para añadir un algoritmo |
| 3 | [`docs/external_adapters.md`](docs/external_adapters.md) | Motores externos (solo `py3dbp` ejecutable hoy) |
| 3 | [`notebooks/README.md`](notebooks/README.md) | Historia visual (notebooks 00–09) |
| 3 | [`web-demo/README.md`](web-demo/README.md) | UI de catálogo / execute / benchmark |

Código de verdad: `src/packing_services/`. Si un `.md` y el código discrepan, gana el código.

---

## Prioridades (de primero a último)

1. **Homogeneizar inputs** — un contrato (`PackAlgorithmInput` / BED-BPP → canónico) para todas las metodologías.
2. **Benchmark de metodologías** — perfiles por tipo + experimento conjunto en un contenedor, mismo validador y métricas.
3. **Empaquetado online** — modo `packing_mode=online` (puerta abierta: constructivos en orden de llegada). Heurístico dedicado y DRL: capas siguientes.
4. Restricciones avanzadas, adaptadores externos reales, métodos exactos.
5. **Espacio de datos** — despriorizado. Hay descriptores en `GET /api/v1/services`; no es el objetivo ni el siguiente paso.

Detalle: [`docs/roadmap.md`](docs/roadmap.md).

---

## Estado actual

| Pieza | Estado |
|-------|--------|
| Contrato canónico `Item` / `Container` / `PackingProblem` / `PackingSolution` | Listo |
| Validador geométrico propio + métricas comunes | Listo |
| 29 algoritmos ejecutables (`POST /api/v1/algorithms/{name}/execute`) | Listo |
| Benchmark por `problem_type` (perfiles `constructive`, `hybrid`, `metaheuristic`, …) | Listo |
| Entrada BED-BPP (secuencia real de pedidos) | Listo |
| Modos `offline` / `online` (mismo input) | Offline cerrado; online como puerta (constructivos + `input_order`) |
| Experimento conjunto un euro-pallet | Listo (`/benchmark/joint-single-container`, default offline) |
| Heurístico online / DRL | Solo metadatos `future` |
| Adaptadores externos | Registrados; ejecutable solo `py3dbp` si se instala |
| Espacio de datos | Preparado, **fuera de la línea crítica** |

**29 implemented + 6 adapter + 17 future = 52** en el catálogo.
Tabla completa: [`docs/algorithm_catalog.md`](docs/algorithm_catalog.md).

### Algoritmos ejecutables (29)

| Grupo | Nombres |
|-------|---------|
| 3D-BPP constructivos | `heuristic_3d_bpp_v1`, `first_fit_decreasing_3d`, `best_fit_decreasing_3d`, `extreme_points_3d`, `maximal_spaces_3d` |
| 3D-BPP mejora / híbrido | `solution_compaction`, `constructive_plus_local_search`, `relocation_improvement`, `swap_improvement`, `orientation_improvement`, `bin_reduction` |
| 3D-BPP metaheurísticas | `simulated_annealing_3d_bpp`, `genetic_algorithm_3d_bpp`, `grasp_3d_bpp`, `tabu_search_3d_bpp`, `lns_3d_bpp`, `vns_3d_bpp`, `aco_3d_bpp` |
| Container Loading | `single_container_constructive`, `weight_aware_container_loading`, `wall_building_3d` |
| Cartonization | `smallest_feasible_box`, `best_box_volume_utilization`, `first_fit_box`, `largest_feasible_box`, `multi_box_cartonization` |
| Palletization | `layer_based_palletization`, `stack_based_palletization` |
| Stacking-aware | `stacking_aware_constructive` |

Cartonization **elige** caja del catálogo. El resto **recibe** el contenedor. El experimento conjunto no incluye cartonization.

---

## Contrato de ejecución

```
POST /api/v1/algorithms/{algorithm_name}/execute
```

- Pack (`3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION`, `STACKING_AWARE`): body `PackAlgorithmInput`.
- Cartonization: body `CartonizationAlgorithmInput` (**solo offline**).
- Campo `packing_mode`: `offline` (default) u `online`. Mismo JSON de ítems/contenedor.
- Salida siempre `AlgorithmExecuteResponse` (solución + validador + métricas).
- BED-BPP: el mismo execute acepta `{ "input_format": "bed_bpp", "order_id", "orders", "packing_mode" }` y normaliza al contrato interno. `sequence` → `arrival_index` siempre. Offline reordena (defaults del algoritmo); online fuerza `input_order`.

Catálogo filtrable: `GET /api/v1/algorithms?packing_mode=offline`. Descripción de modos: `GET /api/v1/packing-modes`.

Ejemplos: [`docs/api_examples.md`](docs/api_examples.md).

---

## Instalación y arranque

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
PYTHONPATH=src uvicorn packing_services.api.main:app --reload
```

Docs interactivas: http://localhost:8000/docs

```bash
# Experimento conjunto (pedido BED-BPP más pequeño, euro-pallet, default offline)
PYTHONPATH=src python scripts/run_joint_single_container.py

# UI de catálogo / execute / benchmark
./web-demo/start.sh   # API :8000 + UI :8080
```

Opcional: `pip install py3dbp` activa el baseline externo.

---

## Endpoints (resumen)

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/health` | Salud |
| GET | `/api/v1/packing-modes` | `offline` / `online`, mismo contrato de entrada |
| GET | `/api/v1/algorithms` | Catálogo (filtros `status`, `problem_type`, `family`, `packing_mode`) |
| GET | `/api/v1/algorithms/{name}` | Metadatos + esquemas + ejemplo |
| **POST** | **`/api/v1/algorithms/{name}/execute`** | Ejecución canónica |
| POST | `/api/v1/validate` | Validador independiente |
| POST | `/api/v1/benchmark` | Comparar ≥2 motores, **un** `problem_type` |
| GET | `/api/v1/benchmark/profiles` | Perfiles de motores por tipo |
| POST | `/api/v1/benchmark/joint-single-container` | Cuatro tipos, un euro-pallet; default `packing_mode=offline` |
| GET/POST | `/api/v1/datasets/bed-bpp/*` | Muestra y conversión BED-BPP |
| POST | `/api/v1/pack/*` | Legacy por tipo; preferir `/algorithms/{name}/execute` |
| GET | `/api/v1/services` | Descriptores (espacio de datos, **no prioritario**) |
| GET | `/api/v1/metadata` | Metadatos globales del servicio |

---

## Árbol del repo

```
packing-services/
├── README.md                 ← este documento
├── docs/                     ← detalle técnico (índice: docs/README.md)
├── src/packing_services/     ← implementación
│   ├── domain/ schemas/ validation/ metrics/
│   ├── algorithms/ adapters/ datasets/ benchmark/
│   ├── services/ api/ utils/
├── examples/                 ← JSON ejecutables + 5_bed-bpp.json
├── tests/
├── notebooks/                ← demos visuales
├── web-demo/                 ← UI
└── scripts/
```

Capas y flujos: [`docs/architecture.md`](docs/architecture.md).

---

## Convenciones y límites

- AABB; `length`→X, `width`→Y, `height`→Z; origen `(0,0,0)` min-corner.
- `allowed_orientations`: `"all"` (6 rotaciones) o `"none"`.
- Heurísticos, no óptimos. Estabilidad avanzada, fragilidad y CoG: pendientes.
- Motores externos: no se modifican sus repos; ver [`docs/external_adapters.md`](docs/external_adapters.md).

---

## Scripts

| Script | Uso |
|--------|-----|
| `scripts/run_joint_single_container.py` | Benchmark conjunto BED-BPP |
| `scripts/regenerate_algorithm_catalog.py` | Regenera `docs/algorithm_catalog.md` |
| `scripts/sync_web_demo_showcase.py` | Copia `examples/showcase_*` a la UI |
