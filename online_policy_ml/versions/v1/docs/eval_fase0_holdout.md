# Fase 0 de Evaluación: Comparación de Producto en el Holdout

> **Alcance histórico.** Cifras de un ciclo anterior a la corrección del maestro (septiembre 2026).
> El hallazgo (la ventaja de val/test corto no se transfiere al holdout) se confirmó con el
> checkpoint actual: empate vs heurístico. Las cifras vigentes están en
> [`../README.md`](../README.md) §5. Este archivo se conserva como registro del primer ciclo.

Pertenece a la pista de **evaluación de producto**. Índice: [`README.md`](README.md).

| | |
|---|---|
| **Flujos** | `eval_fase0_holdout`, `eval_fase0_baseline_p3s2` |
| **Fuente** | `scripts/run_holdout_offline_vs_online.py` |
| **Módulo** | `src/packing_services/benchmark/holdout_offline_online.py` |
| **Estado** | Terminado |

---

## Motivación

Hasta esta fase, toda la evidencia sobre la política aprendida provenía de validación y test cortos
(fases 3 a 5 de entrenamiento) y de un smoke test sobre un único pedido, `00100408`, que además es el
más pequeño del conjunto. No existía ninguna afirmación a nivel de producto.

Esta fase produce esa afirmación: recorre los **cinco** pedidos del holdout completos, comparando
modo offline y modo online sobre la misma entrada, el mismo validador y las mismas métricas.

---

## Diseño

### Pedidos

Los cinco pedidos de `examples/5_bed-bpp.json`, que nunca intervinieron en entrenamiento ni en
ajuste. Se respeta el destino que declara cada pedido en BED-BPP, de modo que dentro de un pedido
todos los motores reciben el mismo contenedor.

| Pedido | Ítems | Destino |
|--------|-------|---------|
| `00100001` | 44 | rollcontainer |
| `00100002` | 38 | rollcontainer |
| `00100003` | 34 | rollcontainer |
| `00100004` | 58 | euro-pallet |
| `00100408` | 26 | euro-pallet |

### Motores

| Modo | Motor | Presupuesto |
|------|-------|-------------|
| offline | `extreme_points_3d` | pedido completo, `volume_desc` |
| offline | `best_fit_decreasing_3d` | pedido completo, `volume_desc` |
| offline | `layer_based_palletization` | pedido completo, `volume_desc` |
| online | `online_3d_bpp_heuristic` | p=1, s=1 |
| online | `drl_policy_3d_bpp` con `mlp_v1_p1s1.pt` | p=1, s=1 |
| online | `online_3d_bpp_heuristic` | p=3, s=2 |
| online | `drl_policy_3d_bpp` con `mlp_v1_p3s2.pt` | p=3, s=2 |

Cada política aprendida se enfrenta al heurístico **en su mismo presupuesto de información**, de
modo que la comparación sea a igual información y no a igual nombre.

### Criterio de Ranking

Se importa de `joint_single_container`, para que la comparabilidad no dependa del módulo nuevo:
soluciones válidas, mayor `volume_utilization`, menor `items_unpacked`, menor tiempo.

---

## Métricas Derivadas

La métrica `volume_utilization` divide el volumen empacado por el volumen del **contenedor
completo**. Cuando el pedido entero cabe, todos los motores producen exactamente la misma cifra y la
métrica deja de discriminar: en `00100004` los seis motores dan 61.4 % y en `00100408` dan 64.6 %.

Para separar una carga compacta de una dispersa se añadieron dos columnas **derivadas de la propia
solución**, sin modificar el contrato de métricas:

| Columna | Definición |
|---------|-----------|
| `load_height_mm` | Altura de carga alcanzada, máximo de `position.z + orientation.height` |
| `envelope_utilization` | Volumen empacado dividido por huella del contenedor multiplicada por la altura alcanzada |

