# Cierre de la campaña corta

Cierre del 2026-10-03 sobre `91ee3ed10cb028881c2d0823239c3203759b429d`. No se ejecutó packing, calibración, entrenamiento ni evaluación test adicionales. Este informe reúne evidencia técnica ya publicada o recién verificada. No es un artículo científico ni un texto listo para envío. Podría apoyar más adelante una investigación con otra hipótesis, todavía no definida.

Los protocolos no se suman. Un delta del teacher, uno de la ablación de normalización y uno del selector compacto pertenecen a contratos distintos.

## Lo que queda registrado

1. El actor histórico, en la evaluación de 200 pedidos, sigue no concluyente. Evidencia: [`08_independent_evaluation_run.md`](08_independent_evaluation_run.md) y [`../results/07_independent_evaluation/`](../results/07_independent_evaluation/).
2. La configuración de normalización quedó abandonada por su propia regla. Evidencia: [`13_normalization_development.md`](13_normalization_development.md).
3. El teacher no mostró ventaja media frente a GreedyBestFit en su diagnóstico. La media de delta fue -0.021117453869047634. Evidencia: [`15_teacher_utility_run.md`](15_teacher_utility_run.md).
4. El contrato geométrico nuevo y la adaptación de OnlineBPH quedaron auditados en una verificación de cinco pedidos de desarrollo. Evidencia: [`16_protocol_and_baseline_feasibility.md`](16_protocol_and_baseline_feasibility.md) y [`16a_onlinebph_capture_contract.md`](16a_onlinebph_capture_contract.md). El smoke original de OnlineBPH sigue en `method_failure` porque el arnés rechazó la captura; no se recalificó.
5. El selector compacto mejoró la media de train y no alcanzó la puerta en desarrollo. Evidencia: [`17_compact_calibration_run.md`](17_compact_calibration_run.md) y [`../results/17_compact_calibration/`](../results/17_compact_calibration/).

## Comprobación del paso 17, sin reejecutar

Hay 32 configuraciones y 40 pedidos de train, 20 por target. Desarrollo tiene 50 pedidos, 25 por target. Las claves esperadas son 1520 y hay 1520 `result.json` únicos, sin claves de más ni de menos. Cada caso tiene captura, auditoría, entrada, timings y resultado. `worker_status` es `ok` en los 1520. `physical_stability_verified` es null. El protocolo 16 sigue con `grid_executed` falso: esa cuadrícula se ejecutó bajo el protocolo 17, no reescribiendo el 16.

`freeze.json` permanece como el registro anterior a la corrida, con `grid_executed` falso. La corrida completada está en `manifest.json`. Las medias de train y las de desarrollo, recalculadas desde los resultados por pedido, coinciden con las tablas guardadas. No hubo que corregir archivos.

Top 3 de train: `a1_b0.5_c0`, `a0_b1_c0`, `a0.5_b1_c0`. La elegida en desarrollo es `a=1`, `b=0.5`, `c=0`. La condición A no se cumple, la B tampoco y la C sí. No se eligió otra configuración después de la puerta. La decisión de esa cuadrícula sigue siendo abandonarla.

En los 40 pedidos de train, la configuración `a=b=c=0` y GreedyBestFit coinciden en el plan guardado: mismo ítem, mismas coordenadas y mismas dimensiones orientadas, y la misma lista de no colocados. No es solo la misma `U_geom`. Esa comparación no existe en desarrollo, porque la configuración cero no se ejecutó ahí.

## Tiempos, por separado

La pared de reloj de la calibración es 5088.675920605001 segundos. Hubo cuatro procesos concurrentes. Sumar los tiempos de los 1520 casos no produce esa pared, porque los procesos se solapan:

- Bucle de packing, suma: 2685.6848721459537 segundos.
- Arranque, suma: 2840.290848554978 segundos.
- Auditoría y escritura, suma: 11134.479057560948 segundos.
- Pared de proceso de los workers, suma: 6501.899406375003 segundos.

Esas sumas no son un coste total de CPU ni una comparación de eficiencia.

## Límites

No hay superioridad demostrada frente a PCT ni frente al estado del arte. El smoke de OnlineBPH solo verificó la integración. No hubo comparación externa completa del selector calibrado. No hubo confirmación del selector nuevo. No se verificó estabilidad física. Este resultado no invalida de forma universal el BC, el PPO, la normalización ni la calibración de heurísticas.

## Decisión

Cerrar esta vía experimental. No continuar a comparación externa ni test confirmatorio con esta configuración.
