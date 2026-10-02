# 05 — primera corrida del piloto interno

Commit de ejecución: `4ed37334c4ca7bd45aa0138bc09c80c3d5989ee2` en `research/paper-online-packing`. Una sola corrida. No hubo entrenamiento, ni una segunda inferencia, ni commit, ni push.

Comando:

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_internal_pilot.py --protocol /home/edmundo/packing-services/paper/protocols/03_internal_pilot.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt --output-dir /home/edmundo/packing-services/paper/results/04_internal_pilot
```

`run_id`: `3d4c452016015dcf`. Estado: `complete`. Terminó el 2026-10-02T17:24:10Z con código 0. El protocolo `03_internal_pilot.json` no se modificó y conserva `pilot_executed=false`.

## Integridad

La lectura posterior no llamó a las políticas. Hay 40 filas únicas, en el orden del manifiesto y con el actor antes que la heurística, y 20 pares únicos. Los ids y targets coinciden con el protocolo: 7 euro-pallet y 13 rollcontainer. El mismo `run_id` está en el manifiesto, las filas, los pares y el resumen. Los 40 casos tienen `worker_status=ok`, captura y auditoría. `physical_stability_verified` permanece null.

El recálculo de cada `delta` desde `effective_u_geom`, la media, la mediana, las victorias, los empates, las derrotas y el desglose por target coinciden con `summary.json`. No hay discrepancia. El denominador es 20.

## Resultados

En este conjunto de desarrollo, bajo el protocolo geométrico especificado, el actor obtuvo una diferencia de 0.013028540736607131 frente a GreedyBestFit.

La media de los 20 `delta` es 0.013028540736607131. La mediana es 0.0029772321428571114. Hay 11 victorias, 3 empates y 6 derrotas, con empate si `abs(delta) <= 1e-9`.

| Target | n | Media | Mediana | Victorias | Empates | Derrotas | Fallos actor | Fallos heurística |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| euro-pallet | 7 | 0.01735284598214285 | 0 | 3 | 3 | 1 | 0 | 0 |
| rollcontainer | 13 | 0.010700068681318666 | 0.004069642857142841 | 8 | 0 | 5 | 0 | 0 |

## Fallos y limitaciones

No hubo fallos de método, timeout, geometría inválida, violación de peso ni discrepancia con el snapshot. Quince filas del actor y dieciséis de la heurística tienen ítems sin candidata; eso forma parte del resultado y no entra como fallo.

El agregado describe esta mezcla de 7 y 13 pedidos. El tiempo quedó registrado solo como diagnóstico. La estabilidad física sigue sin verificar. Esta corrida no es una evaluación confirmatoria. Los cuatro ids excluidos por precaución siguen fuera y los 675 candidatos con exposición incierta no se declaran limpios.
