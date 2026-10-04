# Control de integridad del piloto PPO

El control no generó episodios nuevos. La integridad pasa. El código congelado y los artefactos coinciden con un entrenamiento de 6144 decisiones, 12 actualizaciones y 192 pasos de Adam por semilla.

## Protocolo y corte

SHA256 de `protocol_frozen.json`: `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`.

HEAD esperado `c7191d5fc87b4125795cd168b49c4709bb95a9b8` en `research/paper-online-packing`. Los hashes de los ocho archivos congelados coinciden con el protocolo y con `training/training_config.json`. Train tiene 128 pedidos y desarrollo 40, sin identificadores comunes. Las 36 entradas de la observación no incluyen futuro, sufijo ni ítems restantes.

El presupuesto ejecutado es el reducido: 6144 decisiones, doce rollouts de 512 y 192 pasos de Adam. El reloj de 4800 s por semilla no cortó el entrenamiento.

## Semillas

En cada semilla el historial tiene doce actualizaciones, con 16 pasos de Adam y decisiones 512, 1024, …, 6144. El checkpoint inicial tiene cero actualizaciones y sesgo [1, 0, 0]. El checkpoint final coincide con el último y declara 12 actualizaciones y 6144 decisiones. Los pedidos del historial están dentro de train.

La evidencia on-policy y de las ventajas está en el código cuyo hash no cambió: cada actualización usa solo su rollout de 512, la log_prob antigua se comprueba al terminar, y las ventajas se normalizan una vez antes de los minibatches de 128. Esas transiciones no se guardaron en el historial, así que el valor numérico de cada ventaja no se puede recalcular desde el disco. El código que las calculó es el congelado.

## Episodio cortado

Cada semilla termina con un episodio abierto etiquetado `corte_de_presupuesto`. No está marcado como `secuencia_agotada` ni como `sin_candidata`, y el registro no trae retorno. En el código, la última transición de un rollout que corta el episodio queda truncada, no terminada, y el retorno usa el valor del estado siguiente. Ese episodio parcial no entra como episodio completo en una estadística de retorno: las recompensas guardadas son sumas de rollout, no retornos de episodio.

## Cambio de política

Los vectores de observación de las 6144 decisiones no están guardados. La última captura tiene acciones de un episodio y no la observación que vio el actor. No se reconstruye la trayectoria, así que no hay proporción de decisiones distintas ni separación entre otra regla y otra geometría. No se impone un umbral de KL ni de entropía.

Los tensores sí están. Ninguna semilla conserva el actor inicial. La diferencia absoluta máxima es 0.0304, 0.0477 y 0.0296. El sesgo final sigue cerca de [1, 0, 0]: aproximadamente [0.993, -0.002, 0.008], [0.988, 0.011, 0.002] y [0.990, -0.002, 0.015]. Un cambio de ese tamaño no demuestra que el entrenamiento sea inútil.

## Decisión del control

La integridad pasa. Autoriza una evaluación de desarrollo y no autoriza otro entrenamiento.
