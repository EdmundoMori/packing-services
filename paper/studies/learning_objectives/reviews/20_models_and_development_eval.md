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
