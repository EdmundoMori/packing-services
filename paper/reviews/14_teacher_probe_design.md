# 14 — diseño del diagnóstico de utilidad del teacher

Preparado el 2026-10-03 sobre `c97ed114508e01ba6f4a4ebf94129dc68d638ec0`, rama `research/paper-online-packing`. No se entrenó, no se abrieron pickle ni checkpoints y no se empaquetaron los 50 pedidos. No hay commit ni push. La configuración de normalización del paso 13 sigue abandonada.

Protocolo: `paper/protocols/14_teacher_probe.md`.

## Qué hace el teacher

`receding_horizon_ep_index` en `online_policy_ml/src_ml/teacher.py`, líneas 32–95, elige una candidata que ya es legal.

- La cola que observa es el argumento `remaining`: toda la cola que queda, no solo el buffer. En la línea 48 la ordena por volumen descendente e identidad.
- La simulación toma `session.snapshot()` en la línea 45, hace `session.commit` dentro del bucle y restaura con `session.restore(snap)` en las líneas 73–74. Esa simulación no es el empaquetado final.
- La candidata seleccionada es la primera de esa simulación cuyo ítem está en el buffer y cuya pose coincide a 1 mm, con el mismo contenedor y las mismas dimensiones orientadas, líneas 76–93. Si la pose no coincide, elige la pose más cercana de ese ítem.
- El fallback es `privileged_volume_ep_index`, líneas 17–29 y 95: mayor volumen del buffer, luego menor `rank_key` y menor índice de buffer.
- `collect_order_transitions` en `online_policy_ml/src_ml/collect.py`, líneas 31–135, ya ejecuta el rollout completo. En cada paso llama a `label_index` y, en las líneas 117–119, hace un solo commit real y retira ese ítem de la cola.
- Un ítem sin candidata se descarta con `remaining.pop(0)`, líneas 69–72. El diagnóstico registra el mismo motivo que el bucle online: no hay colocación legal con el presupuesto de información actual.

El generador de etiquetas no devuelve la geometría de la solución. El diagnóstico repite ese control y llama a `receding_horizon_ep_index`. No define otra heurística con el nombre del teacher. Cada paso toma una decisión nueva. La simulación se comprueba restaurada antes del commit real.

GreedyBestFit, en `src/packing_services/online/policies.py` líneas 63–73, no usa el resto de la cola: descarta `remaining_count` y mira la preview `p`. Con p=s=1, actor y heurística ven un ítem. El teacher, durante la simulación, ve el resto. Esa diferencia queda registrada y no se presenta como la misma observabilidad.

## Comparador

Los 50 heurísticos de `paper/results/11_normalization_ablation/packing/` se pueden reutilizar. Identificadores, targets 25/25, p=s=1, algoritmo `online_3d_bpp_heuristic`, restricciones, contenedor, capturas y el hash conjunto `7073d4898fa8415b53aaa9250e0065daa48f2d5cb10da4a79ac526fa1c280844` coinciden con el protocolo. El código que los escribió sigue igualando el manifiesto de packing. No se lanza otra heurística.

## Pruebas

`python -m unittest discover -s paper/tests -p 'test_*.py'` cubre, con pedidos sintéticos, la restauración, el commit único de una candidata legal, el descarte del ítem más antiguo, el fallback, la captura contrastada con el snapshot, el timeout con continuación y el rechazo del comparador si el algoritmo no es el heurístico. La lectura de los 50 JSON guardados no ejecuta esos pedidos. `physical_stability_verified` permanece `null`.

## Comando futuro

No se ha lanzado.

```bash
cd /home/edmundo/packing-services
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_teacher_probe.py --protocol /home/edmundo/packing-services/paper/protocols/14_teacher_probe.json --comparator /home/edmundo/packing-services/paper/results/11_normalization_ablation/packing --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --output /home/edmundo/packing-services/paper/results/14_teacher_probe
```
