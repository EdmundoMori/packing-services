# Subproyecto: Entrenamiento de Política Online

Documento complementario de [`../README.md`](../README.md).

## Relación con el Proyecto Principal

El objetivo del proyecto **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas (misma entrada, mismo validador, mismas métricas), tanto en modo offline como online.

Este directorio contiene el código de **entrenamiento y exportación** de la política aprendida que utiliza el sistema de producción. **No redefine el objetivo** del repositorio principal; simplemente proporciona los artefactos necesarios para el modo online.

## Datos de Entrenamiento

> **Importante:** Los 5 pedidos de `examples/5_bed-bpp.json` constituyen el **holdout de producto** y no se utilizan para entrenamiento.

---

## Ejecución de los Notebooks

```bash
cd packing-services
source .venv/bin/activate
cd online_policy_ml/notebooks
jupyter notebook
```

---

## Pipeline de Entrenamiento

El entrenamiento sigue un pipeline de 5 fases, cada una documentada en un notebook:

| Notebook | Fase | Artefactos Generados |
|----------|------|---------------------|
| `01_datos_y_splits.ipynb` | Preparación de datos | `data/train\|val\|test/bed_bpp_orders.json` |
| `02_etiquetas_p2o.ipynb` | Generación de transiciones P2O | `data/*/transitions_pXsY.pkl` |
| `03_entrenar_validar_exportar.ipynb` | Entrenamiento con pedidos cortos | `artifacts/models/` |
| `04_escalar_revalidar.ipynb` | Escalado con split completo | `data/scale/` + actualización de `artifacts/models/` si mejora |
| `05_receding_horizon_p3s2.ipynb` | Entrenamiento receding-horizon | `*_rh.pkl` + `mlp_v1_p3s2.pt` si supera validación |

---

## Requisitos de Dependencias

### Para Modelos MLP

```bash
pip install 'packing-services[torch]'
# Alternativa:
pip install torch
```

### Para Modelos Lineales

Los modelos lineales (`linear_v1.json`) no requieren PyTorch.

---

## Modelos de Producción

Los siguientes modelos están disponibles para uso en producción. **No es necesario reentrenar.**

Las rutas son relativas a la raíz del repositorio y pueden utilizarse directamente en el parámetro `parameters.model_path`:

| Uso | Ruta del Modelo | Parámetros |
|-----|-----------------|------------|
| O3DBP (predeterminado) | `online_policy_ml/artifacts/models/mlp_v1_p1s1.pt` | p=1, s=1 |
| Cinta (receding-horizon) | `online_policy_ml/artifacts/models/mlp_v1_p3s2.pt` | p=3, s=2 |
| Linear (sin PyTorch) | `online_policy_ml/artifacts/models/linear_v1.json` | p=1, s=1 |

---

## Endpoints de Producción

Los modelos se invocan mediante los siguientes endpoints:

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/v1/algorithms/drl_policy_3d_bpp/execute` | Ejecución canónica |
| `POST /api/v1/online/learned/execute` | Endpoint dedicado (fuerza `packing_mode=online`) |

### Modelo de Prueba

El archivo `examples/online_policy_linear_v1.json` es un **placeholder para pruebas** (smoke test). No debe utilizarse como modelo de producción.
