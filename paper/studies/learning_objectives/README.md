# learning_objectives

Etiquetas verificadas. 9 modelos publicados (`2b4f5e9`).

## Intento development fallido (conservado)
- run_id `dev_eval_2b4f5e9a8f7c_20261005T160901Z`
- 240/240 crash pre-packing (`Path.resolve` del intérprete venv)
- 0 capturas / 0 auditorías; summary y gate originales intactos
- Interpretación: `evaluacion_incompleta_por_fallo_del_arnes`
- Los ceros **no** son resultados de packing

## Corrección de arnés
- `worker_env.py` + preflight subprocess; `absolute()` no `resolve()`
- Puerta científica no aplicable sin capturas auditadas
- Revisión: `reviews/21_venv_workers_and_invalid_gates.md`
