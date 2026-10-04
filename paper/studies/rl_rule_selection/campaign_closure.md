# Cierre de rl_rule_selection

Esta configuración PPO completó el presupuesto previsto, pero su política determinista seleccionó Greedy en todas las decisiones observadas de desarrollo y no superó la puerta de avance.

No se selecciona semilla. El test final no se abre. No se amplía el presupuesto. No hay continuación automática. `physical_stability_verified` permanece null. Este cierre no ejecuta episodios, entrenamiento ni reconstrucciones de trayectorias.

Se detiene la búsqueda experimental de mejora algorítmica en estas configuraciones. Se conserva la infraestructura y la evidencia. No se inicia otra campaña sin una pregunta y justificación nuevas.

El material puede consolidarse como informe técnico reproducible. No es un artículo de superioridad ni una promesa de publicación.

## Verificación releída

El SHA256 de `protocol_frozen.json` es `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`.

Cada semilla, 101, 102 y 103, tiene 6144 decisiones, doce actualizaciones y 192 pasos de Adam. El historial recorre 512, 1024, …, 6144, con 16 pasos en cada actualización. El checkpoint final es byte a byte el último:

| Semilla | SHA256 de `checkpoint_final.pt` |
| --- | --- |
| 101 | `9aac6e069a7c49dd317b1c6b8099b355d1c668c7ee2ca81846421c4179606fd3` |
| 102 | `7b0127d27915709aa9854f5ac0f00cf7839a955a4537daa600b07c2042f0df27` |
| 103 | `8ac905a3760f75b5a033e599457e67bfc4a2e8f130bdd2bbf0d4275a967ad90e` |

Hay 360 `result.json` únicos, todos con estado `ok`, captura y auditoría de geometría válida. Veinte pedidos son euro-pallet y veinte rollcontainer. Las medias de las reglas fijas, recalculadas desde `raw_u_geom` de cada pedido, son:

- `greedy_best_fit`: 0.6490688532366071
- `lowest_top`: 0.6467826590401785
- `least_height_increase`: 0.6441794205729167

La referencia, por mayor media y con el desempate de 1e-12, es `greedy_best_fit`. La diferencia RL−referencia es 0 en las tres semillas y en los dos targets. El máximo absoluto de esa diferencia por pedido es 0. Cada semilla eligió `greedy_best_fit` en 1577 de 1577 decisiones de desarrollo. Las condiciones de la puerta quedan false, false, true, true, true. No apareció discrepancia con las cifras guardadas en `development_verification.json`.

## Igualdad comprobada en las capturas

En las 120 parejas de semilla PPO y pedido, la captura de PPO y la de `greedy_best_fit` coinciden en el plan guardado: mismo identificador de ítem colocado, misma posición `flb_mm`, mismas dimensiones orientadas y la misma lista de no colocados, incluido el motivo. Esa comparación no se infiere del volumen. La igualdad de U_geom es otro hecho: también se da en las 120 parejas, con diferencia absoluta 0. La elección de la regla Greedy es un tercero: 1577 de 1577 decisiones por semilla.

## Límites

Las observaciones de las 6144 decisiones de entrenamiento no están en el historial. El bootstrap del episodio cortado y la log_prob antigua se respaldan en el código congelado, en las pruebas y en los contadores. No se recalcularon desde rollouts persistidos. Esto no es una auditoría exhaustiva de cada update. No hay evidencia, en lo guardado, de un error de PPO, y tampoco se afirma que no pudiera existir uno fuera de esos contadores.

Superar en media a la selección uniforme no se presenta como mejora aprendida. El sesgo inicial no se declara causa del resultado. Entrenar más no se propone como remedio. No hay superioridad frente a PCT ni frente a la literatura, ni inferioridad general del aprendizaje, ni equivalencia estadística entre métodos.

## Relación con el trabajo anterior

Estas campañas no se suman. Cada línea es la evidencia de su propio protocolo y de su propia muestra.

1. El actor histórico, en la evaluación independiente de 200 pedidos, sigue con resultado no concluyente.
2. El selector compacto incumplió su puerta. La configuración `a=1`, `b=0.5`, `c=0` permanece abandonada.
3. Las preferencias contrafactuales superaron a la clasificación en su desarrollo y quedaron por debajo de Greedy. Esa campaña está cerrada en `studies/counterfactual_ranking/campaign_closure.md`.
4. La selección PPO de reglas, en este desarrollo, se comportó como Greedy determinista y no pasó su puerta.

Son evidencias acotadas de estas configuraciones. No refutan en general los modelos aprendidos.

## Decisión

Se detiene la búsqueda experimental de mejora algorítmica en estas configuraciones. Se conserva la infraestructura y la evidencia. No se inicia otra campaña sin una pregunta y justificación nuevas.
