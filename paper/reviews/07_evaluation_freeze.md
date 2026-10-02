# 07 — congelar la evaluación independiente

HEAD de trabajo: `1e7f7b7391a8418dd1977d7d4fa0eacd94cab1e8` en `research/paper-online-packing`. No hubo packing, entrenamiento, inferencia, commit ni push. No se deserializó el checkpoint ni ningún pickle.

## Muestra

Los pools `absent_from_inspected_sources` siguen en 675 euro-pallet y 815 rollcontainer. Las exclusiones positivas siguen siendo las nueve ya registradas y no entran en la muestra. Todos esos ids pertenecen a `full.test`.

La selección usa el SHA256 de `packing-study-eval-v1|20261002|TARGET|ID`, ordena por hash y después por id, y toma 91 y 109. El orden de ejecución es el id ascendente de los 200. El hash de esa lista es `dcb312188127239b70a0b4422fef8b03fc489817b9e504f180278d812a2d2227`.

Estos pedidos no aparecen en las fuentes inspeccionadas. No se llaman absolutamente limpios. La identidad histórica del archivo BC sigue no comprobada.

## Primaria

Media de los 200 `delta_i`, igual peso por pedido, con desglose por target obligatorio y secundario. El intervalo bootstrap percentil del 95 % se calcula con 20000 medias, `default_rng(20261002)`, remuestreo pareado dentro de cada target, cuotas 91 y 109 en cada réplica, y percentiles 2.5 y 97.5 con `method="linear"`.

Por encima de 0: evidencia de ventaja media bajo este protocolo. Por debajo de 0: evidencia de desventaja media. Si incluye 0, el signo de la media no es concluyente. Eso no demuestra igualdad. El intervalo es aproximado, supone pedidos suficientemente independientes y no cubre todas las instancias posibles. Pedidos del mismo dataset pueden compartir estructura.

## Preflight

El preflight del protocolo nuevo terminó con `ok`, 200 pedidos, 91 y 109, configs equivalentes, `checkpoint_loaded=false` y `workers_started=false`. El directorio `paper/results/07_independent_evaluation/` no se creó. El protocolo del piloto y sus resultados no se modificaron.

Comando futuro:

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_internal_pilot.py --protocol /home/edmundo/packing-services/paper/protocols/07_independent_evaluation.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt --output-dir /home/edmundo/packing-services/paper/results/07_independent_evaluation
```
