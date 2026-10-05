# 20 — Modelos emparejados y evaluador de development

## Procedencia del aborto

Intento bajo HEAD `2176460` falló en `verify_frozen_artifacts` (hash de `model_spec.py`).
Evidencia: `forensics/training_abort_provenance.json`. **Solo validación**; sin datos,
forward, Adam ni pesos.

Entrenamiento válido: HEAD `468ff51` → `learning_models/` (9× época 40, init nueva).

## Evaluador

- `tools/run_development_eval.py` + `episode_worker.py` + `actor_policy_s.py`
- 240 casos: 24 Greedy + 216 actores (S-constrained)
- 2 workers; Torch 1+1 hilos; timeout 300 s / caso; cupo 3600 s
- Puerta congelada del protocolo (no exige superar Greedy)

## Resultado de la ejecución autorizada

- run_id `dev_eval_2b4f5e9a8f7c_20261005T160901Z`
- 240/240 crash antes de packing (`torch` ausente en worker por `Path.resolve` del intérprete venv)
- 0 capturas / 0 auditorías
- Summary gate string: `no_avanzar_con_esta_configuracion` (contrastes 0)
- Decisión científica: **`evaluacion_incompleta`**
- Sin relanzamiento automático (norma del prompt)
