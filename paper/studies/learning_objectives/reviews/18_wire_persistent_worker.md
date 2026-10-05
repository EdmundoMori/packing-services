# 18 — Worker real cableado al lanzador persistente

HEAD base: `f0ad0ef8cb633e72eac28cc791d0ea87eb7938d7`.

## Cambios

| Pieza | Rol |
| --- | --- |
| `tools/labeling_runctl.py` | Lanzador desacoplado (doble fork, flock, PID+identidad, sin auto-restart) |
| `tools/run_learning_labels_attempt03.py` | Worker real: hashes antes de packing; 46 referencias; 26 pendientes |
| `tools/labeling_campaign_safe.run_attempt03_recovery` | Lógica de campaña attempt 03 + heartbeat |
| `tools/labeling_budget.py` | `max(reg01,span01)+120+max(reg02,span02)`; preflight separado |
| `attempt_03_plan.json` | 46 reutilizables + 26 pendientes; staging excluido |

## Prueba de integración

`tests/test_attempt03_integration.py` ejercita **runctl + worker real** con:

- evidencia sintética reutilizable;
- pendiente sintético (`--mock-packing`);
- auditor real (`verify_order_artifacts`);
- supervivencia tras salida del lanzador;
- bloqueo de duplicados;
- rechazo de split test;
- presupuesto heredado.

No basta con `synthetic_labeling_worker.py` solo.

## Límites

- Salida de proceso ≠ campaña completa.
- SIGKILL / caída del host pueden impedir cierre normal.
- Protocolo congelado no modificado.
- Sin entrenamiento / actores / test.
