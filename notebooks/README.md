# Notebooks didácticos

Documento hijo de [`../README.md`](../README.md).

**10 notebooks** (00–09) para explicar el avance de forma visual. No sustituyen
el README ni `docs/`: son la historia narrada (layouts, KPIs, benchmarks).

El hilo es: **inputs homogéneos → ejecutar → validar → comparar metodologías**.
El notebook 09 menciona descriptores; el espacio de datos **no** es el cierre
del proyecto ([`../docs/roadmap.md`](../docs/roadmap.md)).

---

## Requisitos

```bash
cd packing-services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[notebooks]" nbclient nbformat
```

---

## Cómo ejecutar

```bash
cd notebooks
jupyter notebook
```

Ejecuta primero la celda de configuración de cada notebook.

```bash
cd packing-services
source .venv/bin/activate
MPLBACKEND=Agg python notebooks/_execute_all.py
```

Si aparece `ModuleNotFoundError: packing_services`: kernel = `.venv`,
`pip install -e ".[notebooks]"`, reiniciar kernel. `setup_paths()` va **antes**
de importar `display` / `viz` / `runners`.

---

## Instancias showcase (`showcase-v2`)

**Catálogo maestro:** `examples/showcase_master_catalog.json` — SKUs P1–P5
compartidos por 3D-BPP, Container Loading y Single Container. Pallet, stacking
y cartonization usan instancias propias (geometría distinta).

| Grupo | Instancia | Diferenciación |
|-------|-----------|----------------|
| 3D-BPP | `showcase_3d_bpp_instance.json` | best_fit 27 emp. vs extreme_points 22 |
| Híbrido / mejora / metaheurísticas | misma instancia 3D-BPP | refinan layout u orden |
| Container Loading | `showcase_container_loading_instance.json` | weight_aware 27 vs single_container 17 |
| Single Container | `showcase_single_container_instance.json` | best_fit 13 (94%) vs first_fit 16 (89%) |
| Cartonization | `showcase_cartonization_instance.json` | single-box BOX_M vs multi_box |
| Palletization | `showcase_palletization_instance.json` | layer vs stack |
| Stacking-aware | `showcase_stacking_aware_instance.json` | stacking_aware vs stack_based |

Función homogénea: `display.run_and_show_showcase_benchmark(group)`.

Comparación **cruzada** (BED-BPP, un euro-pallet, `input_order`):
`PYTHONPATH=src python scripts/run_joint_single_container.py`
(no está en estos notebooks showcase).

---

## Recorrido

| Notebook | Pregunta |
|----------|----------|
| `00_introduccion_y_vision` | ¿Qué problema y qué prioridad? |
| `01_arquitectura_y_servicios` | ¿Cómo está organizado? |
| `02_demo_3d_bin_packing` | ¿Cómo se empaca? |
| `03_comparacion_de_algoritmos` | ¿Qué metodología 3D-BPP gana aquí? |
| `04_validacion_independiente` | ¿Quién comprueba la solución? |
| `05_container_loading` | ¿Peso y varios contenedores? |
| `06_single_container_loading` | ¿Un solo contenedor? |
| `07_cartonization` | ¿Qué caja del catálogo? |
| `08_catalogo_algoritmos_y_futuro` | ¿Qué hay implementado y cómo se compara? |
| `09_preparacion_espacio_de_datos` | Contratos/descriptores (tema **despriorizado**) |

**Ruta corta:** 00 → 02 → 03 → 08. El 09 es opcional.

---

## `_shared/`

| Archivo | Función |
|---------|---------|
| `loaders.py` | Showcase, builders de benchmark, execute input |
| `runners.py` | Ejecuta servicios sin HTTP |
| `display.py` | KPIs y tablas |
| `viz.py` | Layout 2D y barras |
| `viz_3d.py` | Layout 3D Plotly |

Regenerar desde fuentes: `python notebooks/_build_notebooks.py`.
