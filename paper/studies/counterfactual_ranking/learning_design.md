# Diseño del experimento de aprendizaje

Este documento recoge el diseño. El protocolo operativo de las etiquetas es `learning_protocol_frozen.md`. El borrador queda como antecedente. El entrenamiento no forma parte de este diseño.

## Pregunta

¿Aprender diferencias de retorno entre candidatas mejora el packing frente a aprender únicamente la identidad de la mejor candidata, manteniendo datos, observabilidad, arquitectura y motor constantes?

## Lo que ya queda medido

El diagnóstico se recalculó desde los resultados guardados, sin empaquetar. Coincide con `verification.json`: 20 pedidos, 100 estados completos, 395 continuaciones, 4 reutilizadas y 391 nuevas, cero duplicados, cero desconocidos y cero fallos. Hay 96 ventajas positivas, 234 ceros y 65 negativas, y 47 estados con alguna mejora. Las medias por pedido son `f_i` = 0.47 y `m_i` = 0.02460370349702381. Euro-pallet queda en 0.30 y 0.009787708333333344; rollcontainer, en 0.64 y 0.03941969866071428. La pared acumulada, con el preflight, es 1223.2690794659975 segundos. El protocolo congelado es `e8fafb399a59863fc7a03f011b91f93e22af78f3a0d7aa78520c4a9e035717c1`. Las cuatro reutilizaciones apuntan a `preflight_results/preflight.json`, SHA256 `b0fb7cd9958202c8cec7e90170bbc9c6b177ed49b5ec03ed75abefd8c47e3dfd`, pedidos `00109938` y `00105640`. `authorizes_training` sigue en false. No hay discrepancia que corregir.

Esas cifras no se trasladan como puerta de este experimento. Miden margen entre candidatas examinadas, no si un modelo lo aprende ni si un episodio mejora.

## Límites que este diseño no elimina

Los estados salen de trayectorias Greedy. Solo se etiquetan hasta cuatro estados con elección por pedido. Solo se examinan hasta cuatro candidatas. El retorno usa el futuro real. El máximo por estado no es el rendimiento de una política. La señal observada no prueba predictibilidad desde las características. El diagnóstico no evalúa estabilidad física. Euro-pallet conserva su resultado más débil y entra en los dos splits.

Aunque el muestreo recorra el pedido, seguirá habiendo diferencia entre los estados de Greedy y los que visite el actor.

## Brazos

Los dos brazos comparten estados, candidatas evaluadas, retornos, arquitectura, entradas, normalización, motor y semillas.

A. Clasificación. Una MLP compartida puntúa cada candidata. El objetivo imita, con una distribución suave, la candidata de mayor `Q_hat` entre las examinadas.

B. Preferencias. La misma MLP. El objetivo ordena pares según la diferencia de `Q_hat`, pondera por el tamaño de esa diferencia y trata los empates sin declarar un ganador.

GreedyBestFit es el baseline no aprendido. El actor histórico, con `FEATURE_DIM=35`, puede citarse como antecedente. Su contrato no está verificado como equivalente y no entra como comparación homologada. No se añaden PPO, Transformer, xLSTM, otro generador ni una búsqueda de arquitecturas.

## Entradas

`FEATURE_DIM` histórico es 35, en `src/packing_services/online/features.py`, versión 1. Ese encoder no cumple el contrato de este experimento y no se modifica.

Columnas compatibles, las 17 del contrato nuevo `counterfactual-actor-v1`: dimensiones, volumen, peso y rotación del ítem actual; posición y orientación de la candidata; `support_ratio`; índice del contenedor; ítems ya colocados; peso cargado y altura usada. El peso y `support_ratio` son atributos presentes. El contrato geométrico no usa el peso para decidir legalidad, y `support_ratio` no convierte `physical_stability_verified` en verdadero.

Columnas excluidas: `rank_0` a `rank_3`, porque son la clave con la que Greedy ordena; `remaining_n`, porque es la longitud del sufijo; `buffer_index_n`, porque identifica una posición del buffer; y las doce columnas `preview_*`, porque describen ítems posteriores. Con `p=1` esas previsualizaciones salen vacías, pero el canal sigue siendo de ítems futuros y no entra en el contrato. `compact_selector_view` ya omite la cola, aunque conserva `rank_key`, así que tampoco es este contrato.

La normalización se ajusta solo con las filas de train. No se reutilizan las estadísticas de la campaña de normalización abandonada. El encoder nuevo no está implementado.

## Datos

La selección es estática. No se empaquetó ni se construyeron etiquetas. El dataset y el pool son los del diagnóstico, con los mismos SHA256. La exclusión histórica conserva el hash `fa27ae825c1e2b5a637c6e4ed0b8e5febbc88edbd9fbcc78826f87001b741a9b`. Además se bloquean los 20 pedidos del diagnóstico. Tras eso quedan 627 euro-pallet y 753 rollcontainer. El prefijo de selección es `counterfactual-learn-v1|20261003|`. No aparecieron clones. El test final no se selecciona ni se abre para elegirlo.

Los 20 pedidos diagnósticos no se usan como test ni se parten al azar. Tampoco aportan sus 395 etiquetas: aquella regla tomaba los cinco primeros estados y esta usa cuantiles.

Train: 24 pedidos, 12 por target. Desarrollo: 12 pedidos, 6 por target. Las listas, los hashes y las firmas están en el borrador JSON. El tamaño es el del propio diagnóstico, no un orden de magnitud mayor: 96 estados de train como techo, frente a los 100 ya medidos. Doce pedidos de desarrollo alcanzan para separar targets y siguen siendo una muestra pequeña de desarrollo.

