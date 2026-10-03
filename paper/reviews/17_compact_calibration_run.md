# 17 — calibración del selector compacto

Ejecutado el 2026-10-03 sobre `91ee3ed10cb028881c2d0823239c3203759b429d`, rama `research/paper-online-packing`. No hay commit. El protocolo 16 y los resultados de 16 y 16A no se modificaron.

`physical_stability_verified` permanece null. Eso no es estabilidad demostrada. Esta corrida no compara con OnlineBPH, PCT ni literatura, y no es una evaluación confirmatoria. Los mismos pedidos repetidos en las 32 configuraciones no son observaciones independientes.

## Congelación

Protocolo `paper/protocols/17_compact_calibration.json`, SHA256 `3f1349ebe5f5327530c3db341ae7888ec56d3506dc15ee861e04838645caac23`. Manifiesto `paper/results/17_compact_calibration/freeze.json`, escrito antes de empaquetar.

Dataset SHA256 `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`.

Fórmula `compact_contact_height_v1`: contacto normalizado menos `a` por el incremento de altura normalizado, menos `b` por el techo normalizado, más `c` por el apoyo. El contacto es `-rank_key[0] / (2(lw+lh+wh))`. No es una prueba de estabilidad.

La cuadrícula es exactamente `a,b` en {0, 0.5, 1, 2} y `c` en {0, 0.25}, 32 configuraciones, orden lexicográfico. No se amplió.

Train: los 40 IDs del protocolo 16, 20 por target, únicos, dentro de `full.train`, sin intersección con los 50 de desarrollo, los 200 del paso 07 ni sus nueve `positive_exclusion_ids`. Orden: la lista euro-pallet y después la rollcontainer.

Desarrollo: los 50 `execution_items` del protocolo 10, 25 por target, en ese orden.

La firma de clon es el SHA256 del target y de la secuencia de longitud, anchura, altura, peso y `allowed_orientations` del snapshot compacto, antes de colocar. No hubo firmas compartidas entre train y desarrollo. El origen BED-BPP no trae un permiso de rotación por ítem; el permiso usado es el de ese snapshot.

Los cinco Greedy del smoke no se reutilizaron: `compact_study.py` y el worker ya no tienen el hash de aquella corrida. Se ejecutaron los 40 y los 50 Greedy de este protocolo. No se reutilizaron las `U_geom` de los pasos 08, 13 ni 15.

Antes de lanzar, la pared máxima de los cinco Greedy del smoke, aplicada a 1520 casos, daba 11336 segundos. Lo ya consumido en los pasos 16 y 16A sumaba 58.1 segundos de pared de proceso. El presupuesto de 12 horas cabía, con la incertidumbre de que aquellos cinco pedidos no representan toda la muestra. La cuadrícula no se cambió después de ver resultados.

## Pruebas

122 pruebas, OK, antes del packing real. `git diff --check` no señaló espacios finales. Con coeficientes cero, el selector reprodujo las colocaciones de GreedyBestFit en el caso sintético. En los 40 de train, `a=b=c=0` empató los 40 pedidos con Greedy: media de delta 0 y marcador 0/40/0.

## Casos

1520 resultados, todos con `worker_status=ok`. Ningún `input_mismatch`, ningún fallo de geometría ni de contrato. No hubo timeouts ni crashes. La etapa quedó `complete`.

| Bloque | Casos |
| --- | --- |
| Greedy train | 40 |
| Cuadrícula train | 1280 |
| Greedy desarrollo | 50 |
| Top 3 en desarrollo | 150 |
| Total | 1520 |

Pared de reloj de la ejecución: 5088.68 segundos, con cuatro procesos. El presupuesto de 43200 segundos sigue por encima de esa pared y también de una cota de cuatro veces esa pared.

## Train

Media Greedy, igual a la de `a=b=c=0`: 0.6498141734. Euro-pallet 0.6407621973 (1001 ítems). Rollcontainer 0.6588661496 (649 ítems).

La tabla está ordenada por la regla congelada. El marcador es victorias/empates/derrotas frente a Greedy, con tolerancia descriptiva 1e-9. Esa tolerancia no elige la configuración.

