# Piloto interno geométrico

Estado: **listo para implementar el evaluador piloto**.

No es un piloto ejecutado ni una evaluación confirmatoria. Compara dos políticas del repositorio sobre el mismo generador y el mismo problema convertido. No es una comparación externa.

## Pregunta

¿La política aprendida mejora la utilización geométrica frente a `GreedyBestFitPolicy` cuando ambas reciben las mismas candidatas y restricciones?

## Métodos

A. Checkpoint `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt`, llamado **actor seleccionado con best_epoch=0**. Ese valor, en `fit_ppo`, es el actor inicial anterior al bucle (`train_ppo.py`, líneas 471–484). No es una mejora demostrada mediante PPO. SHA256 del archivo, sin deserializarlo: `6139beb5c13c6a3f9c701626a1765cf690234f253c2a9b9e4c03185b0228ec24`.

B. `GreedyBestFitPolicy` (`policies.py`, líneas 33–73).

## Condiciones

Los 20 ids y su orden son los de `data/scale/val/order_ids.json`. Cada pedido conserva su target. El dataset fuente y el subconjunto vuelven a coincidir en los 20.

`_resolve_target_container` (`bed_bpp.py`, líneas 72–95) asigna:

- euro-pallet: 1200 × 800 × 2000 mm, id `EURO_PALLET`, volumen 1920000000 mm³.
- rollcontainer: 800 × 700 × 2000 mm, id `ROLLCONTAINER`, volumen 1120000000 mm³.

Esas medidas salen de `TARGET_SIZES_MM` (líneas 21–24). El volumen es largo × ancho × alto (`models.py`, `Container.volume`, líneas 76–77).

El peso máximo del contenedor es `DEFAULT_PALLET_MAX_WEIGHT_KG` = 1500 para los dos targets (líneas 26 y 89–94). `order_to_problem` no pasa un diccionario de restricciones. Para `3D_BPP`, distinto de `STACKING_AWARE`, `_default_constraints` enciende no solape, contención, rotación y peso máximo (líneas 144–149). `basic_stability`, `load_bearing`, `fragility` y `unloading_sequence` quedan en el default false del modelo (`models.py`, líneas 94–97). Esas banderas son las mismas para euro-pallet y rollcontainer.

Ambos métodos reciben ese problema convertido. Siguen iguales: `p=1`, `s=1`; orden de llegada; hasta seis permutaciones de la receta; el mismo generador `ExtremePointOnlineSession` y la misma `ValidatorMask`; descartar el ítem sin candidata legal y continuar (`loop.py`, líneas 72–80). El bucle entrega `remaining_count` a las dos políticas; `GreedyBestFitPolicy` no lo usa (`policies.py`, línea 73).

| Posición | Pedido | Target | Contenedor mm | Volumen mm³ |
| --- | --- | --- | --- | --- |
| 0 | 00107792 | rollcontainer | 800×700×2000 | 1120000000 |
| 1 | 00105320 | rollcontainer | 800×700×2000 | 1120000000 |
| 2 | 00105445 | rollcontainer | 800×700×2000 | 1120000000 |
| 3 | 00101348 | euro-pallet | 1200×800×2000 | 1920000000 |
| 4 | 00105737 | rollcontainer | 800×700×2000 | 1120000000 |
| 5 | 00104464 | rollcontainer | 800×700×2000 | 1120000000 |
| 6 | 00109069 | rollcontainer | 800×700×2000 | 1120000000 |
| 7 | 00107675 | rollcontainer | 800×700×2000 | 1120000000 |
| 8 | 00100130 | euro-pallet | 1200×800×2000 | 1920000000 |
| 9 | 00106558 | rollcontainer | 800×700×2000 | 1120000000 |
| 10 | 00102736 | rollcontainer | 800×700×2000 | 1120000000 |
| 11 | 00101358 | rollcontainer | 800×700×2000 | 1120000000 |
| 12 | 00101236 | rollcontainer | 800×700×2000 | 1120000000 |
| 13 | 00101411 | rollcontainer | 800×700×2000 | 1120000000 |
| 14 | 00106265 | euro-pallet | 1200×800×2000 | 1920000000 |
| 15 | 00104873 | euro-pallet | 1200×800×2000 | 1920000000 |
| 16 | 00101899 | euro-pallet | 1200×800×2000 | 1920000000 |
| 17 | 00106028 | euro-pallet | 1200×800×2000 | 1920000000 |
| 18 | 00100415 | rollcontainer | 800×700×2000 | 1120000000 |
| 19 | 00105295 | euro-pallet | 1200×800×2000 | 1920000000 |

Recuento verificado: 7 euro-pallet y 13 rollcontainer. Estos 20 pedidos son desarrollo y selección, no una prueba confirmatoria.

## Agregado fijado antes de ejecutar

`U_geom` de cada pedido usa el volumen de su propio contenedor.

`delta_i = U_geom(actor, i) - U_geom(heurística, i)`.

El resultado primario agregado es la media aritmética de los 20 `delta_i`, con el mismo peso por pedido.

Por target, el informe debe incluir media y mediana de delta, victorias, empates y derrotas, fallos de cada método, y el tamaño del grupo. Empate si `abs(delta) <= 1e-9`.

Ese agregado depende de la composición de estos 20 pedidos. No equivale a una ventaja demostrada para cada target ni para toda la colección.

Una salida inválida, un crash o un timeout es un fallo: `U_geom = 0` en el agregado, con las cifras brutas conservadas. Los fallos permanecen en el denominador de los 20. El auditor independiente revisa dimensiones, identidades, contención y solapes. Las secundarias siguen siendo la fracción de ítems colocados, la fracción del volumen solicitado que se coloca, la altura máxima, el número y tipo de fallos, y el tiempo solo como diagnóstico.

Este agregado no se sustituye después por otro que resulte más favorable. Todavía no hay cifras.

## Frases

Permitido solo después de ejecutar el evaluador:

«En este conjunto de desarrollo, bajo el protocolo geométrico especificado, el actor obtuvo una diferencia de X frente a GreedyBestFit.»

X no se sustituye aquí.

Todavía no permitido: «Superamos a PCT.», «Mejoramos el estado del arte.», «Demostramos estabilidad física.», ni «Confirmamos generalización» con este piloto.

## Bloqueos

No queda bloqueo de protocolo para implementar el evaluador. La mezcla de targets deja de ser un bloqueo: cada pedido usa el contenedor de su target y los dos métodos reciben el mismo problema.

La reserva confirmatoria no cambia. Los cuatro ids `00101249`, `00102764`, `00108147` y `00109619` siguen excluidos por precaución. Los 675 euro-pallet de `full.test` con exposición incierta no se declaran limpios y no se elige un tamaño.
