# Resumen del piloto interno

Estado: complete.

En este conjunto de desarrollo, bajo el protocolo geométrico especificado, el actor obtuvo una diferencia de -0.000593820157738 frente a GreedyBestFit.
El agregado depende de la composición de estos pedidos. No equivale a una ventaja demostrada para cada target ni para toda la colección.
El tiempo es diagnóstico y no permite afirmar mayor eficiencia.
La estabilidad física permanece sin verificar.

n=200, media=-0.000593820157738, mediana=0, victorias=78, empates=53, derrotas=69.

Desglose por target:
- rollcontainer: n=109, media=0.00073940443152, mediana=0.00344107142857, victorias=57, empates=9, derrotas=43, fallos actor=0, fallos heurística=0.
- euro-pallet: n=91, media=-0.00219075950092, mediana=0, victorias=21, empates=44, derrotas=26, fallos actor=0, fallos heurística=0.

Secundarias, con el tiempo solo como diagnóstico:
- actor: fracción de ítems=0.920265951193, fracción del volumen solicitado=0.900215853963, altura máxima media=1987.97, tipos de fallo={}, filas con ítems sin candidata=147.
- heuristic: fracción de ítems=0.919373365226, fracción del volumen solicitado=0.901429405614, altura máxima media=1983.42, tipos de fallo={}, filas con ítems sin candidata=143.

Fallos de método, geometría o peso: actor=0, heurística=0. Siguen dentro del denominador.
Los ítems no colocados por falta de candidata forman parte del resultado y no son un fallo de método.