| Configuración | Media U_geom | Media delta | V/E/D |
| --- | --- | --- | --- |
| a1_b0.5_c0 | 0.6655107420 | 0.0156965685 | 15/16/9 |
| a0_b1_c0 | 0.6628677765 | 0.0130536031 | 14/16/10 |
| a0.5_b1_c0 | 0.6628179178 | 0.0130037444 | 13/20/7 |
| a1_b2_c0 | 0.6613942478 | 0.0115800744 | 15/17/8 |
| a0_b2_c0 | 0.6602975663 | 0.0104833929 | 16/16/8 |
| a0_b2_c0.25 | 0.6597635396 | 0.0099493662 | 15/13/12 |
| a2_b2_c0 | 0.6592185131 | 0.0094043397 | 14/17/9 |
| a2_b0.5_c0 | 0.6577337902 | 0.0079196168 | 13/18/9 |
| a0.5_b0.5_c0 | 0.6568961693 | 0.0070819959 | 13/18/9 |
| a1_b1_c0 | 0.6563594041 | 0.0065452307 | 15/17/8 |
| a0.5_b2_c0 | 0.6562788088 | 0.0064646354 | 15/14/11 |
| a2_b1_c0 | 0.6560228713 | 0.0062086979 | 15/15/10 |
| a2_b1_c0.25 | 0.6559141460 | 0.0060999726 | 15/13/12 |
| a1_b2_c0.25 | 0.6537878960 | 0.0039737226 | 15/12/13 |
| a0_b0.5_c0 | 0.6531643780 | 0.0033502046 | 13/16/11 |
| a0.5_b2_c0.25 | 0.6527592018 | 0.0029450284 | 14/13/13 |
| a2_b0.5_c0.25 | 0.6522312586 | 0.0024170852 | 10/20/10 |
| a1_b1_c0.25 | 0.6507341846 | 0.0009200112 | 12/15/13 |
| a0.5_b1_c0.25 | 0.6504427765 | 0.0006286031 | 10/18/12 |
| a1_b0_c0 | 0.6501455666 | 0.0003313932 | 12/19/9 |
| a2_b2_c0.25 | 0.6501394840 | 0.0003253106 | 14/16/10 |
| a1_b0.5_c0.25 | 0.6500500872 | 0.0002359138 | 10/17/13 |
| a0_b0_c0 | 0.6498141734 | 0.0000000000 | 0/40/0 |
| a2_b0_c0 | 0.6497530815 | -0.0000610919 | 12/18/10 |
| a0.5_b0.5_c0.25 | 0.6476744808 | -0.0021396926 | 14/14/12 |
| a0.5_b0_c0 | 0.6475302225 | -0.0022839509 | 11/19/10 |
| a0_b1_c0.25 | 0.6424698672 | -0.0073443062 | 10/17/13 |
| a1_b0_c0.25 | 0.6423340116 | -0.0074801618 | 10/16/14 |
| a0.5_b0_c0.25 | 0.6421443092 | -0.0076698642 | 10/16/14 |
| a0_b0.5_c0.25 | 0.6377823338 | -0.0120318397 | 9/18/13 |
| a0_b0_c0.25 | 0.6366899751 | -0.0131241983 | 11/14/15 |
| a2_b0_c0.25 | 0.6335965692 | -0.0162176042 | 6/15/19 |

Top 3 por mayor media, sin empate que hubiera que romper: `a1_b0.5_c0`, `a0_b1_c0`, `a0.5_b1_c0`. Las medias recalculadas desde los 40 `result.json` coinciden.

En train, `a1_b0.5_c0` tiene media de delta 0.0156965685, mediana no usada para elegir, marcador 15/16/9. Euro-pallet 0.6496827897 (1015 ítems) y rollcontainer 0.6813386942 (675 ítems). No hubo fallos. El bucle medio fue 1.803 s, el arranque 1.846 s, la captura 0.037 s y la auditoría con escritura 7.383 s. La pared de proceso media fue 4.199 s. La auditoría queda fuera de esa pared.

## Desarrollo

Solo las tres configuraciones seleccionadas. Greedy en estos 50: euro-pallet 0.6395219323 (1287 ítems) y rollcontainer 0.6556994955 (729 ítems).

| Configuración | Media U_geom | Media delta | Mediana delta | V/E/D | Delta euro | Delta roll | Ítems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| a1_b0.5_c0 | 0.6486892920 | 0.0010785781 | 0 | 11/29/10 | -0.0000514063 | 0.0022085625 | 2019 |
| a0_b1_c0 | 0.6433256894 | -0.0042850246 | 0 | 10/25/15 | 0.0026680937 | -0.0112381429 | 2006 |
| a0.5_b1_c0 | 0.6466513121 | -0.0009594018 | 0 | 11/26/13 | 0.0019905625 | -0.0039093661 | 2011 |

La elegida por la regla es la primera, `a=1`, `b=0.5`, `c=0`. No se sustituyó por otra. En euro-pallet el marcador descriptivo es 3/20/2 y en rollcontainer 8/9/8. No hubo fallos. Bucle medio 1.980 s, arranque 1.900 s, captura 0.039 s, auditoría y escritura 5.913 s, pared de proceso 4.652 s.

## Puerta

Aplicada solo a `a1_b0.5_c0`:

- A. Media pareada 0.0010785781, por debajo de 0.005. No cumple.
- B. Media pareada euro-pallet -0.0000514063. No cumple.
- C. Media pareada rollcontainer 0.0022085625. Cumple.

## Decisión

Esta cuadrícula y esta configuración quedan abandonadas según la regla congelada.

## Hashes del código congelado

| Archivo | SHA256 |
| --- | --- |
| `paper/tools/compact_selector.py` | `7d02d22ade3b41b9336e1e03961c9f15851bfbe6e47cd87614eeb592eb5a9efe` |
| `paper/tools/compact_study.py` | `93409b31b093702e80c43da4fe6030cb3913707493756f1df9296c37326af476` |
| `paper/tools/compact_worker.py` | `eb8f235e158fa71f322693bef87c3202fa35aade1140d57423d0c13d9083df7a` |
| `paper/tools/run_compact_calibration.py` | `7aa8bd86d586b1e05f6d5e8fc5bd9bb1b12dcca341f36145b23da3607f2c2464` |
| `policies.py` | `089e1246193285f05241c4729392e7ce3ce8d4cd62a6e15645ba9990e05fe581` |
| `session.py` | `a04d09780eca1d9bae6ef78387299ba13cf7f532f9bb0f8735f8fcf3972cb71c` |
| `loop.py` | `59f66757d6d91acf5f36f01af343ac50a639e656943438f282989ba79d1cb6a8` |

Producción no cambió. Esas tres últimas rutas conservan el hash ya publicado.
