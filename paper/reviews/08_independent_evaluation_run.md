# 08 — primera evaluación independiente congelada

Commit de ejecución: `41c6e6b996831d12908969084010350541c8e358` en `research/paper-online-packing`. Una sola corrida. No hubo entrenamiento, ni una segunda inferencia, ni commit, ni push.

Comando:

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_internal_pilot.py --protocol /home/edmundo/packing-services/paper/protocols/07_independent_evaluation.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt --output-dir /home/edmundo/packing-services/paper/results/07_independent_evaluation
```

`run_id`: `09d052b75a534728`. Estado: `complete`. Terminó el 2026-10-02T19:02:18Z con código 0. El protocolo `07_independent_evaluation.json` no se modificó y conserva sus campos históricos, incluido `executed=false`.

## Integridad

La lectura posterior no llamó a las políticas. Hay 400 filas únicas por `(order_id, method)`, en el orden del protocolo y con el actor antes que la heurística, y 200 pares únicos. Los ids, el orden y los targets coinciden con la lista congelada: 91 euro-pallet y 109 rollcontainer. El hash de esa lista sigue siendo `dcb312188127239b70a0b4422fef8b03fc489817b9e504f180278d812a2d2227`.

El mismo `run_id` está en el manifiesto, el resumen, `paired_results.json`, `results.json`, las 400 filas y los dos lados de cada par. Los 400 casos tienen `worker_status=ok`, captura y auditoría. `physical_stability_verified` permanece null en filas, pares, resumen y capturas.

El recálculo de cada `delta` desde `effective_u_geom` coincide con el delta guardado. La diferencia máxima es 0. La media, la mediana, las victorias, los empates, las derrotas y el desglose por target coinciden con `summary.json`. No hay discrepancia numérica. Los 200 pares permanecen en el denominador.

El preflight guardado en el manifiesto anotó el árbol como dirty, con 18 líneas de `status --short`. Esa foto se tomó después de crear la carpeta de salida, junto a los 17 `.pkl` sin seguimiento. La precomprobación anterior a la corrida no tenía modificaciones rastreadas.

`summary.md` lo escribió el evaluador con su frase fija. La clasificación de este paso es la de `independent_analysis.json`, obtenida con `bootstrap_primary()` sobre los deltas recalculados, en el orden de `position` del protocolo dentro de cada target. Fueron 20000 réplicas, semilla `20261002`, remuestreo pareado y estratificado, y percentiles 2.5 y 97.5 con `method="linear"`.

## Resultados

La media de los 200 `delta` es -0.0005938201577380936. El intervalo bootstrap percentil del 95 % es [-0.006293330782645088, 0.005043209075334814].

En puntos porcentuales de `U_geom`, la media es -0.05938201577380937 y el intervalo es [-0.6293330782645088, 0.5043209075334814]. Esa escala multiplica el delta por 100.

La mediana es 0. Hay 78 victorias, 53 empates y 69 derrotas, con empate si `abs(delta) <= 1e-9`.

La clasificación predefinida es `no_concluyente`. El intervalo incluye el cero, así que el resultado es no concluyente respecto al signo de la media. La igualdad queda sin demostrar.

El desglose por target es secundario y descriptivo:

| Target | n | Media | Mediana | Victorias | Empates | Derrotas | Fallos actor | Fallos heurística |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| euro-pallet | 91 | -0.0021907595009157486 | 0 | 21 | 44 | 26 | 0 | 0 |
| rollcontainer | 109 | 0.0007394044315203155 | 0.0034410714285715294 | 57 | 9 | 43 | 0 | 0 |

## Fallos

| Método | Fallo de método | Geometría inválida | Peso | Discrepancia de entrada | Timeout u otro fallo de worker | `worker_status=ok` |
| --- | --- | --- | --- | --- | --- | --- |
| actor | 0 | 0 | 0 | 0 | 0 | 200 |
| heuristic | 0 | 0 | 0 | 0 | 0 | 200 |

Ciento cuarenta y siete filas del actor y ciento cuarenta y tres de la heurística tienen ítems sin candidata. Eso forma parte del resultado y permanece fuera de los fallos de método.

## Limitaciones

La identidad histórica del archivo de transiciones BC sigue `no_comprobada`. `called_clean` sigue en false. La ausencia en las fuentes inspeccionadas, con las nueve exclusiones positivas fuera de la muestra, deja la independencia absoluta sin establecer.

El intervalo es aproximado. Supone pedidos suficientemente independientes y no cubre todas las instancias posibles. Los 200 pedidos comparten el mismo actor y la misma fuente de benchmark, así que la dependencia entre pedidos permanece.

Esta corrida compara el checkpoint existente con GreedyBestFit bajo el protocolo geométrico 07. Quedan sin establecer la superioridad frente a PCT, la superioridad frente al estado del arte, una mejora obtenida mediante PPO, la estabilidad física y una mayor eficiencia.
