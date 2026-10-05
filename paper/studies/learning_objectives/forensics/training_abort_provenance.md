"""Procedencia del intento de entrenamiento abortado vs campaña válida.

Evidencia de código (run_learning_train.py) y de forensics/training_abort_model_spec_hash/.
"""

from __future__ import annotations

# Orden en run_learning_train.main (HEAD 468ff51 / abortado 2176460 mismo orden):
# 1) comprobar output ausente
# 2) verify_frozen_artifacts  <-- aborto aquí (línea ~81)
# 3) verify_labeling_output
# 4) output.mkdir + carpetas seed/arm
# 5) runtime_document + training_manifest (written_before_fit)
# 6) load_train_states
# 7) run_seed_arms (forward/backward/Adam + checkpoints)
#
# El traceback del aborto muestra RuntimeError en verify_frozen_artifacts
# por hash de tools/model_spec.py. No hay learning_models/ de ese intento.
# training_stdout del aborto vacío de JSON de campaña.
# Conclusión demostrada: solo validación de hashes; sin carga de datos,
# sin forward/backward/Adam, sin pesos guardados. Métricas de entrenamiento: no.
