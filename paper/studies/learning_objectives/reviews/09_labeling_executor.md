# 09 — Ejecutor de etiquetado learning_objectives

HEAD de partida: `ee1e6b925a8cb539139bd00958de9d6984937fc3`.
No se ejecutó la campaña completa de etiquetas. No hubo entrenamiento, desarrollo ni test.
No se modificó el protocolo congelado, el manifiesto de muestras ni el preflight publicado.

## Contratos comprobados

| Artefacto | Valor |
| --- | --- |
| SHA256 completo `protocol_frozen.json` | `385f25c60e92dc936c02363b7152031d20b2728db13c2f9d4911446930b83b05` |
| Digest interno | `a5959cb602ee00dfcb56b531de02d6e9d1dd618c42a54b7aa1e0d2214e6ad155` |
| `sample_manifest.json` | `782eb3abe10163270db8dec9594d099ea936e4491747278bee1b06a73accda62` |

Hashes de dataset y código del protocolo contrastados. Sin ambigüedad sustantiva que bloquee el ejecutor.

## Componentes

| Módulo | Rol |
| --- | --- |
| `tools/labeling_contracts.py` | preflight estático, hashes, manifiesto de ejecución |
| `tools/labeling_states.py` | estados Greedy + cuantiles + S vía `pipeline` |
| `tools/labeling_reuse.py` | reutilización exacta de las 16 continuaciones publicadas |
| `tools/labeling_campaign.py` | restauración, continuación, captura, auditoría, reloj |
| `tools/labeling_verify.py` | normalización train-only y verificación independiente |
| `tools/run_learning_labels.py` | CLI con rutas absolutas |

Reutiliza: `candidate_support` / `pipeline`, `quantile_sampling`, `continue_from`, `score_solution`, `encode_candidate`, `recompute_u`, `fit_normalization`.

## Reutilización del preflight

Pedidos `00105883` y `00104801`. Antes de reusar: dataset, digest de protocolo, hashes de código, ítem actual, sufijo, S, acción, captura y auditoría. Si falla, la etapa se detiene. Evidencia publicada solo referenciada. Cada continuación cuenta una sola vez.

Presupuesto:
- preflight: `35.121554053999716` s, fase `preflight`, una sola vez en el techo global 28800;
- etiquetado nuevo: cupo 13500 s (sin descontar el preflight de ese cupo).

## Cobertura y fallos

Distingue: menos estados elegibles; menos de cuatro geometrías; timeout (`q_hat=null`); captura/geometría inválida; discrepancia de entrada; no ejecutado por presupuesto; error interno del evaluador (`incomplete`). No reintenta ni sustituye. Estados incompletos se conservan y no entran en normalización/entrenamiento.

## Comando futuro (no lanzado aquí)

```bash
/home/edmundo/packing-services/.venv/bin/python \
  /home/edmundo/packing-services/paper/studies/learning_objectives/tools/run_learning_labels.py \
  --study-dir /home/edmundo/packing-services/paper/studies/learning_objectives \
  --output /home/edmundo/packing-services/paper/studies/learning_objectives/learning_labels
```

Carpeta de salida propuesta: `paper/studies/learning_objectives/learning_labels/` (debe no existir).

Preflight estático verificado desde `/tmp` con `--static-only`.

## Decisión

`listo_para_publicar_ejecutor`
