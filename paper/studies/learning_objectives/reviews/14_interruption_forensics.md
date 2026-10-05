# 14 — Forense de interrupción y plan de recuperación

HEAD: `16d2aee819f1776629ceb6a5e2eef27ec42353d5`.
No se ejecutaron nuevas continuaciones ni entrenamiento.

## Causa

| Tipo | Contenido |
| --- | --- |
| **Hechos** | Un único intento escribió `learning_labels/` (~11:14:58–11:18:35). El proceso ya no existe. No hay `labeling_summary.json` ni `runtime_error.json`. `progress.status=running`. Once JSON de tamaño 0, todos bajo `orders/00108806/`. Doce `result.json` válidos. Archivos del intento con propietario root (ejecución bajo sandbox/herramienta). Logs del wrapper `/tmp/lo_label_run` no conservados. `dmesg` accesible no aportó líneas OOM utilizables en este entorno. |
| **Hechos de código** | Persistencia original = `Path.write_text` (truncate in-place). Orden: capturas/estado por choice → `result.json` → return → `progress.json`. El progreso **no** se actualiza antes del return de `label_order`. |
| **Hipótesis principal** | Terminación abrupta no capturable (p. ej. SIGKILL del arnés/sandbox al cerrar el job en background) durante o justo después de escrituras no atómicas. El truncate de `open('w')` puede quedar durable mientras los bytes posteriores no; o el árbol se sincroniza de forma parcial. |
| **Hipótesis descartadas / no apoyadas** | OOM: **no** hay registro que lo respalde (código de salida desconocido ≠ OOM). Excepción Python controlada: no hay `runtime_error.json`. Wall-clock del cupo 13500 s: no plausible (~205 s transcurridos). |
| **Causa no recuperable con certeza** | Señal exacta y código de salida del proceso hijo **desconocidos** (logs del lanzador perdidos). |

### Cómo pudo existir `progress=ok` para `00108806` con `result.json` vacío

1. En memoria, el pedido pudo completarse (`n_states=4`, `wall_seconds≈10.7` aparecen en `progress`).
2. En disco, `choice_0` y `choice_10` quedaron con JSON legibles; `choice_21`, `choice_31` y `result.json` quedaron en tamaño 0 (truncate sin contenido validable).
3. El código solo añade el pedido a `progress` **después** de que `label_order` retorna tras llamar a `write_text(result.json)`. Por tanto, o bien Python consideró terminada la escritura mientras la durabilidad del contenido falló bajo kill/sandbox, o bien hubo pérdida parcial de páginas sucias tras un cierre abrupto del entorno de ejecución.
4. **Conclusión operativa:** `progress` no es fuente de verdad. La integridad se decide por contenido + hashes.

## Integridad recuperable

Inventario: `learning_labels/_forensics/inventory_before_correction.json` (269 archivos; 11 vacíos; 0 JSON no vacíos ilegibles). Originales **no** modificados.

| Clase | Pedidos | Uso |
| --- | ---: | --- |
| Continuaciones/pedidos válidos reutilizables | **12** | reutilizar sin reejecutar |
| Corrupto / incompleto en disco | **1** (`00108806`) | no válido como etiqueta de pedido; `choice_0`/`choice_10` solo referencia parcial |
| Nunca ejecutados | **59** | trabajo pendiente en orden de manifiesto |
| Development | **0** etiquetados | pendiente |
| Test | excluido | no ejecutar |

Reauditoría sin packing: `learning_labels/_forensics/reaudit_without_packing.json` — 12/12 reutilizables; 16 `preflight_reused` únicas; 0 desajustes `q_hat` vs `recomputed_u_geom` en filas íntegras.

Normalización provisional (184 filas / 12 pedidos): **no utilizable para entrenamiento** de la campaña completa.

### Denominadores de señal (no son hallazgos principales)

- Estados empatados / con par estricto: sobre **estados** etiquetados íntegros.
- Pares estrictos/empatados: pares no ordenados entre **todas** las alternativas del estado (**incluye Greedy**).
- Ventaja $+ / 0 / -$ vs Greedy: solo alternativas **no Greedy**; denominador = esas alternativas con $Q$ finito (euro-pallet 32; rollcontainer 104).
- Mejor margen: un valor por estado = $\max_i (Q_i - Q_{\mathrm{Greedy}})$ sobre no-Greedy.

## Cambio operativo

Módulos nuevos (no alteran `protocol_frozen`, `sample_manifest`, preflight ni `losses.py`):

| Módulo | Rol |
| --- | --- |
| `tools/labeling_io.py` | JSON atómico (temp+fsync+validar+replace); handlers SIGTERM/SIGINT |
| `tools/labeling_integrity.py` | Verificación por contenido/hashes; conflicto progress vs disco |
| `tools/labeling_campaign_safe.py` | Progreso solo tras persistir+validar; manifiesto de intento/cierre |
| `tools/labeling_recovery.py` | Plan de recuperación |
| `tools/run_learning_labels_recover.py` | CLI plan-only; `--execute-recovery` rechazado aquí |

`labeling_campaign.py` original se conserva (evidencia del intento 01). SIGKILL/SIGSTOP/power-loss **no** capturables; no se promete durabilidad absoluta.

Pruebas: `tests/test_labeling_recovery.py` (interrupción simulada, preservación de archivo previo, progress vs corrupto, pendiente, presupuesto acumulado, test excluido).

## Plan de recuperación (no ejecutado)

Artefacto: `learning_labels_recovery_plan.json` y `_forensics/recovery_plan.json`.

- Directorio nuevo `learning_labels_recovery/` (aún inexistente).
- Referenciar los 12 pedidos verificados; registrar procedencia.
- No reejecutar continuaciones completas verificadas.
- Ejecutar pendientes en orden de manifiesto **sin** selección por señal.
- `00108806`: reejecución inevitable del pedido (etiquetas no comprobables a nivel pedido); capturas parciales solo como referencia.
- Presupuesto: cargar de forma conservadora **214.80055754699697 s** (suma de paredes en `progress`, incluye la reclamación del corrupto) sobre 13500; restan ≈ **13285.2 s**. Preflight **35.121554053999716 s** separado, ya contado una vez.
- No es una “campaña de un solo intento”: es **continuación/recuperación** del intento 01 interrumpido.

## Decisión

`recuperacion_operativa_viable`

No autoriza ni ejecuta la recuperación en este paso.
