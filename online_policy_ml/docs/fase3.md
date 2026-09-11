# Fase 3: Entrenamiento, Validación y Exportación

## Descripción

Esta fase entrena los modelos de política y exporta los artefactos para producción.

## Modelos Entrenados

### Modelo Lineal (`linear_v1.json`)

- **Arquitectura:** 35 pesos (correspondientes a `FEATURE_DIM=35`)
- **Función de pérdida:** Softmax Cross-Entropy
- **Uso en producción:** No requiere PyTorch

### Modelo MLP (`mlp_v1`)

- **Arquitectura:** `Linear(35, 64) → ReLU → Linear(64, 1)`
- **Formato de exportación:** Un archivo `.pt` por régimen de parámetros
- **Requisito:** Requiere PyTorch para exportación e inferencia

## Proceso de Validación

La validación compara el rendimiento contra:
1. `online_3d_bpp_heuristic` (heurístico base)
2. Modelo placeholder

Todas las comparaciones se realizan en `packing_mode=online`.

## Prueba de Humo (Smoke Test)

Se verifica que `LearnedPlacementPolicy.from_path` cargue correctamente el modelo y procese 1 pedido de los 5 de demostración, validando que `is_valid=True`.

## Configuración

- **Semilla aleatoria:** 42
- **Restricción:** Los 5 pedidos de demostración no se utilizan para selección de hiperparámetros