## Regla de estados, fijada antes de etiquetar

Se recorre la trayectoria Greedy. Un estado con elección tiene al menos dos candidatas legales. Si hay `N`:

- `N = 0`: el pedido se conserva y no se sustituye.
- `N <= 4`: se toman todos.
- `N > 4`: los índices son la parte entera de `i*(N-1)/3 + 1/2` para `i = 0, 1, 2, 3`. Si el redondeo repite un índice, se queda la primera aparición y no se rellena el hueco.

Las alternativas son las de `select_alternatives` con límite 4, Greedy incluida, sin mirar retornos. El techo es 36 pedidos, 144 estados y 576 continuaciones.

## Pérdidas y empates

Un empate es una diferencia de `Q_hat` de valor absoluto menor o igual que `1e-9`. Un retorno desconocido queda `null`. Un estado incompleto no genera etiqueta.

En clasificación, el objetivo es uniforme sobre las examinadas que están a menos de `1e-9` del máximo. La pérdida es la entropía cruzada contra el softmax de esas puntuaciones. El empate no se rompe con la identidad de Greedy.

En preferencias, cada par no empatado se orienta hacia el `Q_hat` mayor. Su peso, dentro del estado, es la diferencia absoluta dividida por la suma de esas diferencias. La pérdida logística se promedia con esos pesos. En cada empate se suma `(s_i - s_j)^2`. El coeficiente de esa penalización queda propuesto en 1 y pendiente de congelar.

Cada estado se pondera por `1/n_i`, donde `n_i` es el número de estados etiquetados de su pedido.

## Checkpoints y semillas

Semillas emparejadas 11, 23 y 37. Se informan las tres. No se elige la mejor. El checkpoint de cada corrida es el de la última de las 40 épocas propuestas. No se selecciona con el regret de desarrollo ni con `U_geom`. Esas épocas, la tasa `0.001` de Adam y el coeficiente de empate siguen pendientes de congelar. El entrenamiento no está implementado.

## Evaluación

1. Ranking en los estados etiquetados de desarrollo: regret respecto al mejor `Q_hat` examinado, con la media del regret si varias puntuaciones empatan. La accuracy no es el único resultado.
2. Episodios completos: los mismos 12 pedidos, el mismo motor y el mismo contrato. El actor elige entre todas las candidatas legales, no solo entre las cuatro etiquetadas.
3. Media pareada de `U_geom` frente a Greedy, por semilla y por target.
4. Media pareada entre brazos.
5. Fallos y geometría auditada.
6. Tiempo de decisión separado del arranque y de la auditoría.

Una mejora de ranking no se presenta como mejora de episodios.

## Puerta propuesta

Es una puerta práctica de desarrollo. No es la puerta del diagnóstico, no es una significación y no autoriza publicación. No está aplicada: todavía no hay actores entrenados.

El delta es el `U_geom` de un episodio completo, el mismo pedido y la misma semilla. Cada pedido pesa igual y, después, cada semilla pesa igual. Se avanza con esta configuración solo si se cumplen las cinco condiciones del protocolo congelado: media de preferencias menos clasificación de al menos 0.005, esa diferencia positiva en al menos dos de tres semillas, media de preferencias menos Greedy de al menos 0.01, esa diferencia no negativa en ninguno de los dos targets, e integridad y cobertura del evaluador. Incumplirla significa no avanzar con esta configuración. No es una refutación universal del aprendizaje de preferencias.

El ranking se informa y no sustituye a esas condiciones.

## Presupuesto estimado

La media medida de continuación más auditoría en las 391 continuaciones nuevas fue 3.091 segundos. Aplicada a 576 continuaciones da unos 1781 segundos. Es una estimación puntual con la media de estados tempranos. No es una cola. Los estados tardíos deberían ser más baratos porque el sufijo es más corto, y esa rebaja no está medida. Recorrer la trayectoria completa para localizar los cuantiles tampoco está medido: no se extrapola el coste diminuto de los cien estados tempranos del diagnóstico.

El peor caso de 576 continuaciones a 60 segundos son 34560 segundos y no cabe en la pared de etiquetas de 14400. El presupuesto, si se acepta al congelar, sería truncado. La pared de entrenamiento propuesta es 600 segundos por cada una de las seis corridas. La de evaluación es 7200 segundos para como máximo 84 episodios, con 60 segundos de decisión y 60 de auditoría por episodio. El tiempo de entrenamiento y el de un episodio del actor no están medidos. Al agotarse una pared se para y se registra lo pendiente.

## Qué impediría avanzar

Con la integridad en orden, no se avanza con esta configuración si la media pareada de preferencias menos clasificación queda por debajo de 0.005, si esa diferencia es positiva en menos de dos semillas, o si la comparación con Greedy no cumple su umbral o empeora un target. Tampoco se avanza si solo mejora el ranking y los episodios no se mueven. Ese resultado no refuta el aprendizaje de preferencias fuera de este piloto.

## Qué se podría afirmar si funciona

En estos 12 pedidos de desarrollo, con esta arquitectura, estas entradas y etiquetas de estados Greedy, el brazo de preferencias superó al de clasificación en `U_geom` pareado. Si la cláusula frente a Greedy también se cumple, también lo superó. Eso no sería un test final, no evaluaría estabilidad física, no homologaría al actor histórico y no afirmaría novedad suficiente ni publicabilidad.

## Pendiente

Entrenar los dos brazos con la configuración ya congelada. Evaluar episodios y aplicar la puerta. Elegir el test final en otro paso. El encoder, las pérdidas y la regla de cuantiles ya están implementados; las etiquetas, si esta corrida termina, quedan en `learning_labels/`.
