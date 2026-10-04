# Evaluación de desarrollo

La integridad del entrenamiento pasó y la evaluación se ejecutó una vez sobre los 40 pedidos del manifiesto, veinte por target. Hay 360 casos con captura, auditoría y U_geom recalculada. No hay pendientes, fallos de método ni errores del evaluador. `physical_stability_verified` permanece null. OnlineBPH y el test final no se ejecutaron.

El protocolo congelado no fija un reloj de desarrollo. Los límites de este paso son los pedidos aquí: 300 s por caso y 3600 s globales. No modifican el protocolo.

## Referencia

Medias de U_geom con igual peso por pedido:

| Regla fija | Media |
| --- | ---: |
| greedy_best_fit | 0.649069 |
| lowest_top | 0.646783 |
| least_height_increase | 0.644179 |

La referencia es `greedy_best_fit`. La diferencia con la segunda no entra en el empate de 1e-12.

## Semillas PPO

El agregado da el mismo peso a cada pedido y después a cada semilla. Las tres semillas empatan con la referencia en los 40 pedidos, tolerancia 1e-9: 0 victorias, 40 empates, 0 derrotas. La media RL−referencia es 0 en cada semilla y en cada target.

| Semilla | RL−referencia | RL−uniforme de la misma semilla | Fallos |
| --- | ---: | ---: | ---: |
| 101 | 0 | −0.002193 | 0 |
| 102 | 0 | −0.004492 | 0 |
| 103 | 0 | 0.012487 | 0 |

La media de las tres diferencias con la uniforme es 0.001934. En las 1577 decisiones de desarrollo de cada semilla, el argmax eligió `greedy_best_fit`. Esa frecuencia describe la política determinista en estos pedidos. No se usa como causa del resultado ni como prueba de generalización a partir de los retornos de train.

Frente a las otras reglas fijas, la media RL−lowest_top es 0.002286 y la media RL−least_height_increase es 0.004889, iguales en las tres semillas.

## Puerta

1. Media RL−mejor regla fija ≥ 0.005: 0. No se cumple.
2. Diferencia positiva en al menos dos semillas: ninguna semilla supera 0. No se cumple.
3. Agregado RL−referencia ≥ 0 en cada target: 0 en euro-pallet y en rollcontainer. Se cumple.
4. Media RL−uniforme > 0: 0.001934. Se cumple.
5. Integridad y evaluación completa: se cumple.

La puerta no se cumple. Esta configuración se cierra. No hay más entrenamiento ni elección de semilla.

## Tiempo y memoria

El muro de desarrollo fue 471.250 s. El máximo de la suma muestreada de VmRSS del padre y de los workers vivos fue 1339180 KB, en 688 muestras. El `ru_maxrss` del padre fue 229020 KB. Dos workers y un hilo de Torch por worker.
