# Revisión metodológica

Borrador. El preflight no es una preregistración confirmatoria. No afirma novedad suficiente, estabilidad física ni superioridad frente a PCT. OnlineBPH sigue siendo una heurística externa. El contrato geométrico sobre BED-BPP no es su leaderboard oficial.

Clasificación de este paso: **presupuesto no demostrado**. La implementación de los cuatro pedidos no está bloqueada. El reloj no ha demostrado que quepan 60000 decisiones por semilla ni la campaña de ocho horas.

## Pregunta

¿Seleccionar reglas según el estado mediante PPO mejora el rendimiento de episodios completos respecto a cada regla fija y una selección aleatoria, bajo el mismo motor, la misma observabilidad y el mismo presupuesto?

Sigue abierta. Los `U_geom` del preflight se guardan y no se usan para cambiar reglas, hiperparámetros ni la muestra.

## Reglas

Las tres reglas leen la misma lista legal. El desempate, después de la clave primaria, es el menor índice original.

Con altura máxima cero, el incremento de altura es igual a `z + altura orientada`. Las reglas 2 y 3 eligen entonces la misma candidata. La prueba sintética del primer ítem `100 × 100 × 1500` lo comprueba.

Dejan de ser equivalentes cuando varias candidatas no aumentan la altura máxima y tienen cimas distintas. La regla 2 minimiza la cima. La regla 3, al ver incremento cero en todas ellas, cae en el índice y puede conservar una cima más alta. Tras colocar esa torre, el ítem `200 × 150 × 100` produce 18 candidatas con altura máxima 1500 mm. La regla 2 elige el índice 4, con altura orientada 100 mm. La regla 3 elige el índice 0, con altura orientada 150 mm. Las tres acciones se conservan.

En los cuatro pedidos reales la redundancia por pares va de 0.70 a 1.00. La coincidencia de las tres geometrías va de 0.021 a 0.417. En el rollcontainer de 67 ítems, la regla de menor incremento termina en 56 colocaciones y las otras dos reglas fijas en 58. No son la misma política. No se añade otra regla.

## Observabilidad

La codificación usa el ítem actual, `len(session.packed) / 1000` sin saturación, el peso cargado y las tres propuestas. Las posiciones y las dimensiones se dividen por el eje correspondiente del contenedor. Una prueba cambia el identificador del ítem y el sufijo sin cambiar el vector. El tope anterior en 50 igualaba conteos distintos; se quitó antes del preflight. No hay media ni desviación ajustada. Si más adelante se añade alguna, se ajustará solo en los 128 pedidos de train.

La recompensa es el volumen orientado colocado dividido por el volumen del contenedor. `gamma = 1`. La suma coincide con `U_geom` recalculado en los 16 episodios. `physical_stability_verified` queda `null`.

## Exposición y train

La unión de identificadores únicos es 8659. La suma de conteos por fuente es 24646; el exceso de 15987 es solapamiento y no se vuelve a excluir. La intersección con el pool de 1500 es 156 pedidos: 71 euro-pallet y 85 rollcontainer. Quedan en el pool 609 y 735. De esos se eligen 64 y 64 por hash `rl-rules-train-v1|20261004|`. Desarrollo y test no se emiten. Su separación futura, si se congela, sigue por pedido en ese mismo orden.

Las firmas son las del snapshot compacto. Se firmaron 8658 identificadores excluidos presentes en el dataset, con cero ausencias y cero errores. Los 128 de train tienen firmas distintas y ninguno chocó con un excluido. Los 17 pickle no se abrieron. Los nombres de carpeta del packing anterior aportan 12 pedidos que ya estaban en el protocolo; no se abrió su `U_geom`. La independencia absoluta no se declara.

Los cuatro pedidos del preflight siguen dentro de train. Son los extremos de longitud, con desempate por identificador:

| Target | Papel | Pedido | Ítems |
| --- | --- | --- | --- |
| euro-pallet | más corto | 00101471 | 23 |
| euro-pallet | más largo | 00106344 | 98 |
| rollcontainer | más corto | 00102307 | 16 |
| rollcontainer | más largo | 00102424 | 67 |

Sus resultados ya se conocen. No son un conjunto de desarrollo.

## PPO

Queda registrado en `ppo_proposal.json`, antes de usar los retornos: rollout de 512 decisiones, minibatch 128, cuatro épocas, Adam `3e-4` con betas `(0.9, 0.999)` y `eps = 1e-8`, clip 0.2, entropía 0.01, valor 0.5, recorte de gradiente 0.5, crítico separado y observación de 36 escalares. `gamma = 1` y `lambda = 1`. La terminación real no recibe bootstrap; el corte del rollout sí. Si la varianza de las ventajas es cero, las ventajas normalizadas son cero. Las pruebas sintéticas cubren log-probabilidades antiguas separadas del grafo, el ratio, el clipping, la alineación y el reset. Esas filas no miden convergencia ni la velocidad del entrenamiento BED-BPP.

Cada semilla tiene 4800 s de reloj de su worker. Las semillas 101 y 102 pueden ocupar los dos workers a la vez; la 103 usa el worker que queda después. El tiempo no usado no se reasigna. El reloj de pared del entrenamiento no pasa de cuatro horas. Un hilo Torch por worker. Si el reloj deja cantidades distintas de decisiones, episodios o updates, se registran. No se igualan después. El checkpoint es el final de cada semilla. No se elige la mejor. No se reajusta la configuración después de desarrollo.

## Benchmark futuro, sin ejecutarlo

En desarrollo se elegirá la regla fija de mayor media. En test se informarán las tres. La comparación primaria será la diferencia pareada de `U_geom` contra esa referencia, con igual peso por pedido y después por semilla. La selección aleatoria uniforme es otra comparación, con réplicas y semillas fijadas de antemano, no una sola trayectoria. OnlineBPH se identifica aparte, bajo el contrato de captura ya comprobado. El bootstrap re-muestrea pedidos y conserva juntas las semillas de cada pedido. Un intervalo que contiene cero no es equivalencia. La puerta de avance no se fija después de ver desarrollo, y el test no se abre para decidir si conviene continuar.

## Presupuesto

Medición: el preflight completo tardó 134.5 s de pared para 16 episodios, dentro de los 900 s. El episodio de bucle más lento costó 0.641 s por decisión. Otro episodio largo costó 0.073 s por decisión.

Extrapolación, no medición: 60000 decisiones a 0.641 s suman unas 10.7 h de un worker, por encima de los 4800 s de la semilla. A 0.073 s, 60000 decisiones caben en esa cuota. En 4800 s a la tasa lenta caben unas 7500 decisiones y del orden de 15 updates de 512 decisiones; a la tasa del otro episodio largo, del orden de 100 updates, y el tope de 60000 decisiones llegaría antes que el reloj. Cuatro pedidos, aunque incluyan los extremos de longitud de train, no caracterizan el resto de geometrías ni OnlineBPH ni una evaluación de 200 pedidos. Por eso el presupuesto de la campaña no queda demostrado.
