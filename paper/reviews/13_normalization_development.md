# 13 — packing de desarrollo de la ablación

Packing terminado el 2026-10-03 sobre `6ae66fb6d38dcbb278e0d29f872e3c076d5b32cc`, rama `research/paper-online-packing`. El manifiesto de `paper/results/11_normalization_ablation/packing/` está `complete`. Hubo una sola etapa, con timeout de 300 segundos, CPU y una tentativa por caso. No hubo entrenamiento, reintento ni commit.

Comando:

```bash
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_normalization_ablation.py pack --protocol /home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json --freeze /home/edmundo/packing-services/paper/results/10_normalization_freeze.json --run-dir /home/edmundo/packing-services/paper/results/11_normalization_ablation --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json
```

Hay 550 claves únicas: 50 heurísticas y 250 resultados por brazo. Los diez modelos y la heurística comparten los mismos 50 pedidos, semillas 42–46 y 25 pedidos por target. Cada caso tiene captura y auditoría. `physical_stability_verified` permanece `null`. Los hashes de los modelos coinciden con `training_verification.json`. El manifiesto de entrenamiento, los emparejamientos, el protocolo y el congelado no se modificaron.

## Resultados por semilla

Cada cifra es la media de los 50 pedidos. Los fallos, si los hubiera, permanecerían en el denominador. Aquí no hubo fallos de método.

| Semilla | normalized−raw | raw−heurística | normalized−heurística |
| --- | --- | --- | --- |
| 42 | -0.002823156994047631 | -0.010310473214285713 | -0.013133630208333344 |
| 43 | 0.002817314732142848 | -0.011881663690476192 | -0.009064348958333343 |
| 44 | 0.008967771577380945 | -0.012416883928571433 | -0.003449112351190489 |
| 45 | 0.0036462961309523755 | -0.010260741071428573 | -0.006614444940476198 |
| 46 | -0.005618776785714292 | -0.010198688988095245 | -0.015817465773809537 |
| Media de las cinco | 0.001397889732142849 | -0.011013690178571432 | -0.009615800446428582 |

Las cinco semillas no son 250 pedidos independientes. Son cinco mediciones de los mismos 50.

## Target

Cada media de target es la media de las cinco medias de semilla, con 25 pedidos en el denominador de cada semilla.

| Target | Pedidos | normalized−raw | raw−heurística | normalized−heurística |
| --- | --- | --- | --- | --- |
| euro-pallet | 25 | -0.0019433687500000029 | 0.00047931249999999623 | -0.0014640562500000068 |
| rollcontainer | 25 | 0.004739148214285701 | -0.02250669285714286 | -0.01776754464285716 |

## Fallos y discrepancias

No hay filas de fallo. Los recuentos de `method_failure`, geometría inválida, peso, discrepancia de entrada y fallo de worker son cero. Hay 308 empaquetados parciales válidos: tienen ítems sin colocar y no cuentan como fallo. El recálculo desde los `result.json` coincide con `packing/aggregate.json`. La lista de discrepancias está vacía.

## Regla congelada

- A. El promedio normalized−raw es 0.001397889732142849 y es mayor que cero.
- B. La diferencia es positiva en tres semillas, 43, 44 y 45. Hacen falta cuatro.
- C. El promedio normalized−heurística es -0.009615800446428582 y no es mayor que cero.

La decisión predefinida es abandonar esta configuración. No se elige una semilla ni se cambia un umbral.

## Imitación y packing

En el entrenamiento publicado, el `val_loss` del brazo normalizado fue menor que el del brazo raw en las cinco semillas. Esa es una mejora de imitación sobre las transiciones de BC. El packing de estos 50 pedidos no convierte esa mejora en la regla de avance: el promedio frente a raw es positivo, pero faltan semillas positivas y el brazo normalizado queda por debajo de la heurística compartida.

## Alcance

Esto es desarrollo, no una confirmación. No demuestra superioridad frente a PCT ni estabilidad física. Los 50 pedidos quedan observados en `packing/verification.json`. Una versión futura no puede presentarlos como confirmación no inspeccionada. El registro histórico del paso 09 y los protocolos congelados no se reescribieron.

La evidencia de packing ocupa 168059136 bytes. La evidencia de entrenamiento previa sigue en 1045517 bytes.
