# Evidencia y afirmaciones de rl_rule_selection

Cada fila usa la evidencia de este estudio o, cuando se indica, la de una campaña anterior sin mezclar sus números. La verificación de cierre releyó artefactos. No generó episodios ni trayectorias.

| Afirmación | Evidencia | Alcance | Límite | Estado |
| --- | --- | --- | --- | --- |
| El protocolo congelado es el SHA256 `61923d12…50b9c25` | `protocol_frozen.json` | Este piloto | No es preregistración confirmatoria | Observado |
| Cada semilla completó 6144 decisiones, 12 actualizaciones y 192 pasos de Adam | `training/seed_*/seed_manifest.json` e `history.jsonl` | Semillas 101, 102 y 103 | El reloj de 4800 s no fue el corte | Observado |
| El checkpoint final es el de la última actualización | SHA256 idéntico de `checkpoint_final.pt` y `checkpoint_last.pt` | Las tres semillas | No se eligió por recompensa de train | Observado |
| Desarrollo tiene 360 casos únicos, completos y auditados | `development/cases/*/result.json`, capturas y auditorías | 40 pedidos, veinte por target | Un intento por caso | Observado |
| La referencia es `greedy_best_fit` | Medias recalculadas 0.6490688532366071, 0.6467826590401785 y 0.6441794205729167 | Estos 40 pedidos | El desempate de 1e-12 no hizo falta | Observado |
| RL−referencia es 0 en las tres semillas | Diferencia por pedido, máximo absoluto 0 | Igual peso por pedido y después por semilla | No es equivalencia estadística | Observado |
| El argmax eligió Greedy en 1577 de 1577 decisiones por semilla | `rule_counts` de los 120 casos PPO | Decisiones de desarrollo ya guardadas | No explica por qué el entrenamiento llegó ahí | Observado |
| El plan guardado de PPO y de Greedy coincide | 120 de 120 capturas: ítem, `flb_mm`, dimensiones orientadas y no colocados | Esas parejas | No se deduce solo de U_geom | Observado |
| La puerta queda false, false, true, true, true | Operadores del protocolo sobre las medias recalculadas | Esta configuración | No cierra otras arquitecturas | Observado |
| Las observaciones de train no se guardaron | Cero campos de observación en los tres `history.jsonl` | Auditoría de los updates | Bootstrap y log_prob antigua no se recalcularon desde rollouts | Observado |
| No se selecciona semilla ni se abre el test | `continuation_decision.md` | Este cierre | No hay continuación automática | Observado |
| El actor histórico es no concluyente | `paper/reviews/08_independent_evaluation_run.md` y el cierre de la fase 18 | Esa evaluación de 200 pedidos | No se suma a este piloto | Observado en su campaña |
| El selector compacto incumplió su puerta | `paper/reviews/17_compact_calibration_run.md` | `a=1`, `b=0.5`, `c=0` | Protocolo distinto | Observado en su campaña |
| Las preferencias superaron a la clasificación y quedaron bajo Greedy | `studies/counterfactual_ranking/campaign_closure.md` | Doce pedidos de ese desarrollo | No se agrega con las medias de este estudio | Observado en su campaña |
| Superioridad frente a PCT o a la literatura | No hay esa comparación en este desarrollo | — | OnlineBPH no se ejecutó aquí | No respaldado |
| Inferioridad general del aprendizaje por refuerzo | Solo esta puerta y estas 40 órdenes | — | Un resultado local no generaliza el método | No respaldado |
| El sesgo inicial causó el empate con Greedy | El sesgo final sigue cerca de [1, 0, 0] y el argmax fue Greedy | Descripción, no identificación causal | Falta el contrafactual de otro sesgo | No respaldado |
| Entrenar más resolvería el empate | No se probó otro presupuesto | — | El presupuesto previsto ya se completó | No respaldado |
| Superar a la uniforme es una mejora aprendida | La media RL−uniforme es 0.0019338707527282 y RL−Greedy es 0 | La puerta pide las dos cosas, entre otras | La condición 4 sola no abre el test | No respaldado |

## Decisión

Se detiene la búsqueda experimental de mejora algorítmica en estas configuraciones. Se conserva la infraestructura y la evidencia. No se inicia otra campaña sin una pregunta y justificación nuevas.
