# R03: cierre del preflight real BED-BPP-RL

## Procedencia

Primer intento conservado en `preflight_real_run_20261006T1526/`.
Los 16 workers fallaron al importar el entorno histórico.
No produjo episodios confirmados; su campo `real_orders_packed=true`
no constituye evidencia de placements y se conserva sin reescribir.

La recuperación explícita está en `preflight_real_recovery_02/`.
El runtime corregido pasó una prueba sintética antes de la recuperación.
El código local adicional se identifica mediante los hashes del manifiesto;
el HEAD por sí solo no identifica esos archivos entonces no versionados.

## Verificación

16 episodios, 4 pedidos, 648 transiciones.
16 terminaciones naturales y 0 truncaciones.
Verificación desde artefactos y copia portable aceptadas.
Sin entrenamiento PPO ni nuevo packing durante la re-verificación.

Pared de recuperación: 29.299867630000 s.
Cargo anterior: 3.563556382000 s.
El cargo anterior es una contabilización operativa, no una reconstrucción
exacta de toda la duración del primer intento.

| Pedido | Política | Transiciones | Cierre | Retorno observado |
|---|---|---:|---|---:|
| 00101784 | fixed_greedy_best_fit | 44 | all_items_placed | 0.619633333333 |
| 00101784 | fixed_lowest_top | 44 | all_items_placed | 0.619633333333 |
| 00101784 | fixed_least_height_increase | 44 | all_items_placed | 0.619633333333 |
| 00101784 | uniform_rules | 44 | all_items_placed | 0.619633333333 |
| 00101736 | fixed_greedy_best_fit | 58 | all_items_placed | 0.617856250000 |
| 00101736 | fixed_lowest_top | 58 | all_items_placed | 0.617856250000 |
| 00101736 | fixed_least_height_increase | 58 | all_items_placed | 0.617856250000 |
| 00101736 | uniform_rules | 58 | all_items_placed | 0.617856250000 |
| 00107463 | fixed_greedy_best_fit | 18 | no_legal_candidate_after_placement | 0.534579464286 |
| 00107463 | fixed_lowest_top | 27 | no_legal_candidate_after_placement | 0.783374107143 |
| 00107463 | fixed_least_height_increase | 23 | no_legal_candidate_after_placement | 0.700838392857 |
| 00107463 | uniform_rules | 23 | no_legal_candidate_after_placement | 0.700838392857 |
| 00102588 | fixed_greedy_best_fit | 37 | no_legal_candidate_after_placement | 0.696309821429 |
| 00102588 | fixed_lowest_top | 37 | no_legal_candidate_after_placement | 0.696309821429 |
| 00102588 | fixed_least_height_increase | 39 | no_legal_candidate_after_placement | 0.729452678571 |
| 00102588 | uniform_rules | 36 | no_legal_candidate_after_placement | 0.675238392857 |

## Interpretación y límites

Las reglas ejercitan el entorno; no se selecciona una política por estos
retornos. Igual volumen no implica igualdad de planes.
La muestra operativa de cuatro pedidos no demuestra la cola de tiempos
ni representa un benchmark de eficacia.

`non_candidate_loop_residual` no mide exclusivamente selección de acción.
Los picos ru_maxrss registrados son idénticos; no se interpretan como
memoria incremental ni como mediciones independientes por episodio.
La comprobación RSS del lanzador es posterior al episodio, no un límite duro.

El corpus confirmado local tiene manifiesto relativo y hashes.
AABB no implica estabilidad física; physical_stability_verified permanece null.
Demostración PPO y corpus definitivo pendientes.

Decisión: preflight_real_verificado_para_disenar_corpus_y_demostracion_RL.
