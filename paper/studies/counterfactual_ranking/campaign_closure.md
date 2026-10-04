# Cierre de la campaña counterfactual_ranking

Campaña cerrada. Decisión: no avanzar con esta configuración. No se selecciona semilla ni otro brazo. El test final no se abre ni se ejecuta. No hay continuación automática. Esta decisión no es una refutación universal del aprendizaje de preferencias.

La verificación de este cierre releyó la evidencia ya guardada. No ejecutó episodios, ajustes ni continuaciones nuevas. Las tres medias de development coinciden con `learning_packing/aggregate.json`: preferencias−clasificación `0.03094863126240079`, preferencias−Greedy `-0.019783628885582008`, clasificación−Greedy `-0.050732260147982794`.

## 1. Pregunta y contrato

La pregunta del protocolo de aprendizaje es si aprender diferencias de retorno entre candidatas mejora el packing frente a aprender solo la identidad de la mejor candidata, con los mismos datos, la misma observabilidad, la misma arquitectura y el mismo motor. El texto está en `learning_protocol_frozen.json`, SHA256 `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`.

El contrato geométrico es el del paso 16: secuencia original, un contenedor del target propio, `p=s=1`, rotaciones permitidas por el contrato, contención y no solape. Peso, estabilidad y load-bearing quedan inactivos. El episodio se detiene en el primer ítem actual sin candidata legal. `physical_stability_verified` permanece `null`.

El actor usa 17 columnas del estado presente, del ítem actual y de la candidata. No recibe el sufijo, `Q_hat`, el identificador del pedido ni la etiqueta Greedy. La red es `Linear(17, 64) → ReLU → Linear(64, 1)`.

Este protocolo no es el de la campaña compacta ya cerrada. La configuración `a=1, b=0.5, c=0` sigue abandonada. No hay equivalencia entre esos protocolos.

## 2. Diagnóstico privilegiado

El diagnóstico, en `diagnostic_review.md` y `diagnostic_results/`, usó 20 pedidos y el sufijo real. Reutilizó 4 continuaciones de preflight y ejecutó 391 nuevas: 395 en total, 100 estados completos y 0 retornos desconocidos. `A_hat` fue positivo en 96 alternativas, cero en 234 y negativo en 65. En 47 de 100 estados, alguna candidata examinada superó a Greedy. La media de `f_i` fue 0.47 y la de `m_i` fue 0.02460370349702381, con igual peso por pedido.

Eso es una oportunidad entre candidatas examinadas en estados de una trayectoria Greedy. No es el rendimiento de una política, ni una cota, ni una comparación con PCT. La clase `margen_suficiente_para_disenar_el_experimento_de_aprendizaje` no autorizó el entrenamiento por sí sola. El reloj usado fue 1223.2690794659975 s de un presupuesto de 14400 s.

## 3. Construcción de etiquetas

`learning_labels_verification.json` registra 36 pedidos, 144 estados completos y 553 continuaciones. Train tiene 24 pedidos y development 12. No hay estados incompletos, claves duplicadas ni `Q_hat` desconocidos. De las 553 alternativas, 74 superan a Greedy, 392 empatan y 87 quedan por debajo, con tolerancia `1e-9`.

Cada pedido aporta cuatro estados etiquetados, elegidos por cuantiles sobre la trayectoria Greedy. En la trayectoria había más estados con elección: 660 y 359 en train, 291 y 177 en development, según el mismo archivo. El tope de etiquetado es cuatro candidatas por estado, incluida Greedy. `Q_hat` es el retorno de una continuación Greedy del sufijo real. El actor no recibe ese sufijo.

La normalización usa las 368 filas completas de train. Development aporta 185 filas y no entra en las medias ni en las escalas. Dos columnas quedan constantes después de normalizar: `item_can_rotate` y `bin_index_n`, en `learning_training/signal_diagnostic.json`. Se conservaron.

## 4. Comparación controlada de objetivos

Los dos brazos comparten arquitectura, datos, normalización, semillas e inicialización. Classification usa entropía cruzada con objetivo uniforme entre los máximos empatados. Preferences usa pares ordenados por diferencia de retorno y una penalización de empates. Cada estado pesa uno. Las pérdidas no se comparan entre sí: tienen definición y escala distintas.

Semillas 11, 23 y 37. Cuarenta épocas, un paso de Adam por época sobre los 96 estados de train, sin early stopping. La última capa parte de cero. El checkpoint es la época 40.

Hubo dos lanzamientos del ejecutor. `learning_training_aborted_missing_checkpoint_dir/` falló al guardar: las tres semillas terminan con el error de `torch.save` porque faltaba el directorio de checkpoints. No dejó pesos, historiales ni ranking. Si en ese proceso hubo pasos de Adam, queda desconocido. Si alguien leyó métricas antes del relanzamiento, no está documentado. El fuente de ese ejecutor no se recuperó.

