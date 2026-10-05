# 13 — Generación de etiquetas learning_objectives

HEAD de ejecución: `16d2aee819f1776629ceb6a5e2eef27ec42353d5`.
Rama: `research/paper-online-packing`.
Intentos: **1**. No se relanzó. No se modificó el ejecutor ni el protocolo.

## Precomprobación

| Comprobación | Resultado |
| --- | --- |
| SHA256 `protocol_frozen.json` | `385f25c60e92dc936c02363b7152031d20b2728db13c2f9d4911446930b83b05` |
| Digest interno | `a5959cb602ee00dfcb56b531de02d6e9d1dd618c42a54b7aa1e0d2214e6ad155` |
| SHA256 `sample_manifest.json` | `782eb3abe10163270db8dec9594d099ea936e4491747278bee1b06a73accda62` |
| Train / development | 48 / 24 (24+24 / 12+12 por target) |
| Test en orden de ejecución | ausente |
| `learning_labels/` antes de lanzar | inexistente |
| Continuaciones preflight | 16 |
| Cupo etiquetado nuevo | 13500 s |
| Preflight contabilizado | 35.121554053999716 s, una vez |
| Pruebas + `--static-only` | OK, sin packing en static |

## Ejecución

```bash
/home/edmundo/packing-services/.venv/bin/python \
  /home/edmundo/packing-services/paper/studies/learning_objectives/tools/run_learning_labels.py \
  --study-dir /home/edmundo/packing-services/paper/studies/learning_objectives \
  --output /home/edmundo/packing-services/paper/studies/learning_objectives/learning_labels
```

| Campo | Valor |
| --- | --- |
| Inicio (mtime manifiesto) | 2026-10-05 11:14:58 +02 |
| Inicio trabajo (birth progress) | 2026-10-05 11:15:10 +02 |
| Última escritura progress | 2026-10-05 11:18:35 +02 |
| Fin observado (proceso muerto) | ≤ 2026-10-05 11:21:34 +02 |
| Estado en disco | `progress.status=running` (sin `labeling_summary.json`) |
| Código de salida | desconocido (proceso terminado; logs `/tmp` del wrapper no conservados) |
| Fallo | **después** de trabajo experimental |

## Cobertura (hechos)

Techo contractual: $72\times 4\times 4=1152$ continuaciones. No es cobertura obligatoria.

| Split \| target | Pedidos íntegros | Estados trayectoria (suma $N$) | Estados etiquetados | Candidatas / continuaciones con $Q$ |
| --- | ---: | ---: | ---: | ---: |
| train \| euro-pallet | 3 | 138 | 12 | 44 / 44 |
| train \| rollcontainer | 9 | 296 | 36 | 140 / 140 |
| development \| * | 0 | 0 | 0 | 0 / 0 |
| test | 0 (excluido) | — | — | — |

- Pedidos esperados: 72. Resultados JSON válidos: **12**.
- Pedido `00108806`: marcado `ok` en `progress.json`, pero `result.json` y capturas `choice_21`/`choice_31` están **vacíos** en disco → tratado como corrupto.
- Pendientes: 59 pedidos no ejecutados + integridad rota en uno.
- Reutilización preflight: **16** (`source=preflight_reused`), sin duplicación en alternativas válidas.
- Continuaciones nuevas (válidas): 168. Desconocidos ($Q=\mathrm{null}$): 0 en filas válidas. Pendientes de campaña: el resto del manifiesto.
- Estados con $<4$ geometrías (contrato): 3 euro-pallet + 3 rollcontainer.

## Señal descriptiva (solo 12 pedidos train íntegros)

| Split \| target | Todos empatados | Con par estricto | Pares estrictos / empatados | Alt. vs Greedy $+$ / $0$ / $-$ | Mejor margen (min / mediana / max) |
| --- | ---: | ---: | ---: | ---: | --- |
| train \| euro-pallet | 6 | 6 | 23 / 38 | 0 / 21 / 11 | $-0.091$ / $0$ / $0$ |
| train \| rollcontainer | 5 | 31 | 142 / 63 | 31 / 30 / 43 | $-0.054$ / $0.011$ / $0.154$ |

Límites: no son pedidos independientes; el mejor margen **no** es mejora de una política online; no hay development; la campaña **no** está completa. En euro-pallet no hubo alternativa con ventaja estricta frente a la continuación Greedy del mismo estado en esta muestra parcial. La decisión de continuidad de entrenamiento queda para revisión externa; **no** se entrenó.

## Verificación independiente (sin nuevo packing)

Sobre los 12 `result.json` válidos:

- Claves (pedido, estado, acción) únicas; sin test; hashes de selección alineados al manifiesto.
- $S$: $\le 4$ geometrías; `greedy_in_support=true`; contrato `greedy_plus_orientation_position_diversity_v1`.
- 17 características, nombres y orden = `FEATURE_NAMES`.
- $Q_{\mathrm{hat}}$ vs `recomputed_u_geom`: 0 desajustes.
- Auditorías `audited=true` en alternativas inspeccionadas; capturas coherentes donde el archivo no está vacío.
- Normalización **provisional** solo train (184 filas de 12 pedidos): SHA256 `68bef1e83acb3698d682f30d6fb9289f1199f02eaae91b99b66fa5192fc4fcf8`; columnas con escala 1 por constancia: `item_can_rotate`, `bin_index_n`. **No** es la normalización congelada de campaña completa.

Artefactos: `learning_labels/interruption_record.json`, `independent_verification_partial.json`.

## Tiempos y presupuesto

| Fase | Segundos | Restante de cupo |
| --- | ---: | ---: |
| Preflight (contado 1×) | 35.121554053999716 | (fase separada; cupo preflight 900) |
| Etiquetado nuevo (aprox. mtimes) | ≈ 205 | 13500 − 205 ≈ 13295 |
| Suma paredes de pedidos en progress | 214.80 | — |
| Suma paredes de 12 pedidos válidos | 204.08 | — |
| Global contabilizado aprox. | ≈ 240 | 28800 − 240 ≈ 28560 |

Memoria (`ru_maxrss`): no medida (proceso muerto antes de flushear `/usr/bin/time -v`).
No se declara demostrado el presupuesto de entrenamiento ni de evaluación.

## Decisión

`bloqueado_por_integridad_o_cobertura`

No autoriza entrenamiento. Evidencia parcial conservada. No commit/push en este paso.
