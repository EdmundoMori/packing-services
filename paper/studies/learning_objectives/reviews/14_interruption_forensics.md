# 14 — Forense de interrupción y plan de recuperación

HEAD base: `16d2aee819f1776629ceb6a5e2eef27ec42353d5`.

## Causa

| Tipo | Contenido |
| --- | --- |
| **Causa** | **Desconocida** |
| **Código de salida** | **Desconocido** (logs del lanzador no conservados) |
| **Hechos comprobados** | Escritura no atómica (`Path.write_text`) en el ejecutor del intento 01; once archivos JSON vacíos bajo `orders/00108806/`; inconsistencia `progress` (status ok) frente a contenido vacío; mecanismo exacto de corrupción **no establecido** |
| **No demostrado** | SIGKILL, kill de sandbox, OOM, ni “falta de durabilidad” como causa probada. La hipótesis de durabilidad **no explica por sí sola** el incidente y no se presenta como causa |

## Tiempo registrado (no cota demostrada del wall total)

| Cantidad | Valor | Interpretación |
| --- | ---: | --- |
| Suma `wall_seconds` en `progress.orders_done` | 214.80055754699697 s | Tiempo **registrado** por pedido (secuencial por diseño); incluye la reclamación de `00108806` |
| Span artefactos lanzador | ≈ 216.746 s | `mtime(progress.json)−mtime(execution_manifest.json)` — cota verificable entre artefactos, no precisión de proceso |
| Reserva operativa | 120 s | Dentro del cupo 13500; no amplía presupuesto |
| Contabilizado para deadline intento 02 | max(registrado, span)+reserva ≈ 336.746 s | |
| Preflight | 35.121554053999716 s | Fase separada, una sola vez |

Fases cubiertas por el registrado: trabajo por pedido reportado en progress. Inciertas/ausentes: arranque/static_preflight del intento 01, huecos entre pedidos, teardown. No hay evidencia de paredes concurrentes (diseño secuencial).

## Integridad recuperable

- 12 pedidos reutilizables por contenido.
- 1 corrupto (`00108806`): `choice_0`/`choice_10` comprobables como parciales; `choice_21`/`choice_31`/result no comprobables; repetición inevitable por evidencia insuficiente, no por retorno.
- 59 pendientes **registrados** en `progress.pending_order_ids` (no se etiquetan genéricamente como “nunca ejecutado” sin más).
- Inventario: `forensics/inventory_before_correction.json`.

## Ejecutor

`--execute-recovery` estuvo rechazado de forma **deliberada** en el paso solo-plan; la ejecución no estaba cableada en el CLI. Ahora `run_learning_labels_recover.py --execute-recovery` implementa el intento 02 vía `run_recovery_attempt` (referencias readonly + packing pendiente).

## Decisión de diseño

`recuperacion_operativa_viable` (la autorización de ejecución es un paso posterior/publicado).
