# Fase 4: Escalado de Datos y Revalidación

## Descripción

Esta fase amplía el conjunto de entrenamiento utilizando una muestra más representativa del split completo, en lugar de limitarse a los pedidos más cortos.

## Datos de Entrenamiento

- **Muestra:** aleatoria del split completo
- **Proporciones:** 80 entrenamiento / 20 validación / 20 test
- **Diferencia con fase 3:** no se restringe a pedidos cortos

## Componentes Heredados

Se mantienen sin cambios:
- Encoder de características
- Maestro P2O
- Contrato de exportación

## Artefactos Generados

| Directorio | Contenido |
|------------|-----------|
| `data/scale/train/` | Datos de entrenamiento escalados |
| `data/scale/val/` | Datos de validación escalados |
| `data/scale/test/` | Datos de test escalados |
| `artifacts/models/fase4/` | Modelos entrenados en esta fase |
| `artifacts/models/fase3/` | Copia de respaldo de modelos fase 3 |

## Criterio de Promoción a Producción

Los artefactos en `artifacts/models/*.json` y `*.pt` se actualizan únicamente si el MLP con parámetros `p=1, s=1`:
1. **Mejora o iguala** la utilización de volumen en validación scale
2. Mantiene `is_valid=True`

## Consideraciones para el Régimen `p=3, s=2`

En este régimen:
- No se ejecuta el heurístico (el lookahead es computacionalmente costoso en pedidos medianos)
- Se comparan los pesos del placeholder y los de fase 3 contra los de fase 4
