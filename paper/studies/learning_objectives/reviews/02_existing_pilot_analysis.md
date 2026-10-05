# Análisis exploratorio del piloto existente

Este análisis se diseñó después de observar el piloto counterfactual. No es confirmatorio. No declara equivalencia. No selecciona semilla. No reejecuta packing.

Fuente: 84 `result.json` en `paper/studies/counterfactual_ranking/learning_packing/cases/`. Salida: `results/02_existing_pilot_analysis.json`.

## Integridad

Doce pedidos (6 euro-pallet, 6 rollcontainer), tres semillas, 84 claves únicas. Todos los `effective_u_geom` son finitos y entran en el denominador. No se repararon valores de origen.

## Definición

Para cada pedido `i`,

`d_i = media_s ( U_geom(preferencias, i, s) − U_geom(clasificación, i, s) )`,

con `s ∈ {11,23,37}`. Análogamente para preferencias−Greedy y clasificación−Greedy. Greedy no depende de la semilla.

La media de los doce `d_i` coincide con la media de las tres medias por semilla: `0.03094863126240079`. Las medias publicadas de preferencias−Greedy y clasificación−Greedy se reproducen exactamente: `-0.019783628885582008` y `-0.050732260147982794`.

## Resumen del contraste preferencias−clasificación

| Agregado | Valor |
| --- | ---: |
| Media de `d_i` | 0.03094863126240079 |
| Mediana de `d_i` | 0.015054253472222185 |
| Pedidos con `d_i > 0` | 7 |
| Pedidos con `d_i = 0` (tol. 1e-9) | 1 |
| Pedidos con `d_i < 0` | 4 |
| Media euro-pallet | 0.0013134331597222132 |
| Media rollcontainer | 0.06058382936507937 |

Las medias por semilla son `0.03409619760664681`, `0.02844305555555555` y `0.030306640625000002`.

## Bootstrap exploratorio

Unidad: pedido. Semillas ya reducidas dentro de `d_i`. Estratificación por target con cuotas 6/6. 20000 réplicas, `numpy.random.default_rng(20261004)`, percentiles 2.5 y 97.5 con `method="linear"`.

Intervalo 95 % exploratorio de la media de `d_i`: `[-0.004208279906580691, 0.07644716396432695]`.

El intervalo incluye el cero. No se usa para confirmación retrospectiva.

## Leave-one-order-out

Ningún pedido, al retirarse, cambia el signo de la media de `d_i` respecto al signo positivo del conjunto completo. Eso no autoriza excluir pedidos ni declarar robustez confirmatoria.

## Lectura acotada

En esta muestra de desarrollo, preferences supera a classification en media, queda por debajo de Greedy en media, y el intervalo exploratorio de preferences−classification cruza cero. El desajuste de candidatas etiquetadas frente al despliegue permanece fuera de este recálculo.
