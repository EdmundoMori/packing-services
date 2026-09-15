# Fase 1 de Evaluación: Multi-Pallet

> **Alcance histórico.** Medido sobre checkpoints anteriores a la corrección del maestro.
> El defecto (con dos contenedores, los motores por puntos extremos parten la carga) es de
> scoring + distribución de entrenamiento de un solo contenedor: **sigue vigente**. No se
> corrige reentrenando 01–03. Siguiente medición: notebook `10` (sin reentrenar).
> Plan de modelado (PPO, un contenedor): [`../README.md`](../README.md) §7.

Pertenece a la pista de **evaluación de producto**. Índice: [`README.md`](README.md).

| | |
|---|---|
| **Flujo** | `eval_fase1_multipallet` |
| **Fuente** | `scripts/run_holdout_offline_vs_online.py --containers 2` |
| **Estado** | Terminado |

---

## Motivación

La [Fase 0](eval_fase0_holdout.md) dejaba entre 10 y 83 ítems fuera según el motor, con un solo
contenedor por pedido. En los tres pedidos de rollcontainer quedaban fuera entre 6 y 17 ítems, que
son exactamente los que absorbería un segundo pallet.

Un almacén no despacha pedidos incompletos: si la carga no entra en un pallet, se abre otro. Esta
fase mide qué ocurre cuando el sistema tiene esa opción disponible.

---

## Diseño

Se replica el destino nativo de cada pedido para ofrecer **dos contenedores idénticos** en la misma
`PackAlgorithmInput`, con identificadores distinguibles (`EURO_PALLET-1`, `EURO_PALLET-2`). Cada
motor decide por sí mismo si abre el segundo.

### Criterio de Ranking

Para el caso multi-contenedor se define un criterio propio, distinto del de Fase 0:

1. Soluciones válidas
2. Menor `items_unpacked`
3. Menor `containers_used`
4. Mayor `volume_utilization`
5. Menor tiempo

Los ítems fuera preceden al número de pallets deliberadamente. Si el orden fuera el inverso, dejar
carga en el muelle puntuaría mejor que abrir el segundo pallet, lo cual invierte la prioridad real de
la operación. El cubo va después porque se divide entre los contenedores efectivamente usados y ya
penaliza por sí solo abrir uno de más.

El ranking de un solo contenedor **no se modificó**, de modo que la tabla de Fase 0 sigue siendo
comparable.

---

## Resultados

Treinta corridas, todas válidas, cero violaciones.

| Motor | Empacados | Fuera | Pallets usados | `util`~ | `util@alto`~ | `t`~(s) |
|-------|-----------|-------|----------------|---------|--------------|---------|
| offline `layer_based_palletization` | 200/200 | 0 | **9** | 43.7 % | 52.6 % | 0.04 |
| offline `extreme_points_3d` | 200/200 | 0 | 10 | 37.3 % | 67.0 % | 0.12 |
| offline `best_fit_decreasing_3d` | 200/200 | 0 | 10 | 37.3 % | 39.2 % | 0.36 |
| online `mlp_v1_p1s1` | 200/200 | 0 | 10 | 37.3 % | 37.8 % | 2.89 |
| online `heuristic#p1s1` | 200/200 | 0 | 10 | 37.3 % | 37.6 % | 3.01 |
| online `mlp_v1_p3s2` | 200/200 | 0 | 10 | 37.3 % | 37.9 % | 5.81 |

El objetivo inmediato se cumple: con dos contenedores ningún ítem queda fuera. El resto de los
indicadores empeora.

---

## Defecto Encontrado

Cinco de los seis motores abren el segundo pallet en los cinco pedidos, sin excepción. El caso
decisivo es `00100408`, del que la Fase 0 ya había demostrado que cabe entero en un solo pallet con
los seis motores empacando 26/26 al 64.6 %.

Con dos contenedores disponibles, el reparto es el siguiente:

| Motor | Pallet 1 | Pallet 2 |
|-------|----------|----------|
| `layer_based_palletization` | 26 | — |
| `extreme_points_3d` | 15 | 11 |
| `best_fit_decreasing_3d` | 14 | 12 |
| `heuristic#p1s1` | 14 | 12 |
| `mlp_v1_p1s1` | 14 | 12 |
| `mlp_v1_p3s2` | 10 | **16** |

No se trata de abrir el segundo pallet prematuramente: la carga se parte casi por mitad, y
`mlp_v1_p3s2` coloca más en el segundo que en el primero. El cubo cae del 64.6 % al 32.3 % en ese
pedido, y del 70.9 % al 37.3 % en la media del holdout.

---

## Causa

El defecto tiene dos componentes que se refuerzan.

### Puntuación de Candidatas

La clave de selección de puntos extremos, en `_extreme_points.py`, premia el área de contacto:

```python
if self.selection == "best_fit":
    contact = self._contact_score(box, state)
    return (-round(contact, 6),) + blb
```

El suelo vacío del segundo pallet ofrece contacto igual a la huella completa de la caja con `z = 0`,
lo cual supera a casi cualquier posición apilada en el primero. No existe ningún término que premie
consolidar en el menor número de contenedores. `layer_based_palletization` se salva porque no usa
esta puntuación: llena por capas, contenedor a contenedor.

### Distribución de Entrenamiento

El encoder v1 expone la ocupación del contenedor de cada candidata (`used_height_n`,
`loaded_weight_n`) y el total colocado en la sesión (`n_packed_n`), de modo que la conjunción "este
pallet está vacío pero ya llevo catorce ítems colocados" **es representable** con 35 features. Lo que
nunca ocurrió es el caso: todas las instancias P2O tenían un solo contenedor, así que
`used_height_n = 0` coincidía siempre con `n_packed_n = 0`, es decir con el primer ítem del episodio.

El modelo aprendió a leer "pallet vacío" como "inicio de episodio, coloca libremente". Además,
`bin_index_n` existe en el vector pero su peso quedó sin entrenar, porque en entrenamiento valía
siempre 0.

---

## Consecuencia

El multi-pallet no es utilizable en su estado actual. La carencia no es de métrica ni de ajuste de
parámetros: falta una **disciplina de selección de contenedor**, que hoy no está escrita en ninguna
parte del sistema.

La secuencia de trabajo derivada de este hallazgo es el [Paso A](eval_pasoA_consolidacion.md)
(notebook `10`): mide cuánto de la brecha se cierra sin reentrenar. Es independiente del PPO
de un contenedor ([README del subproyecto](../README.md) §7).

---

## Reproducción

```bash
cd packing-services
source .venv/bin/activate
PYTHONPATH=src python scripts/run_holdout_offline_vs_online.py \
    --containers 2 --skip-greedy-lookahead \
    --json online_policy_ml/artifacts/reports/08_holdout_multipallet.json
```
