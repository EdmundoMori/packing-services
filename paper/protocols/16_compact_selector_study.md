# 16 — contrato geométrico común y comparador OnlineBPH

Preparado sobre `6fc55b6b74bfa46697b1fd25a6eb52cc4e71a1a2`. La cuadrícula del selector no se ejecuta. Este documento no reproduce Table 1 de Zhao ni la evaluación oficial de Kagerer.

El JSON congelado es `paper/protocols/16_compact_selector_study.json`.

## Tres protocolos

- Zhao, ICLR 2022: el artículo PCT. El PDF de OpenReview respondió 403 en esta sesión, así que las condiciones de Setting 2 atribuidas al paper quedan **no verificadas** en página. El código clonado, commit `5e7b4238b18310af4529e0f85157d17de605850c`, usa `setting == 2` con seis orientaciones y `check_box` que devuelve verdadero antes del chequeo de estabilidad (`space.py`).
- Kagerer, IJRR 2023: la evaluación oficial BED-BPP. El README de la rama `paper-implementation` describe `run_heuristic_O3DBP_3_2.py` para preview `p=3` y selección `s=2`. La página del artículo no se releyó aquí.
- Este experimento: secuencia original, un contenedor del target propio, hasta seis permutaciones, contención y no solape, peso máximo, estabilidad y load-bearing inactivos, `p=s=1`, y parada cuando el ítem actual no tiene candidata legal.

Las corridas publicadas de los pasos 08, 13 y 15 tenían el peso máximo activo y seguían colocando el sufijo. Sus `U_geom` no son baseline de este contrato.

## Smoke

La regla, fijada antes de mirar utilizaciones, toma los tres primeros euro-pallet y los dos primeros rollcontainer de `development_sample.execution_items`, ordenados por `position`:

| Pedido | Target | Posición |
| --- | --- | --- |
| 00100084 | euro-pallet | 0 |
| 00100101 | rollcontainer | 1 |
| 00100802 | rollcontainer | 2 |
| 00100909 | euro-pallet | 3 |
| 00101315 | euro-pallet | 4 |

Como máximo esos cinco pedidos y diez casos, con GreedyBestFit y OnlineBPH. CPU, un intento, 300 segundos. Un fallo se conserva.

## Selector futuro, sin ejecutar

`score = contacto_normalizado - a × incremento_altura_normalizado - b × techo_normalizado + c × apoyo`, con `a,b ∈ {0, 0.5, 1, 2}` y `c ∈ {0, 0.25}`: 32 configuraciones. El ajuste propuesto usa 40 pedidos de `train_order_ids_full.json`, 20 por target, fuera de los 50 de desarrollo y de los 200 de la evaluación 07. La validación propuesta aplica las tres mejores de train a esos mismos 50. La puerta es una regla de ingeniería: mejora media de al menos 0.005 frente a Greedy y medias no negativas en ambos targets. No es una prueba estadística.
