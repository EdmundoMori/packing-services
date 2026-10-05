# 19 — Cierre de verificación de etiquetas y ejecutor de entrenamiento

## Procedencia del exit 1 (intento 03)

| Elemento | Valor |
| --- | --- |
| Proceso original | exit **1** (no reescrito) |
| `labeling_summary.json` | `completed` (72 pedidos) |
| Verificador en proceso | glob `*/result.json` (incl. `.staging_*`) → `issues_found` |
| Hash verificador original (HEAD `1240617`) | `f7059eeab9bc8f2ca49f9bec9889a46e0f6924b593336f3eab1a76453dfec82d` |
| Verificador corregido | `manifest_keyed_v2` (claves de manifiesto; staging ≠ final) |
| Re-verificación posterior | `verified` / `ready_for_training=true` (artefacto distinto) |

Narrativa demostrada: **generación completa → cierre con fallo del verificador → validación posterior aceptada**.

## Entrenamiento preparado

- `tools/run_learning_train.py` + `training_loop.py` + `training_data.py`
- 3 brazos × semillas 11/23/37; 40 épocas; 1 Adam/época; permutaciones compartidas
- Presupuesto 1800 s; sin episodios ni test
- Pruebas sintéticas en `tests/test_training_executor.py`
