# 16 — Intento 02 de recuperación (interrumpido)

HEAD de ejecución: `f0ad0ef8cb633e72eac28cc791d0ea87eb7938d7`
(publicado: `research: make label recovery durable and preserve interrupted attempt`).

## Hechos

- Intento 02 lanzado una vez tras el push; **no relanzado** tras la interrupción.
- Causa y código de salida: **desconocidos** (stdout/stderr del wrapper vacíos; sin `labeling_summary.json`).
- `progress.status=running` al detenerse; última escritura ≈ 11:58:41 (lanzamiento ≈ 11:40:05).
- Span de artefactos intento 02 ≈ **1115.9 s**.
- Suma de `wall_seconds` de pedidos nuevos en progress ≈ **1108.0 s** (tiempo registrado de esos pedidos; no cota demostrada del wall total del proceso).

## Cobertura al detenerse

| Clase | N |
| --- | ---: |
| Pedidos con `result` válido (excl. `.staging_*`) | 46 |
| Referenciados readonly desde intento 01 | 12 |
| Nuevos ejecutados | 34 (incl. repetición inevitable `00108806`) |
| Pendientes registrados | 26 (2 train + 24 development) |
| Test | 0 |
| Preflight reusado (claves únicas globales) | 16 |
| Desajustes $Q_{\mathrm{hat}}$ vs `recomputed_u_geom` | 0 |
| Claves duplicadas (sin staging) | 0 |
| Integridad contenido en los 46 | reusable_valid |

No se declara `completed`. Normalización final **no** ajustada (train incompleto; development vacío). Provisional del intento 01 **no** usada.

Quedan directorios `.staging_*` residuales del ejecutor seguro; no son etiquetas.

## Señal descriptiva (solo 46 train; no hallazgo principal)

Denominadores: pares = todas las alternativas (incluye Greedy); ventajas = solo no-Greedy.

| Split/target | Órdenes | Estados empatados / con par estricto | Adv $+ / 0 / -$ | Mejor margen mediana |
| --- | ---: | --- | --- | ---: |
| train/euro-pallet | 22 | 51 / 37 | 33 / 173 / 49 | 0 |
| train/rollcontainer | 24 | 21 / 75 | 75 / 113 / 85 | 0 |

No es mejora online.

## Decisión

`bloqueado_por_integridad_o_cobertura`
