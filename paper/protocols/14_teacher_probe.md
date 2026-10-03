# 14 — diagnóstico de utilidad del teacher

Protocolo de desarrollo. No está ejecutado. No entrena, no abre pickle ni checkpoint, y no vuelve a empaquetar los 50 pedidos en este paso. No es una prueba confirmatoria. El teacher no es un upper bound ni un baseline online homologado. `physical_stability_verified` permanece `null`.

La normalización del paso 13 incumplió la regla de avance y esa configuración queda abandonada. Este diagnóstico no la reabre.

## Pregunta

¿Las decisiones de `receding_horizon_ep`, aplicadas secuencialmente, mejoran `U_geom` en los 50 pedidos de desarrollo ya observados?

La muestra es `development_sample.execution_items` del protocolo 10: 25 euro-pallet y 25 rollcontainer. Ya fueron observados. No se reservan pedidos nuevos.

## Teacher

El maestro existente elige una candidata ya legal. En cada paso vuelve a decidir sobre el estado real. La simulación interna ve el resto de la cola, se restaura y no es el empaquetado final. GreedyBestFit y el actor, con p=s=1, ven el buffer y la preview. Esa observabilidad no es la misma y queda registrada aparte.

Geometría, orden de llegada y p=s=1 se conservan. Una tentativa, CPU y timeout de 300 segundos. Un fallo entra con `U_geom` efectivo 0 y permanece en el denominador. El tiempo es solo diagnóstico.

## Comparador

Los 50 resultados heurísticos de `paper/results/11_normalization_ablation/packing/` se reutilizan. La lectura de sus identificadores, hashes, configuración y código relevante acepta el contrato. No se ejecuta otra heurística.

El digest del comparador es `7073d4898fa8415b53aaa9250e0065daa48f2d5cb10da4a79ac526fa1c280844`.

## Métrica e interpretación

La métrica primaria es la media de `U_geom(teacher) - U_geom(GreedyBestFit)` sobre los 50 pedidos. También se guardan el desglose por target, victorias, empates, derrotas, fallos por tipo, uso del fallback, decisiones con varias candidatas y el tiempo diagnóstico.

- Sin ventaja media observada: no justifica otra campaña BC que solo imite este teacher sin revisar antes sus etiquetas u objetivo.
- Con ventaja media observada: investigar si esa ventaja puede aprenderse con la observación limitada del actor.
- Con fallos operativos importantes: separar una limitación del presupuesto de la calidad de las decisiones. No atribuir el resultado automáticamente a las etiquetas.

## Comando futuro

No se ha lanzado.

```bash
cd /home/edmundo/packing-services
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_teacher_probe.py --protocol /home/edmundo/packing-services/paper/protocols/14_teacher_probe.json --comparator /home/edmundo/packing-services/paper/results/11_normalization_ablation/packing --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --output /home/edmundo/packing-services/paper/results/14_teacher_probe
```
