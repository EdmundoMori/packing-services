# Notebooks didácticos — `packing-services`

Conjunto de **10 notebooks** (00–09) para explicar el avance del proyecto de forma **visual**
a una audiencia sin conocimiento previo (tutor de tesis, comité, stakeholders).

No sustituyen la documentación técnica (`docs/`) ni los tests: son la **historia
narrada** del proyecto con gráficos y KPIs filtrados.

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

O abrir un notebook concreto en VS Code / Cursor.

**Importante:** ejecuta primero la celda de configuración de cada notebook.

### Ejecutar todos los notebooks de una vez (validación)

```bash
cd packing-services
source .venv/bin/activate
MPLBACKEND=Agg python notebooks/_execute_all.py
```

Esto ejecuta todas las celdas en orden (00→09) y guarda los outputs en los `.ipynb`.

### Si aparece `ModuleNotFoundError: No module named 'packing_services'`

1. Verifica que el kernel sea el venv del proyecto: **`.venv (Python 3.10+)`**.
2. Instala el paquete en modo editable (recomendado):
   ```bash
   cd packing-services
   source .venv/bin/activate
   pip install -e ".[notebooks]"
   ```
3. **Reinicia el kernel** del notebook (Kernel → Restart) y vuelve a ejecutar la celda de configuración.
4. La celda de setup llama a `setup_paths()` **antes** de importar `display`/`viz`/`runners`; si editaste el notebook a mano, respeta ese orden.

---

## Instancias showcase homogéneas (`showcase-v2`)

**Catálogo maestro:** `examples/showcase_master_catalog.json` — SKUs P1–P5 (30 uds) compartidos por 3D-BPP, Container Loading y Single Container.

Cada grupo de benchmark usa una instancia compleja donde los resultados **se diferencian claramente**:

| Grupo | Instancia | Diferenciación en benchmark |
|-------|-----------|----------------------------|
| 3D-BPP | `showcase_3d_bpp_instance.json` | best_fit 27 emp. vs extreme_points 22 |
| Híbrido | misma instancia 3D-BPP | compaction/LS mueven 8–11 piezas |
| Mejora 3D | misma instancia 3D-BPP | relocation/swap/orientation/bin_reduction refinan layout |
| Metaheurísticas 3D | misma instancia 3D-BPP | SA/GRASP/LNS optimizan orden sobre baseline constructivo |
| Container Loading | `showcase_container_loading_instance.json` | weight_aware 27 vs single_container 17 |
| Single Container | `showcase_single_container_instance.json` (altura 70) | best_fit 13 (94%) vs first_fit 16 (89%) |
| Cartonization | `showcase_cartonization_instance.json` | single-box BOX_M vs multi_box varias cajas |

Todos los notebooks usan la función homogénea `display.run_and_show_showcase_benchmark(group)`.

| Notebook | Instancia / enfoque |
|----------|---------------------|
| 00 | Panorama + showcase 3D-BPP |
| 01 | Arquitectura + demo `POST /algorithms/{name}/execute` |
| 02 | Demo visual 3D-BPP vía algorithm execute |
| 03 | Benchmark 3D-BPP (5 constructivos + py3dbp) |
| 04 | Validación sobre solución 3D-BPP |
| 05 | Container Loading + benchmark CL (3 motores) |
| 06 | **Demo Single Container** + benchmark SCL |
| 07 | Cartonization + benchmark (4 criterios de caja) |
| 08 | Catálogo + endpoints por algoritmo + 9 benchmarks |
| 09 | Descriptores por algoritmo / cierre espacio de datos |

---

| Min | Notebook | Mensaje clave |
|-----|----------|---------------|
| 0–5 | `00_introduccion_y_vision` | Problema, brecha, 4 tipos de problema |
| 5–8 | `01_arquitectura_y_servicios` | Arquitectura modular + perfiles benchmark |
| 8–15 | `02_demo_3d_bin_packing` | **Demo visual principal 3D-BPP** |
| 15–22 | `03_comparacion_de_algoritmos` | Comparación rigurosa 3D-BPP |
| 22–26 | `04_validacion_independiente` | Juez independiente |
| 26–30 | `05_container_loading` | Multi-contenedor + peso |
| 30–34 | `06_single_container_loading` | **Un camión** + benchmark SCL |
| 34–38 | `07_cartonization` | Selección de caja + benchmark |
| 38–44 | `08_catalogo_algoritmos_y_futuro` | Catálogo + 9 benchmarks |
| 44–46 | `09_preparacion_espacio_de_datos` | Cierre e integración futura |

**Ruta corta (20 min):** 00 → 02 → 03 → 06 → 08 → 09

---

## Contenido de cada notebook

| Notebook | Pregunta que responde |
|----------|----------------------|
| `00_introduccion_y_vision` | ¿De qué va el proyecto y por qué importa? |
| `01_arquitectura_y_servicios` | ¿Cómo está organizado el sistema? |
| `02_demo_3d_bin_packing` | ¿Cómo se empacan cajas en contenedores? |
| `03_comparacion_de_algoritmos` | ¿Cuál algoritmo 3D-BPP es mejor y por qué? |
| `04_validacion_independiente` | ¿Quién comprueba que la solución es correcta? |
| `05_container_loading` | ¿Qué pasa con el límite de peso y la distribución? |
| `06_single_container_loading` | ¿Cómo lleno un solo camión? |
| `07_cartonization` | ¿Qué caja elijo para un pedido? |
| `08_catalogo_algoritmos_y_futuro` | ¿Qué hay implementado y cómo se compara? |
| `09_preparacion_espacio_de_datos` | ¿Cómo se publicaría en un espacio de datos? |

---

## Módulo compartido `_shared/`

| Archivo | Función |
|---------|---------|
| `loaders.py` | Carga `examples/showcase_*`, builders de benchmark y `build_algorithm_execute_input` |
| `runners.py` | Ejecuta servicios sin API HTTP (`run_algorithm_execute`, benchmark, validate) |
| `display.py` | KPIs, `show_execute_result`, tablas resumidas, badges válido/inválido |
| `viz.py` | Gráficos: layout 2D, barras, peso, catálogo de cajas |

---

## Regenerar notebooks

Si editas `_build_notebooks.py` (fuentes de las celdas):

```bash
python notebooks/_build_notebooks.py
MPLBACKEND=Agg python notebooks/_execute_all.py   # validar ejecución
```

---

## Qué se muestra vs qué se oculta

**Se muestra:** utilización %, piezas empacadas, validez, ranking, caja elegida,
piezas movidas (mejora local), layouts 2D (vista superior + lateral).

**Se oculta:** JSON completo, coordenadas en tablas, metadata de ejecución detallada,
catálogo completo de 52 algoritmos (solo resumen por estado).
