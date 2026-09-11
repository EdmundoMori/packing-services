# Fase 2: Generación de Etiquetas P2O

## Descripción

Esta fase genera las etiquetas de entrenamiento mediante la metodología Packing-to-Online (P2O).

## Simulador

Se utiliza el bucle online del repositorio principal, compuesto por:
- `session`: gestión de la sesión de empaquetado
- `ValidatorMask`: máscara del validador para filtrar colocaciones legales
- `encode_option`: codificación de opciones de colocación

## Maestro de Etiquetado

El maestro predeterminado es `privileged_volume_ep`, que selecciona:
1. El ítem con mayor volumen del buffer de observación
2. El mejor punto extremo (EP) disponible

## Características del Etiquetado

- La etiqueta es un **índice** entre las candidatas que ya son legales según el validador
- Tasa de etiquetado (`label_rate`): 1.0 cuando existen opciones disponibles

## Exclusiones

Los 5 pedidos de demostración (`examples/5_bed-bpp.json`) no se incluyen en la recolección de transiciones.

## Artefactos Generados

```
data/train/transitions_pXsY.pkl
data/val/transitions_pXsY.pkl
data/test/transitions_pXsY.pkl
```

Donde `X` e `Y` representan los parámetros `lookahead_p` y `select_s` respectivamente.
