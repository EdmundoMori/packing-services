# Selección de reglas con PPO

Borrador. No hay entrenamiento, ni packing de pedidos reales, ni test final.

Pregunta: una política PPO pequeña, que elige entre tres reglas geométricas en estados propios, ¿mejora frente a cada regla fija bajo el mismo contrato y el mismo presupuesto?

Esa pregunta está abierta. Este borrador no afirma novedad suficiente ni una posibilidad garantizada de publicación.

## Diferenciación

Queda fijada la diferencia de diseño: la acción elige una de tres reglas que ya vieron la misma lista de candidatas de puntos extremos. La recompensa es solo el volumen colocado dividido por el volumen del contenedor. La observación usa el estado presente, el ítem actual y las tres propuestas.

Queda pendiente medir si esa política mejora, bajo el presupuesto de abajo, a cada regla fija, a la selección aleatoria y a OnlineBPH.

## Reglas

Sobre la misma lista legal, en este orden:

1. `greedy_best_fit`: menor `rank_key` de GreedyBestFit.
2. `lowest_top`: menor `z + altura orientada`.
3. `least_height_increase`: menor incremento de la altura máxima ya colocada, `max(altura_actual, z + altura_orientada) - altura_actual`.

El desempate común es el menor índice original de esa lista. Si dos reglas proponen la misma geometría, las tres acciones siguen existiendo. La redundancia se registra; no se borra ninguna acción.

La altura usa la dimensión orientada de la candidata, no la altura almacenada del ítem.

## Contrato

Secuencia original, un contenedor del target del pedido, `p = 1`, `s = 1`. Rotaciones, contención y no solape del contrato compacto. Peso, estabilidad y load-bearing inactivos. El episodio se detiene en el primer ítem actual sin candidata legal; el sufijo no se coloca. `physical_stability_verified` permanece `null`.

## Observación, modelo y recompensa

36 escalares: ítem actual normalizado por las dimensiones del contenedor, altura usada, número de ítems ya colocados dividido por 1000 sin saturación, peso cargado con escala fija 1000 kg, y nueve atributos de cada propuesta. No hay sufijo, identificadores ni cantidad de ítems restantes. No hay estadística aprendida en esta observación. `support_ratio` describe la candidata y no entra en la recompensa ni en la máscara de estabilidad.

MLP `36 → 64 → ReLU`. El actor termina en tres logits. El crítico es otra MLP `36 → 64 → 1`, con parámetros distintos. PPO, `gamma = 1`. La recompensa de una colocación es el volumen orientado dividido por el volumen del contenedor. Una parada sin candidata aporta recompensa 0. La suma de recompensas es `U_geom`.

Inicialización, fijada antes de entrenar: la última capa del actor tiene pesos cero y sesgo `[1, 0, 0]`. En ese estado, cualquier observación produce logits `[1, 0, 0]`. La política determinista elige Greedy. Con muestreo softmax, la probabilidad de Greedy es `exp(1) / (exp(1) + 2)`, aproximadamente `0.5761168847658291`. Esa inicialización no garantiza que, después de un paso de PPO, el retorno iguale o supere a Greedy. No se cargan pesos históricos.

## Presupuesto

Tres semillas: 101, 102 y 103. Por semilla, como máximo 60000 decisiones o 1000 episodios. Entrenamiento acumulado: cuatro horas. Campaña completa: ocho horas. CPU, dos workers como máximo al inicio, un hilo de Torch por worker.

Estos topes no se modifican con resultados posteriores. Este paso no ejecuta el entrenamiento.

## Datos propuestos

Train 64, desarrollo 20 y evaluación final 100 por target. El manifiesto de train ya está emitido. Desarrollo y test no se seleccionan ni se consultan.

## Benchmark y selección

Referencias: las tres reglas fijas, selección uniforme entre las tres acciones y la política PPO. OnlineBPH entra como baseline externo, con el contrato de captura ya comprobado. No entra un PCT aprendido, ni el leaderboard BED-BPP, ni la Tabla 1 de Zhao.

En desarrollo, antes de ver resultados, la regla común es:

- por semilla, solo es elegible el checkpoint del final de su presupuesto;
- la regla fija de referencia es la de mayor media de `U_geom` en los 40 pedidos; si empatan, gana el menor índice.

No se elige la mejor semilla. La evaluación final informa las tres. Las medias se emparejan por pedido y se desglosan por target. El bootstrap re-muestrea pedidos y conserva juntas las tres semillas de cada pedido. Un intervalo que contiene cero no se declara igualdad.

## Decisiones operativas que siguen abiertas

El borrador propone, y todavía no congela: clip 0.2, Adam con learning rate `3e-4`, coeficiente de entropía 0.01, coeficiente de valor 0.5, cuatro épocas por actualización, lambda de GAE 1, normalización de ventajas dentro del lote y recorte de gradiente 0.5. La evaluación sería argmax; el entrenamiento, muestreo.

El reloj de cuatro horas cubre los rollouts y las actualizaciones de las tres semillas. El de ocho horas cubre además las reglas fijas, la selección aleatoria, OnlineBPH y la evaluación final. Si una parte no cabe, se registra el corte y el tope no se amplía.

Esas cifras se copian al protocolo congelado antes del primer update. No se ajustan con los retornos de desarrollo.
