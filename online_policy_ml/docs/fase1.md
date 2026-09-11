# Fase 1: Preparación de Datos y Splits

## Descripción

Esta fase establece la base de datos para el entrenamiento de la política online.

## Fuente de Datos

- **Dataset:** `bed-bpp_v1.json`
- **Tamaño:** aproximadamente 10,000 pedidos
- **Unidades:** milímetros (mm)

## Holdout de Producto

El archivo `examples/5_bed-bpp.json` contiene 5 identificadores de pedido (`order_id`) que están **bloqueados** y no se utilizan en ninguna fase del entrenamiento.

## Estrategia de Split

- **Granularidad:** por pedido (no por ítem)
- **Semilla aleatoria:** 42
- **Proporciones:** 70% entrenamiento / 15% validación / 15% test

## Subconjunto de Trabajo

Para las fases siguientes se utiliza un subconjunto de los pedidos más cortos de cada split:
- Entrenamiento: 24 pedidos
- Validación: 8 pedidos
- Test: 8 pedidos

## Restricciones

Esta fase no modifica el código de ejecución (`execute`) ni el encoder de características.