En `00100408`, `extreme_points_3d` cierra la carga en 1685 mm con 76.7 % de cubo en el envolvente
ocupado, mientras el resto de motores llega a los 2000 mm con 64.6 %. Esa diferencia de calidad es
invisible para la métrica actual.

---

## Resultados

Treinta corridas, todas válidas, cero violaciones de restricciones. Sobre 200 ítems en total:

| Motor | Válidos | Primeros | Empacados | Fuera | `util`~ | `util@alto`~ | `t`~(s) |
|-------|---------|----------|-----------|-------|---------|--------------|---------|
| offline `best_fit_decreasing_3d` | 5/5 | 2 | 190 | 10 | 70.9 % | 70.9 % | 0.31 |
| offline `extreme_points_3d` | 5/5 | 2 | 183 | 17 | 69.1 % | 73.4 % | 0.17 |
| online `heuristic#p1s1` | 5/5 | 0 | 187 | 13 | 66.8 % | 66.8 % | 1.77 |
| online `mlp_v1_p1s1` | 5/5 | 0 | 186 | 14 | 66.2 % | 67.0 % | 1.80 |
| online `mlp_v1_p3s2` | 5/5 | 0 | 185 | 15 | 66.1 % | 66.1 % | 3.13 |
| offline `layer_based_palletization` | 5/5 | 1 | 117 | 83 | 53.1 % | 54.0 % | 0.03 |

### Baseline al Mismo Presupuesto

El flujo complementario `eval_fase0_baseline_p3s2` corre el heurístico con lookahead `p=3` para
enfrentarlo a `mlp_v1_p3s2` en su propio régimen. Se limita a los dos pedidos más pequeños porque su
coste es prohibitivo: 95 s en el pedido de 26 ítems y más de 22 minutos en el de 44, que se
interrumpió.

Sobre `00100003`, a igual presupuesto:

| Motor | Empacados | `util` | `t`(s) |
|-------|-----------|--------|--------|
| `online_3d_bpp_heuristic#p3s2` | 28 | 71.5 % | 31.2 |
| `drl_policy_3d_bpp#mlp_p3s2` | 27 | 68.7 % | 0.68 |

---

## Conclusiones

1. **La ventaja de la política aprendida no se transfiere.** Validación daba al MLP +0.7 puntos
   (0.6838 frente a 0.677) y test +0.8 (0.6793 frente a 0.6716). En el holdout el signo se invierte:
   66.2 % frente a 66.8 %, con un ítem menos empacado. A presupuesto `p=3, s=2` la brecha es mayor.
2. **El valor real de `mlp_v1_p3s2` es la velocidad, no la calidad.** A igual presupuesto el greedy
   obtiene mejor cubo, pero a un coste unas 45 veces superior, y deja de ser operable en pedidos
   medianos.
3. **El modo offline domina al online**, como corresponde a quien ve el pedido completo. La
   diferencia de 4 puntos cuantifica el valor de la información anticipada en este conjunto.
4. **`layer_based_palletization` no sirve para BED-BPP.** Deja 83 de 200 ítems fuera. Aparece como
   primero en un pedido únicamente porque empata en cubo y es el más rápido, lo cual es otro síntoma
   del problema de la métrica.

---

## Reproducción

```bash
cd packing-services
source .venv/bin/activate

# Tabla principal: 5 pedidos, 6 motores
PYTHONPATH=src python scripts/run_holdout_offline_vs_online.py \
    --skip-greedy-lookahead \
    --json online_policy_ml/artifacts/reports/06_holdout_producto.json

# Baseline al mismo presupuesto, solo donde es asequible
PYTHONPATH=src python scripts/run_holdout_offline_vs_online.py \
    --order-id 00100003 --order-id 00100408 \
    --json online_policy_ml/artifacts/reports/07_holdout_p3s2_baseline.json
```

Sin `--skip-greedy-lookahead` el script incluye el heurístico `p3s2` sobre los cinco pedidos, lo cual
puede tardar horas.
