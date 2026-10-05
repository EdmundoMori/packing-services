# learning_objectives

Protocolo congelado. Intento 01 de etiquetado interrumpido (causa/exit desconocidos).
Capa de recuperación durable implementada; intento 02 **no** forma parte del
commit de publicación de la capa hasta ejecutarse tras el push.

- Forense: [`reviews/14_interruption_forensics.md`](reviews/14_interruption_forensics.md)
- Plan: [`learning_labels_recovery_plan.json`](learning_labels_recovery_plan.json)
- Manifiesto capa: [`implementation_manifest_recovery.json`](implementation_manifest_recovery.json)
- CLI: `tools/run_learning_labels_recover.py` (`--write-plan-only` | `--execute-recovery`)
- Evidencia intento 01 (local, no indexada en el commit de la capa): `learning_labels/`

Entrenamiento / desarrollo de actores / test: false.
