# Plan de validación (R02 sintético ejecutado)

El criterio de éxito es un **recurso correcto, reutilizable y utilizable por RL**.
No exige superar una heurística ni obtener mejora positiva.

## Verificaciones (R02)

| ID | Comprobación | Estado |
|----|--------------|--------|
| V1 | Observabilidad sin fuga de futuro | Pass (`test_observation_independent_of_suffix`) |
| V2 | Legalidad / identidades de acciones | Pass |
| V3 | Rewards vs \(U_{\mathrm{geom}}\) auditado | Pass (volumen AABB recompuesto) |
| V4 | Terminación vs truncación | Pass |
| V5 | Continuidad de transiciones | Pass (verifier) |
| V6 | Persistencia atómica / manifiesto | Pass |
| V7 | Semilla + política de comportamiento registradas | Pass (metadatos; reproducibilidad fuerte diferida) |
| Engine | Motor post-C04 | Pass |
| Loader | Solo campos agente | Pass |

V8 (update PPO mínimo) **no** se ejecuta en R02 (no entrenamiento).

## Pendiente post-preflight

- Tamaño final del corpus real.
- Presupuesto de pared extrapolado.
- Manifiestos train/dev/test industriales.