`learning_training/` es posterior. Los hashes de inicialización y de permutaciones coinciden con los del intento abortado, y esos hashes se calculan antes del bucle de cada brazo. El optimizador se crea de nuevo dentro de `train_arm`. Los hiperparámetros de los dos manifiestos coinciden. No es un único intento de toda la campaña, y tampoco hay evidencia de que se eligiera un resultado entre varios ajustes completos. La nota está en `learning_packing/provenance_aborted_attempt.md`.

## 5. Ranking sobre estados Greedy

`learning_training/ranking/` evalúa los seis modelos sobre las candidatas ya etiquetadas. El regret de un estado es el máximo `Q_hat` examinado menos el `Q_hat` de la candidata de mayor logit. En development, con igual peso por pedido, el regret fue:

| Semilla | Classification | Preferences |
| ---: | ---: | ---: |
| 11 | 0.015052534412202381 | 0.01693572668650794 |
| 23 | 0.017719938926091267 | 0.016673668464781747 |
| 37 | 0.013933372085813493 | 0.01949079086061508 |

Es la calidad de ordenación entre las candidatas etiquetadas de estados Greedy. No es el rendimiento de un episodio completo. El ranking no eligió época, semilla ni brazo.

## 6. Episodios completos

`learning_packing/` contiene 84 claves únicas: 12 GreedyBestFit, 36 classification y 36 preferences. `packing_verification.json` está `completed`, con cero fallos de método y cero errores del evaluador. Greedy se ejecutó de nuevo en el mismo arnés. No se reconstruyó desde máximos de `Q_hat`.

Durante el packing, el máximo de candidatas legales observado en un paso va de 16 a 142. El etiquetado no pasó de cuatro.

Medias de `U_geom`, primero por pedido y después por semilla:

| Contraste | Agregado | Euro-pallet | Rollcontainer |
| --- | ---: | ---: | ---: |
| preferencias − clasificación | 0.03094863126240079 | 0.0013134331597222137 | 0.06058382936507937 |
| preferencias − Greedy | -0.019783628885582008 | -0.03033486689814815 | -0.009232390873015866 |
| clasificación − Greedy | -0.050732260147982794 | -0.031648300057870365 | -0.06981622023809524 |

En las tres semillas, la media preferencias−clasificación es positiva: 0.03409619760664681, 0.02844305555555555 y 0.030306640625000002. Las tres medias preferencias−Greedy son negativas.

El regret de la sección 5 no anticipa de forma uniforme esta comparación. En las semillas 11 y 37 el regret de classification es menor que el de preferences, y en los episodios preferences queda por encima de classification. Son medidas distintas. La diferencia no identifica una causa.

La puerta exige las cinco condiciones de `learning_protocol_frozen.json`. Cumplen la ventaja media sobre classification, el signo en al menos dos semillas y la integridad. No cumplen la ventaja media sobre Greedy de 0.01 ni el signo no negativo en cada target. Clasificación: no avanzar con esta configuración.

## 7. Decisión y limitaciones

No se amplían datos, épocas, arquitectura ni presupuesto. No se publica un test final. Que classification quede por debajo de preferences y de Greedy no autoriza cambiar el objetivo.

Límites de este piloto, que no son causas demostradas:

- 24 pedidos de train y 12 de development.
- Cuatro estados etiquetados por pedido.
- Hasta cuatro candidatas etiquetadas, frente a hasta 142 candidatas legales en el packing.
- Estados de una trayectoria Greedy, distintos de los estados que visita el actor.
- Futuro privilegiado al construir `Q_hat`, y dependencia de una continuación concreta.
- Dos columnas constantes conservadas.
- Cuarenta actualizaciones full-batch por ajuste.
- Variación entre semillas y entre targets.
- Procedencia solo parcial del intento abortado.

Los estados de un mismo pedido no son independientes. No se calculó significación estadística. No hay verificación de estabilidad física. No hay comparación con PCT ni con el estado del arte. No se infiere una inferioridad general de clasificación, preferencias o PPO.

## 8. Valoración para una publicación posterior

Lo que podría motivar un estudio empírico es la combinación de tres observaciones acotadas: en el diagnóstico aparecieron alternativas de mayor retorno; en este piloto preferences superó a classification en `U_geom` medio en las tres semillas; y ese ranking sobre estados etiquetados no anticipó de forma uniforme el resultado de los episodios. También queda documentado el desajuste entre cuatro candidatas etiquetadas y el conjunto legal completo.

Para sostener una contribución generalizable faltan, entre otras cosas, un test no consultado durante el diseño, más pedidos, estados visitados por la propia política, un conjunto de candidatas alineado con el que usa el actor, una incertidumbre cuantificada y una comparación externa diseñada de antemano. El repositorio reproducible fija lo que se hizo en este piloto. No convierte por sí solo ese piloto en una muestra de la que se pueda extrapolar.

Lo que puede publicarse ya es un informe técnico de esta campaña: protocolo, etiquetas, ajustes, episodios, puerta incumplida y límites. Ese informe no es un artículo presentado como aceptable para una revista. No se recomienda aquí una revista, porque no se han contrastado sus requisitos, y no se promete aceptación.
