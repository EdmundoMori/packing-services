# 07 — evaluación independiente congelada

Protocolo congelado. No está ejecutado. No compara con PCT y no certifica estabilidad física. Los pedidos no se declaran absolutamente limpios.

La muestra sale de los candidatos `absent_from_inspected_sources` del paso 06A: 675 euro-pallet y 815 rollcontainer. Esos ids no aparecen en las fuentes inspeccionadas. La identidad histórica del archivo BC sigue no comprobada.

## Muestra

Selección determinista, sin usar tamaño, dificultad ni métricas de packing. Para cada id se calcula el SHA256 de la cadena UTF-8

`packing-study-eval-v1|20261002|TARGET|ID`

Dentro de cada target se ordena por ese hash y después por id. Se toman los primeros 91 euro-pallet y los primeros 109 rollcontainer. El orden de ejecución de los 200 es el id ascendente.

El hash de esa lista, SHA256 UTF-8 de los ids unidos por salto de línea y con salto final, es `dcb312188127239b70a0b4422fef8b03fc489817b9e504f180278d812a2d2227`.

Siguen fuera las exclusiones positivas: `00101249`, `00102764`, `00108147`, `00109619`, `00100348`, `00104068`, `00108193`, `00108237` y `00109274`.

Los 200 ids, sus hashes de selección y los pools están en [`07_independent_evaluation.json`](07_independent_evaluation.json) y en [`../results/07_sample_freeze.json`](../results/07_sample_freeze.json).

## Condiciones comunes

Las mismas del piloto, con el target propio de cada pedido:

- p=1 y s=1, orden de llegada.
- Hasta seis permutaciones si la receta y el ítem permiten rotación.
- No solape, contención y peso máximo activos. Peso máximo 1500 kg.
- Estabilidad básica y load-bearing desactivados, igual que fragilidad y secuencia de descarga.
- Si no hay candidata legal, se descarta el ítem y se continúa.
- CPU, 300 s, una tentativa por método y pedido.
- Captura completa y contraste independiente.
- Un fallo deja `U_geom=0` y permanece en el denominador.

El actor es el checkpoint vigente, con los pesos BC conservados tras la selección PPO. El comparador es GreedyBestFit sobre el mismo generador y las mismas restricciones. Los dos métodos reciben el mismo problema convertido.

## Primaria

Media aritmética de los 200 `delta_i`, con el mismo peso por pedido. `delta_i` es `U_geom` del actor menos `U_geom` de la heurística, cada una sobre el volumen del contenedor de ese pedido.

El desglose por target es obligatorio y secundario. No se elige después el target favorable como resultado primario.

Intervalo bootstrap percentil del 95 % para esa media:

- 20000 réplicas.
- `numpy.random.default_rng(20261002)`.
- En cada réplica se remuestrean pedidos pareados dentro de cada target y se mantienen 91 y 109.
- No se remuestrean el actor y la heurística por separado.
- Percentiles 2.5 y 97.5 con `method="linear"`.

El intervalo es aproximado y supone pedidos suficientemente independientes. Pedidos del mismo dataset pueden compartir procedencia, tipos de ítem o estructura de pedido, así que la dependencia no queda descartada. No es una garantía ni un intervalo sobre todas las instancias posibles.

Si el intervalo queda por encima de 0, hay evidencia de ventaja media bajo este protocolo. Si queda por debajo de 0, hay evidencia de desventaja media. Si incluye 0, el resultado no es concluyente respecto al signo de la media. Un resultado no concluyente no demuestra igualdad. Se informan siempre la magnitud y el intervalo.

No se añaden pedidos después de ver el resultado para obtener un signo. Una ampliación futura exige otro protocolo y se declara como tal.

## Salida futura

400 filas y 200 pares en `paper/results/07_independent_evaluation/`. Ese directorio no forma parte de este congelado.

Comando futuro, sin ejecutarlo en este paso:

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_internal_pilot.py --protocol /home/edmundo/packing-services/paper/protocols/07_independent_evaluation.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt --output-dir /home/edmundo/packing-services/paper/results/07_independent_evaluation
```
