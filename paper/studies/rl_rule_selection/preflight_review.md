# Preflight real

Cuatro pedidos de train, dieciséis episodios, un intento por caso. No hubo entrenamiento, ni desarrollo, ni test. No es una preregistración confirmatoria.

Clasificación: **presupuesto no demostrado**.

## Casos

Los dieciséis terminaron con estado `ok`. Ninguno agotó los 300 s ni el reloj global de 900 s. La auditoría interna acepta contención y no solape en los dieciséis. `physical_stability_verified` queda `null`. La suma de recompensas coincide con `U_geom` recalculado. El optimizador dio cero pasos. Estos valores no modifican reglas ni hiperparámetros.

| Pedido | Target | Ítems | Método | Decisiones | Pared del caso (s) | Bucle (s) | Candidatas (s) | Decisión (s) | Captura (s) | Auditoría (s) | CPU usuario (s) | Pares iguales | U_geom |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 00101471 | euro-pallet | 23 | GreedyBestFit | 22 | 1.739 | 0.696 | 0.672 | 0.000 | 0.003 | 0.485 | 1.661 | 0.864 | 0.5904 |
| 00101471 | euro-pallet | 23 | Menor z+h | 23 | 1.597 | 0.502 | 0.480 | 0.000 | 0.003 | 0.544 | 1.555 | 0.957 | 0.6266 |
| 00101471 | euro-pallet | 23 | Menor incremento | 23 | 0.961 | 0.457 | 0.437 | 0.000 | 0.002 | 0.494 | 0.909 | 0.957 | 0.6266 |
| 00101471 | euro-pallet | 23 | Softmax inicial | 23 | 1.324 | 0.792 | 0.748 | 0.018 | 0.002 | 0.518 | 1.271 | 0.826 | 0.6266 |
| 00102307 | rollcontainer | 16 | GreedyBestFit | 10 | 0.185 | 0.076 | 0.071 | 0.000 | 0.001 | 0.104 | 0.163 | 0.800 | 0.5046 |
| 00102307 | rollcontainer | 16 | Menor z+h | 12 | 0.207 | 0.051 | 0.044 | 0.000 | 0.003 | 0.149 | 0.189 | 1.000 | 0.6185 |
| 00102307 | rollcontainer | 16 | Menor incremento | 12 | 0.189 | 0.049 | 0.043 | 0.000 | 0.001 | 0.134 | 0.167 | 1.000 | 0.6185 |
| 00102307 | rollcontainer | 16 | Softmax inicial | 12 | 0.226 | 0.073 | 0.060 | 0.005 | 0.001 | 0.145 | 0.195 | 1.000 | 0.6185 |
| 00102424 | rollcontainer | 67 | GreedyBestFit | 58 | 10.482 | 6.521 | 6.410 | 0.000 | 0.008 | 3.907 | 9.494 | 0.931 | 0.6985 |
| 00102424 | rollcontainer | 67 | Menor z+h | 58 | 7.705 | 4.230 | 4.136 | 0.000 | 0.008 | 3.421 | 7.464 | 0.810 | 0.6985 |
| 00102424 | rollcontainer | 67 | Menor incremento | 56 | 7.609 | 4.479 | 4.392 | 0.000 | 0.007 | 3.086 | 7.361 | 0.821 | 0.6751 |
| 00102424 | rollcontainer | 67 | Softmax inicial | 58 | 9.984 | 6.466 | 6.326 | 0.034 | 0.008 | 3.474 | 9.734 | 0.862 | 0.6985 |
| 00106344 | euro-pallet | 98 | GreedyBestFit | 98 | 74.083 | 62.830 | 62.529 | 0.000 | 0.022 | 11.123 | 71.382 | 0.980 | 0.7004 |
| 00106344 | euro-pallet | 98 | Menor z+h | 98 | 38.383 | 28.032 | 27.801 | 0.000 | 0.018 | 10.217 | 37.685 | 0.776 | 0.7004 |
| 00106344 | euro-pallet | 98 | Menor incremento | 96 | 44.355 | 33.570 | 33.313 | 0.000 | 0.026 | 10.653 | 41.084 | 0.698 | 0.6860 |
| 00106344 | euro-pallet | 98 | Softmax inicial | 96 | 53.404 | 44.063 | 43.727 | 0.062 | 0.021 | 9.236 | 51.300 | 0.979 | 0.6860 |

Cuando hay menos decisiones que ítems, el episodio se detuvo en el primer ítem sin candidata. Es la parada del contrato, no un fallo de método. La generación de candidatas ocupa casi todo el bucle. La elección de la regla es breve.

La política inicial no es uniforme. Sus primeros logits son `[1, 0, 0]`. En 189 decisiones muestreó Greedy 116 veces, fracción 0.614, frente a una probabilidad inicial de aproximadamente 0.576 y a un uniforme de un tercio. La semilla base es 101 y cada pedido tiene una corriente derivada de ese valor y de su identificador, para que los dos workers no reordenen los sorteos.

## Memoria y relojes

La pared de la campaña fue 134.5 s. La suma de las paredes de los dieciséis casos fue 252.4 s y la suma de CPU de usuario fue del mismo orden. La diferencia es la concurrencia de dos workers. La pared no es la CPU.

El máximo de RSS conjunta muestreada, padre más dos workers, fue 1138920 KB en 530 muestras. El `ru_maxrss` del padre fue 19200 KB. Al terminar, los workers registraron 565552 KB y 562700 KB. Ese pico del kernel es por proceso y no sustituye a la suma muestreada. El mayor `tracemalloc` de un caso fue de unos 9.8 MB. Mide asignaciones de Python y no toda la memoria de Torch.

Cada worker cargó el dataset en unos 1.77 s, con un hilo Torch. No se repitieron episodios.

## Lectura del presupuesto

La medición cabe en el preflight. La extrapolación no cabe, como techo de interacciones, en las cuatro horas si las decisiones costaran lo que costó el bucle más lento: 0.641 s por decisión llevarían 60000 decisiones a unas 10.7 h de un worker. A 0.073 s por decisión, la otra tasa larga observada, el tope de 60000 decisiones sí entraría en los 4800 s de la semilla. El número de updates de 512 decisiones quedaría, en esos dos extremos, en torno a 15 o a más de 100. Esa horquilla es una extrapolación. Cuatro pedidos no caracterizan la cola de geometrías, OnlineBPH ni el test de 200.
