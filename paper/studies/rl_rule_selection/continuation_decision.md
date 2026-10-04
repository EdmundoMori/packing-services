# Decisión de continuación

Esta configuración de selección de reglas se cierra. La puerta de desarrollo no se cumple. No se elige semilla, no hay más entrenamiento y no se abre el test. `physical_stability_verified` permanece null. Los cierres anteriores siguen en su sitio: la campaña compacta en la fase `18_short_campaign_closure` y counterfactual ranking en `campaign_closure.md`.

## Controles de fase

| Control | Estado |
| --- | --- |
| Integridad del entrenamiento | Superada. Protocolo `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`. Tres semillas con 6144 decisiones, 12 actualizaciones y 192 pasos de Adam. |
| Desarrollo | Completo: 360/360 casos puntuados. La puerta no se cumple. |
| Revisión científica antes del test | No se abre. La puerta no dejó un candidato. |
| Evaluación final | No se abre. El test no se selecciona ni se ejecuta. |

## Puerta

1. Media RL−mejor regla fija ≥ 0.005: no, el valor es 0.
2. Diferencia positiva en al menos dos semillas: no, las tres diferencias son 0.
3. Agregado no negativo en cada target: sí, 0 y 0.
4. Media RL−uniforme > 0: sí, 0.001934.
5. Integridad y evaluación completa: sí.

## Tiempo acumulado

Hay medición de tres fases de ejecución:

| Fase | Muro medido (s) | Límite |
| --- | ---: | --- |
| Preflight de cuatro pedidos | 134.482 | 300 s por caso y 900 s globales |
| Entrenamiento | 522.952 | 4800 s por semilla y 14400 s globales |
| Desarrollo | 471.250 | 300 s por caso y 3600 s globales |

La suma de esos tres muros es 1128.685 s. El diseño, la selección de pedidos y las pruebas no tienen un reloj de campaña, así que esa suma no es la duración total del trabajo. Dos arranques previos de desarrollo murieron antes de emitir capturas y quedaron aparte; no entran en la suma.

No se amplía el presupuesto de interacciones. El entrenamiento rápido no autoriza más decisiones.
