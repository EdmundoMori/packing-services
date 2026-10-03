# 15 — diagnóstico de utilidad del teacher

Ejecutado el 2026-10-03 sobre `8fb808246bcaf0b024440b9d7d9015b23c5c5386`, rama `research/paper-online-packing`. Una sola corrida, CPU, una tentativa y timeout de 300 segundos por pedido. No hubo entrenamiento, ni otro actor, ni otra heurística, ni reintento, ni commit, ni push. El protocolo `14_teacher_probe.json` sigue con `executed=false`. La configuración de normalización del paso 13 sigue abandonada.

Comando:

```bash
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_teacher_probe.py --protocol /home/edmundo/packing-services/paper/protocols/14_teacher_probe.json --comparator /home/edmundo/packing-services/paper/results/11_normalization_ablation/packing --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --output /home/edmundo/packing-services/paper/results/14_teacher_probe
```

Estado del manifiesto: `complete`. Código de salida 0. Inicio `2026-10-03T12:04:11.168Z`, fin `2026-10-03T12:29:18.360Z`, `elapsed_ms` 1507192. La salida estándar quedó vacía. El avance se leyó contando `result.json`: 3 a los dos minutos, 26 a los doce, 46 a los veinticuatro, y 50 al cerrar. `CUDA_VISIBLE_DEVICES` iba vacío. El manifiesto guarda el argv del script, sin el prefijo del intérprete ni esa variable.

## Integridad

Hay 50 `result.json` únicos y coinciden, en orden, con `development_sample.execution_items` del protocolo 10. Las cuotas son 25 euro-pallet y 25 rollcontainer. Cada caso tiene snapshot (`input.json`), `result.json`, `audit.json` y `worker.json`. Hay captura en 49 casos. `00107947` no tiene captura porque el worker agotó el timeout.

El comparador publicado fue aceptado. Su digest recalculado es `7073d4898fa8415b53aaa9250e0065daa48f2d5cb10da4a79ac526fa1c280844`, el mismo digest congelado. No se relanzó GreedyBestFit.

El fallo operativo entra con `effective_u_geom` 0. `physical_stability_verified` permanece `null` en los 50 resultados. El recálculo está en `paper/results/14_teacher_probe/verification.json`.

## Resultados

La métrica primaria es la media de `U_geom(teacher) − U_geom(GreedyBestFit)` sobre los 50 pedidos, con el fallo dentro del denominador. La tolerancia de empate es `1e-9`.

| | Delta | Puntos porcentuales |
| --- | --- | --- |
| Media | -0.021117453869047634 | -2.1117453869047633 |
| Mediana | 0.0 | 0.0 |

Victorias 10, empates 22, derrotas 18. La media y esos recuentos coinciden con `comparison.json`. La mediana no está en `comparison.json`; el recálculo la añade. Los dos valores centrales ordenados son 0 y 0.

| Target | n | Media | Mediana | Victorias | Empates | Derrotas | Fallos |
| --- | --- | --- | --- | --- | --- | --- | --- |
| euro-pallet | 25 | -0.028390104166666673 | 0.0 | 3 | 19 | 3 | 1 timeout |
| rollcontainer | 25 | -0.013844803571428583 | -0.018637500000000085 | 7 | 3 | 15 | 0 |

En puntos porcentuales, la media de euro-pallet es -2.8390104166666674 y la de rollcontainer es -1.3844803571428583. `comparison.json` publica solo las medias de target, y coinciden.

## Fallos

Un fallo, tipo `teacher:method_failure`. Pedido `00107947`, euro-pallet, `worker_status=timeout` a los 300.19389370900035 segundos. `U_geom` efectivo del teacher 0. El heurístico publicado en ese pedido vale 0.666125. El delta es -0.666125 y aporta -0.0133225 a la media de 50. Esa aportación es 0.6308762449590153 de la suma de los deltas. Permanece en el resultado primario.

Ese timeout es una limitación del presupuesto de 300 segundos. `worker.json` no trae `diagnostics` ni captura, así que las decisiones de ese pedido quedan desconocidas. Los otros 49 pedidos terminaron con `worker_status=ok`. Su media, que no sustituye a la de los 50, es -0.007954034560252683 (-0.7954034560252683 puntos porcentuales), con 10 victorias, 22 empates y 17 derrotas. Rollcontainer no tiene fallos operativos y su media ya es negativa.

## Diagnósticos de decisiones

La fuente es `worker.json`, no el cero que `result.json` escribe cuando faltan diagnósticos.

En los 49 pedidos con diagnóstico conocido hay 1980 decisiones, 193 de ellas con fallback y 1950 con varias candidatas. El fallback aparece en 28 pedidos. Los 49 pedidos conocidos tienen al menos una decisión con varias candidatas. `00107947` queda fuera de esas sumas: su número de decisiones y de fallback es desconocido, no cero.

`comparison.json` publica `orders_with_fallback` 28 y `orders_with_multi_candidate_decisions` 49. Esas cifras no se han cambiado. Coinciden con los pedidos conocidos que tienen diagnóstico positivo, porque `result.json` de `00107947` guardó `fallback_steps` 0 y `multi_candidate_steps` 0. La discrepancia es esa representación: el worker no midió esas decisiones. La media, la mediana, las victorias, los empates, las derrotas y los fallos no cambian por esa lectura.

El uso del fallback queda descrito. Esta corrida no atribuye el signo de la media a ese fallback.

## Interpretación

No hay ventaja media observada. No justifica otra campaña BC que solo imite este teacher sin revisar antes sus etiquetas u objetivo.

El teacher observa el resto de la cola durante la simulación. GreedyBestFit, con p=s=1, no. `same_observability_as_greedy` permanece falso. Esta corrida deja `not_upper_bound` y `not_online_homologated_baseline` en verdadero, `confirmatory` en falso y `physical_stability_verified` en null. No es PCT ni una prueba de superioridad del actor.

## Evidencia

`paper/results/14_teacher_probe` ocupa 14232870 bytes según `du -sb` y 14019878 bytes de contenido en 302 archivos. El mayor archivo mide 574714 bytes. `verification.json` está dentro de esa carpeta. `git diff` no muestra cambios en el protocolo 14 ni en `paper/results/11_normalization_ablation`.
