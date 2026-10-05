# 21 — Corrección de intérprete venv y rechazo de puertas inválidas

## Causa del intento fallido (`dev_eval_2b4f5e9a8f7c_20261005T160901Z`)

`Path.resolve()` sobre `.venv/bin/python` seguía el symlink a `/usr/bin/python3.10`
y eliminaba `site-packages` de la venv. Los 240 workers crasharon con
`ModuleNotFoundError: torch` **antes de packing**. 0 capturas / 0 auditorías.
El summary original y su gate (`no_avanzar_con_esta_configuracion`) se conservan
intactos; la interpretación independiente es
`evaluacion_incompleta_por_fallo_del_arnes`. Los ceros no son resultados de packing.

## Cambios

- `worker_env.py`: `venv_python` / `preserve_executable` con `absolute()`; preflight
  por subprocess real (executable, prefix, torch, actor, encoder, auditor).
- `run_development_eval.py`: preflight antes de la cuadrícula; aborta como
  fallo de arnés sin inventar 240 fallos de método; discriminantes
  method/harness/evaluator; integridad y puerta no aplicable si no hay
  capturas auditadas; smoke flags; cupo development descuenta intento fallido;
  geometría vía `internal_geometry_valid`.
- `labeling_runctl.py`: argv[0] con `absolute()` (no `resolve()`).
- `episode_worker.py`: Greedy sin importar torch/actor; actor carga torch solo
  en su rama.
- `episode_analysis.py`: `evaluation_integrity`, harness vs método, puerta no
  aplicable ante evaluación inválida.

## Pruebas

`tests/test_worker_env_integration.py` (+ episode_eval, labeling_runctl):
venv enlazada, conservación de entorno, imports worker, preflight fallido,
cero capturas rechaza completitud, método ≠ arnés, puerta no aplicable,
subprocess real greedy+actor con captura/contraste/auditoría.

## Contabilidad

Intento fallido: 22.538368225097656 s del cupo development 3600 s.
No se reinicia el reloj. Protocolo congelado intacto.
