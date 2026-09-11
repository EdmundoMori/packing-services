# Fase 5: Receding-Horizon para el Régimen `p=3, s=2`

## Descripción

Esta fase implementa un re-etiquetado especializado para el régimen de cinta (`p=3, s=2`) utilizando la estrategia receding-horizon.

## Proceso de Re-etiquetado

- **Maestro utilizado:** `receding_horizon_ep`
- **Alcance:** únicamente el régimen cinta
- **Datos base:** muestra working (pedidos cortos)

## Modelo Afectado

Solo se reentrena `mlp_v1_p3s2`; el modelo `mlp_v1_p1s1.pt` permanece sin modificaciones.

## Artefactos Generados

| Archivo | Descripción |
|---------|-------------|
| `data/train/transitions_p3s2_rh.pkl` | Transiciones receding-horizon (entrenamiento) |
| `data/val/transitions_p3s2_rh.pkl` | Transiciones receding-horizon (validación) |
| `data/test/transitions_p3s2_rh.pkl` | Transiciones receding-horizon (test) |
| `artifacts/models/fase5/*` | Modelos entrenados en esta fase |

> **Nota:** Las transiciones receding-horizon no sobrescriben las transiciones basadas en volumen de fases anteriores.

## Evaluación en Scale

- Se evalúa el rendimiento mediante empaquetado (infraestructura de fase 4)
- No se realiza re-etiquetado en scale (el maestro receding en pedidos de ~40 ítems requiere aproximadamente 1 minuto por pedido)

## Criterio de Promoción a Producción

El modelo `mlp_v1_p3s2.pt` de producción se actualiza únicamente si el candidato RH cumple:

1. **Iguala o mejora** la utilización en validación working
2. Mantiene `is_valid=True`
3. **No empeora** la utilización en validación scale

## Resultado Observado

Tras estabilizar el MLP (accuracy en validación + `lr=3e-4` en cinta), el candidato RH working fue promocionado:
- **Validación working:** empató con el modelo anterior
- **Validación scale:** mejoró respecto al modelo anterior
