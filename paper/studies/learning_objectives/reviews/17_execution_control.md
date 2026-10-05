# 17 — Control de ejecución persistente (pre-intento 03)

HEAD: `f0ad0ef8cb633e72eac28cc791d0ea87eb7938d7`.
Sin continuaciones reales nuevas. Sin intento 03.

## Problemas comprobados

| Hecho | Evidencia |
| --- | --- |
| Intentos 01 y 02 dejaron `progress=running` sin summary | árboles `learning_labels*`, forenses |
| stdout/stderr/`time -v` del intento 02 vacíos | `forensics/attempt_02_*.log` tamaño 0 |
| Lanzador previo acoplado a la sesión de la herramienta | pipes + proceso en foreground/background de Cursor |
| Mecanismo original de kill **no recuperable** con los registros | causa/exit desconocidos |
| Ningún proceso de etiquetado vivo ahora | `pgrep` vacío |
| 46 pedidos content-verified reutilizables | reconciliación; no solo progress |
| Staging: 34 duplicados de finales OK; 1 incompleto sin result | no auto-promover |

## Conteos mutuamente excluyentes (46)

| Categoría | N |
| --- | ---: |
| Referenciados readonly desde intento 01 | 12 |
| Nuevos del intento 02 (excl. repetición) | 33 |
| Repetición inevitable `00108806` | 1 |
| **Total** | **46** |

Nota: el “34 nuevos” previo incluía la repetición (33+1).

Pendientes: **26** = 2 train + 24 development (coinciden con progress y con manifiesto − done).

## Causa

Sigue **desconocida**. Este trabajo es protección operativa, no atribución a Cursor/sandbox/OOM/señal.

## Mecanismo nuevo

- `tools/labeling_runctl.py`: start/status/stop; doble fork + `setsid`; logs en archivos; heartbeat/`run_state` atómicos; flock + verificación PID+identidad; sin auto-restart.
- `tools/labeling_budget.py`: regla contable acumulada.
- `tools/synthetic_labeling_worker.py` + `tests/test_labeling_runctl.py`: supervivencia tras salida del lanzador, duplicados, PID obsoleto, exit ≠0, SIGTERM, muerto sin cierre.
- Plan (no ejecutado): `attempt_03_plan.json` — reutilizar 46; ejecutar 26 pendientes.

### Presupuesto para el próximo deadline

`accounted = max(reg01, span01) + 120 + max(reg02_new, span02) ≈ 336.75 + 1115.90 ≈ 1452.64 s`.
Restan ≈ **12047 s** de 13500. Preflight separado. Reloj **no** se reinicia con un proceso nuevo. Spans ≈ aproximaciones (no pared exacta).

## Comandos futuros (worker cableado en review 18)

```bash
# estado / procesos
.venv/bin/python tools/labeling_runctl.py status \
  --run-dir .../runs/attempt_03 \
  --identity-token run_learning_labels_attempt03.py

# lanzar intento 03
.venv/bin/python tools/labeling_runctl.py start \
  --run-dir .../runs/attempt_03 \
  --run-id attempt03-$(date -u +%Y%m%dT%H%M%SZ) \
  --attempt-id attempt_03_persistent_recovery \
  --identity-token run_learning_labels_recover.py \
  -- --absolute-python -u --absolute-worker ...

# parada segura
.venv/bin/python tools/labeling_runctl.py stop \
  --run-dir .../runs/attempt_03 \
  --identity-token run_learning_labels_recover.py
```

## Limitaciones

- SIGKILL / crash de host no capturables.
- Worker de recuperación real con checkpoint 46+26 aún no se ejecutó (solo plan + lanzador).
- No garantiza ausencia de toda interrupción externa.

## Decisión

`listo_para_publicar_y_autorizar_recuperacion`
