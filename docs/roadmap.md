# Roadmap

Documento hijo de [`../README.md`](../README.md). Índice: [`README.md`](README.md).

Prioridad actual, de primero a último:

1. Homogeneizar inputs.
2. Benchmark de metodologías.
3. Empaquetado online.
4. Calidad extra (restricciones, adaptadores reales, exactos).
5. Espacio de datos (despriorizado).

---

## Hecho (base operativa)

| Bloque | Contenido |
|--------|-----------|
| Core | Dominio, schemas, geometría AABB, métricas, logging, API FastAPI |
| Catálogo | `AlgorithmRegistry` — 29 implemented, 6 adapter, 17 future |
| Validador | Independiente del algoritmo (`POST /validate`) |
| Execute | `POST /api/v1/algorithms/{name}/execute` |
| Tipos | 3D-BPP, CL, SCL, Cartonization, Palletization, Stacking-aware |
| Metaheurísticas 3D-BPP | SA, GA, GRASP, Tabu, LNS, VNS, ACO |
| Inputs | Contrato canónico + conversión BED-BPP (`examples/5_bed-bpp.json`) |
| Benchmark | Perfiles por tipo + `POST /benchmark/joint-single-container` |
| UI | `web-demo/` (catálogo, execute, benchmark) |

Los endpoints legacy `/pack/*` siguen; el patrón canónico es `/algorithms/{name}/execute`.

---

## 1. Homogeneizar inputs (en curso / reforzar)

Ya existe:

- `PackAlgorithmInput` / `CartonizationAlgorithmInput` → `PackingProblem`.
- BED-BPP (`item_sequence`) → `containers` + `items` (`datasets/bed_bpp.py`).
- `sort_strategy=input_order` conserva la llegada.

Pendiente (no bloquea el online, pero sí la comparabilidad estricta):

- Unidades: showcase usa unidades abstractas; BED-BPP usa mm/kg.
- `showcase_master_catalog` no es la geometría de pallet/stacking/cartonization.
- BED-BPP no mapea `max_load_on_top` ni fragilidad; no convierte a CARTONIZATION.

---

## 2. Benchmark de metodologías (en curso / reforzar)

Ya existe:

- `POST /api/v1/benchmark` + `GET /benchmark/profiles` (un `problem_type`).
- Experimento conjunto: un euro-pallet, cuatro tipos, `input_order`
  (`scripts/run_joint_single_container.py`).

Pendiente:

- Más pedidos BED-BPP (no solo el más pequeño).
- Comparar explícitamente `input_order` vs `volume_desc` (offline vs llegada).
- No mezclar cartonization en el conjunto de “un contenedor fijado”.

---

## 3. Empaquetado online (siguiente línea de implementación)

Hoy el baseline es ejecutar constructivos con `sort_strategy=input_order` sobre
BED-BPP. Eso **no** es todavía el servicio `online_3d_bpp_heuristic`.

Siguiente implementación:

1. Heurístico online ejecutable (`online_3d_bpp_heuristic`): un ítem a la vez,
   sin reordenar el resto.
2. Mismo validador y métricas que el experimento conjunto.
3. DRL (`drl_policy_3d_bpp`) después: dataset + simulador + política entrenada.
   Referencia de investigación: alexfrom0815/Online-3D-BPP-PCT.

Las metaheurísticas ya hechas son **offline**: conocen todos los ítems y buscan
una permutación. No sustituyen al online.

---

## 4. Calidad extra (después del online)

- Adaptadores reales cuando el motor esté en el entorno (`skjolber`, BoxPacker,
  3DContainerPacking, PackingSolver). Hoy solo `py3dbp` puede activarse.
- Restricciones: CoG, fragilidad, load-bearing poblado, secuencia de descarga.
- Métodos exactos de referencia (MIP, CP-SAT) para instancias pequeñas.
- `bottom_left_back_3d` como servicio propio es opcional (ya es estrategia interna).

---

## 5. Espacio de datos (último)

`GET /api/v1/services` y `DataspaceService` generan descriptores. **No** hay
integración real (publicar → descubrir → negociar → ejecutar).

No planificar trabajo de dataspace mientras 1–3 estén abiertos.

---

## Entorno

- Docker de la UI: `web-demo/Dockerfile` + `web-demo/docker-compose.yml`.
- Sin base de datos.
- Un contenedor por motor externo: no está en esta versión.
