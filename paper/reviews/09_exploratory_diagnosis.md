# 09 — diagnóstico exploratorio del actor y del teacher

Commit de lectura: `881213f85687debe53a30dc82e9d09e2a4ca2752` en `research/paper-online-packing`. No hubo entrenamiento, ni forward, ni una política nueva, ni commit, ni push. La clasificación del paso 08 sigue siendo `no_concluyente`. Este diagnóstico usa resultados ya observados y no es confirmatorio.

## Hallazgos observados

Sobre los 200 pares, el volumen de los ítems exclusivos explica la diferencia de volumen colocado en los 200 pedidos. El residual máximo es 0. No hay planes finales iguales. Hay 147 conjuntos colocados distintos y 53 con el mismo conjunto y geometría distinta. Esos 53 tienen delta 0: coinciden con los 53 empates publicados. Toda la diferencia de `U_geom` está en los 147 conjuntos distintos, cuya media de delta es -0.0008079185819565899 y cuya mediana es 0.00527500000000003.

La primera divergencia observable es de orientación en 131 pedidos y de posición en 69. En 112 el prefijo común tiene longitud 0: el primer ítem queda en el origen para los dos métodos y cambia la orientación. La longitud media del prefijo es 1.395 y la mediana es 0. Esa primera diferencia no es una causa: las capturas no guardan las candidatas descartadas.

El actor usa 6477 colocaciones permutadas y 1633 sin cambio de ejes. La heurística usa 6141 y 1957. La altura final media es 1987.97 mm y 1983.42 mm. Esas alturas no verifican estabilidad física.

La selección de casos es posterior al resultado y desempató por id. No es una muestra confirmatoria.

| Pedido | Target | Delta | Prefijo | Primera divergencia | Solo actor | Solo heurística |
| --- | --- | --- | --- | --- | --- | --- |
| 00109068 | rollcontainer | 0.10401071428571429 | 2 | posición de `00100858#3` | 4 | 0 |
| 00106938 | rollcontainer | 0.09837499999999999 | 0 | orientación de `00106130#1` | 5 | 1 |
| 00105615 | euro-pallet | 0.09261731770833337 | 0 | orientación de `00110459#1` | 3 | 0 |
| 00107571 | rollcontainer | 0.0741196428571429 | 0 | orientación de `00104130#1` | 4 | 1 |
| 00108776 | rollcontainer | 0.07285714285714284 | 0 | orientación de `00100264#1` | 1 | 0 |
| 00107288 | rollcontainer | -0.1461776785714286 | 0 | orientación de `00105097#1` | 0 | 3 |
| 00107781 | rollcontainer | -0.12537500000000001 | 0 | orientación de `00109731#1` | 0 | 2 |
| 00106828 | rollcontainer | -0.11890870535714282 | 0 | orientación de `00107888#1` | 0 | 2 |
| 00102982 | euro-pallet | -0.10840416666666663 | 0 | orientación de `00102548#1` | 0 | 5 |
| 00105421 | rollcontainer | -0.09968750000000004 | 0 | orientación de `00105511#1` | 1 | 2 |

En `00109068` el ítem `00100858#3` mide 330×210×290 mm y conserva esa orientación. El actor lo apoya en `(0, 0, 290)` y la heurística en `(0, 210, 0)`. El actor coloca además `00100744#26`, `00100744#27`, `00102470#28` y `00106551#29`. En `00107288` el primer ítem `00105097#1` mide 390×280×240 mm, ambos lo apoyan en el origen, el actor lo orienta a 390×240×280 mm y la heurística conserva 390×280×240 mm. La heurística coloca además `00106593#17`, `00110569#19` y `00102125#24`. Las coordenadas del resto de exclusivos están en `paper/results/09_policy_diagnostics.json`.

## Etiquetas BC

Los hashes de los dos pickle coinciden con el resultado 06A antes y después de la lectura. El teacher guardado es `receding_horizon_ep` y el régimen es `p=1`, `s=1`. Hay 1006 transiciones de train y 356 de validación, 1362 en total. Veintitrés tienen una sola candidata y ninguna elección efectiva; su etiqueta es 0.

En las otras 1339, los campos guardados permiten reconstruir la selección GreedyBestFit: la vista previa está a cero, el buffer es 0 y `rank_0..rank_3` reproducen `label_volume` en las 1339. El índice reconstruido es 0 en las 1339, porque las candidatas ya llegan ordenadas por `rank_key`. El teacher coincide con ese índice en 349/987 de train, 131/352 de validación y 480/1339 en conjunto. Discrepa en 638, 221 y 859. Esa coincidencia no demuestra calidad del teacher. El teacher simula el resto de la cola; el actor con `p=1` no observa esos ítems futuros. Las doce características de vista previa, `buffer_index_n`, `bin_index_n` e `item_can_rotate` son constantes en las 50605 filas. `rank_0` va de -691200 a -1500, en milímetros cuadrados de contacto, mientras las coordenadas normalizadas permanecen en `[0, 1]`. `rank_1..rank_3` están en milímetros. No hay valores no finitos. `n_packed_n` vale 1 en 1144 filas y `remaining_n` vale 1 en 4295: ahí el recorte a 50 ítems está saturado.

## Hipótesis aún no probadas

1. La orientación inicial que el teacher privilegiado elige, y que GreedyBestFit no elige en 859 de 1339 pasos con elección, cambia el conjunto colocado y con él `U_geom`. Experimento de desarrollo: reetiquetar solo las transiciones BC ya existentes con el índice GreedyBestFit reconstruible y ajustar un actor en esos pedidos, evaluándolo en pedidos que no estén entre los 220 ya observados. Se abandona la vía si en ese desarrollo la primera orientación sigue separándose con frecuencia parecida o el delta medio permanece en una banda alrededor de cero fijada antes de ver ese resultado.

2. Las 13 características constantes y la escala cruda de `rank_0..rank_3` dominan o desperdician la puntuación del actor en `p=1`. Experimento de desarrollo: el mismo corte BC, sin las columnas constantes y con el rango en la escala del contenedor, comparado con las 35 características actuales. Se abandona si ni la coincidencia con la etiqueta ni un delta geométrico de desarrollo, fuera de los 220, se mueve respecto de un umbral fijado de antemano.

3. Igualar solo la pose dentro de un mismo conjunto no mueve la media de `U_geom`: en estos 53 pedidos el delta ya es 0. Experimento de desarrollo: en pedidos fuera de los 220, medir qué fracción del delta absoluto la aportan los ítems exclusivos. Se abandona cualquier objetivo limitado a la pose si esa fracción sigue siendo la totalidad del delta.

No se implementa ninguno. No se amplía la muestra de 200 para buscar significación. Estos 200 pedidos y los 20 del piloto quedan registrados como observados. Una versión futura ajustada con este diagnóstico no puede presentarlos como confirmación sin inspeccionar. Los protocolos conservan sus campos históricos.

## Limitaciones

Las capturas no contienen los contrafactuales de cada paso. Las transiciones no guardan `look` ni la lista de candidatas fuera del orden ya ordenado por `rank_key`; por eso la reconstrucción se limitó a los casos con vista previa vacía. La identidad histórica del archivo BC sigue no comprobada. La estabilidad física sigue sin verificar. Este texto no afirma superioridad frente a PCT, una mejora obtenida mediante PPO, mayor eficiencia ni un resultado publicable.
