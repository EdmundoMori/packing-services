# Resumen del piloto interno

Estado: complete.

En este conjunto de desarrollo, bajo el protocolo geométrico especificado, el actor obtuvo una diferencia de 0.0130285407366 frente a GreedyBestFit.
El agregado depende de la composición de estos pedidos. No equivale a una ventaja demostrada para cada target ni para toda la colección.
El tiempo es diagnóstico y no permite afirmar mayor eficiencia.
La estabilidad física permanece sin verificar.

n=20, media=0.0130285407366, mediana=0.00297723214286, victorias=11, empates=3, derrotas=6.

Desglose por target:
- rollcontainer: n=13, media=0.0107000686813, mediana=0.00406964285714, victorias=8, empates=0, derrotas=5, fallos actor=0, fallos heurística=0.
- euro-pallet: n=7, media=0.0173528459821, mediana=0, victorias=3, empates=3, derrotas=1, fallos actor=0, fallos heurística=0.

Secundarias, con el tiempo solo como diagnóstico:
- actor: fracción de ítems=0.909689006035, fracción del volumen solicitado=0.893249514428, altura máxima media=1988.5, tipos de fallo={}, filas con ítems sin candidata=15.
- heuristic: fracción de ítems=0.892474803048, fracción del volumen solicitado=0.876568889661, altura máxima media=1987.5, tipos de fallo={}, filas con ítems sin candidata=16.

Fallos de método, geometría o peso: actor=0, heurística=0. Siguen dentro del denominador.
Los ítems no colocados por falta de candidata forman parte del resultado y no son un fallo de método.
