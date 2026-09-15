# Notebooks Didácticos

Documento complementario de [`../README.md`](../README.md).

## Propósito

Este directorio contiene **10 notebooks** (00–09) que presentan el avance del proyecto de forma visual. Los notebooks complementan la documentación técnica pero no la sustituyen: el documento principal es el README y el detalle técnico está en `docs/`.

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas:

- **Misma entrada:** formato de datos unificado para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo.
- **Mismas métricas:** indicadores de rendimiento calculados uniformemente.

El sistema soporta tanto el modo `packing_mode=offline` como `packing_mode=online`.

## Hilo Narrativo

El recorrido por los notebooks sigue esta secuencia lógica:

**Inputs homogéneos → Ejecutar (offline u online) → Validar → Comparar**

> **Nota:** El notebook 09 menciona descriptores de servicios, pero el espacio de datos distribuido **no es el cierre del proyecto**. Ver [`../docs/roadmap.md`](../docs/roadmap.md) para las prioridades.

---

## Requisitos de Instalación

```bash
cd packing-services
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[notebooks]" nbclient nbformat
```

---

## Ejecución de los Notebooks

### Ejecución Interactiva

```bash
cd notebooks
jupyter notebook
```

> **Importante:** Ejecutar primero la celda de configuración de cada notebook.

### Ejecución en Batch

```bash
cd packing-services
source .venv/bin/activate
MPLBACKEND=Agg python notebooks/_execute_all.py
```

### Solución de Problemas

Si aparece `ModuleNotFoundError: packing_services`:
1. Verificar que el kernel esté configurado para usar `.venv`
2. Ejecutar `pip install -e ".[notebooks]"`
3. Reiniciar el kernel
4. Asegurar que `setup_paths()` se ejecuta **antes** de importar `display`, `viz` o `runners`

---

## Instancias Showcase (versión 2)

### Catálogo Maestro

El archivo `examples/showcase_master_catalog.json` contiene los SKUs P1–P5, compartidos por 3D-BPP, Container Loading y Single Container.

Los tipos Palletization, Stacking-aware y Cartonization utilizan instancias propias con geometría específica.

### Tabla de Instancias por Grupo

| Grupo | Instancia | Diferenciación Esperada |
|-------|-----------|------------------------|
| 3D-BPP | `showcase_3d_bpp_instance.json` | best_fit: 27 emp. vs extreme_points: 22 |
| Híbrido / Mejora / Metaheurísticas | misma instancia 3D-BPP | Refinan layout u orden |
| Container Loading | `showcase_container_loading_instance.json` | weight_aware: 27 vs single_container: 17 |
| Single Container | `showcase_single_container_instance.json` | best_fit: 13 (94%) vs first_fit: 16 (89%) |
| Cartonization | `showcase_cartonization_instance.json` | single-box BOX_M vs multi_box |
| Palletization | `showcase_palletization_instance.json` | layer vs stack |
| Stacking-aware | `showcase_stacking_aware_instance.json` | stacking_aware vs stack_based |

### Funciones de Utilidad

- **Benchmark showcase:** `display.run_and_show_showcase_benchmark(group)`
- **Comparación cruzada (BED-BPP, euro-pallet):** `PYTHONPATH=src python scripts/run_joint_single_container.py` (no incluido en los notebooks showcase)

### Política Aprendida de Producción

El algoritmo `drl_policy_3d_bpp` utiliza el modelo `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` (RL / PPO) en `packing_mode=online`.

Demostración disponible en `01_arquitectura_y_servicios.ipynb`.

Holdout de producto: `examples/5_bed-bpp.json`.

---

## Recorrido por los Notebooks

| Notebook | Pregunta que Responde |
|----------|----------------------|
| `00_introduccion_y_vision` | ¿Qué problema resolvemos y cuál es el objetivo? |
| `01_arquitectura_y_servicios` | ¿Cómo está organizado el sistema? |
| `02_demo_3d_bin_packing` | ¿Cómo funciona el empaquetado básico? |
| `03_comparacion_de_algoritmos` | ¿Qué metodología 3D-BPP obtiene mejores resultados? |
| `04_validacion_independiente` | ¿Cómo se verifica una solución? |
| `05_container_loading` | ¿Cómo se maneja el peso y múltiples contenedores? |
| `06_single_container_loading` | ¿Cómo se optimiza un solo contenedor? |
| `07_cartonization` | ¿Cómo se selecciona la caja óptima del catálogo? |
| `08_catalogo_algoritmos_y_futuro` | ¿Qué algoritmos están implementados y cómo se comparan? |
| `09_preparacion_espacio_de_datos` | ¿Qué son los contratos y descriptores? (tema despriorizado) |

### Ruta de Lectura Rápida

Para una visión general del proyecto: **00 → 02 → 03 → 08**

El notebook 09 es opcional dado que el espacio de datos está despriorizado.

---

## Módulo `_shared/`

Este módulo contiene utilidades compartidas por todos los notebooks:

| Archivo | Función |
|---------|---------|
| `loaders.py` | Carga de instancias showcase, builders de benchmark, construcción de input para execute |
| `runners.py` | Ejecución de servicios sin HTTP (invocación directa) |
| `display.py` | Visualización de KPIs y tablas |
| `viz.py` | Gráficos de layout 2D y barras comparativas |
| `viz_3d.py` | Visualización de layout 3D con Plotly |

### Regeneración de Notebooks

Para regenerar los notebooks desde las fuentes:

```bash
python notebooks/_build_notebooks.py
```
