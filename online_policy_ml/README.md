# Política online aprendida

Subproyecto de entrenamiento e inferencia para `packing_mode=online`.
El execute de packing-services **solo carga** checkpoints.

**Informe histórico de cierre (2026-09-15):** [`docs/informe_cierre_rl_online.md`](docs/informe_cierre_rl_online.md).
**Errata documental vigente (C01):** [`../paper/reviews/C01_current_claims_correction.md`](../paper/reviews/C01_current_claims_correction.md).

`versions/` es archivo de campañas (v1 imitación; v2 recetas PPO no promocionadas). No se ejecuta desde ahí.

---

## Estado vigente (interpretación C01)

- Default de API: archivo `artifacts/models/mlp_v1_p1s1_ppo.pt`, opción `policy=rl`, régimen p=1 s=1. Los **tensores vigentes coinciden** con el actor BC (`mlp_v1_p1s1.pt`); el informe de la corrida registra `best_epoch=0`, que **no** demuestra una mejora obtenida mediante PPO. El nombre del archivo y de la opción API no equivalen al método que produjo los pesos seleccionados ([`paper/reviews/06_actor_provenance.md`](../paper/reviews/06_actor_provenance.md)).
- Holdout de producto n=5 (`06_evaluar_holdout.json`): la diferencia media de utilización respecto al heurístico online es −0.0014 con IC95 que **incluye cero**. Eso es un resultado **no concluyente** sobre el signo de la diferencia; **no** establece empate estadístico, igualdad ni equivalencia.
- Evaluación independiente de 200 pedidos (protocolo geométrico 07 / paso 08): media de delta ≈ −0.00059; IC bootstrap 95 % incluye cero; clasificación predefinida `no_concluyente`. Distinta del holdout n=5 y de cualquier comparación PCT. Tampoco afirma equivalencia ([`paper/reviews/08_independent_evaluation_run.md`](../paper/reviews/08_independent_evaluation_run.md)).
- Caso histórico `00100408` frente a un dato publicado de transferencia PCT (Kagerer): se inspeccionó un caso; la captura interna cumple las comprobaciones geométricas auditadas en ese flujo; el dato publicado de Kagerer corresponde a una transferencia de PCT; aplicar nuestro límite de altura **no** constituye una comparación homologada con el protocolo ICLR ni una evaluación completa BED-BPP. **No se demostró superioridad frente a PCT.** Nuestro MLP **no** es una reproducción de PCT.
- Multi-palé: first-fit `07` 30→24 palés; execute `08` iguala. `consolidate` si hay 2+ contenedores.

---

## Invariantes

Encoder v1 (`FEATURE_VERSION=1`, `FEATURE_DIM=35`), loader `mlp_v1`, bucle `run_online_loop`, holdout `00100001`–`00100004` y `00100408` nunca en train, europalé 1200×800×2000 mm, offline y catálogo intocados.

---

## Checkpoints y API

| Uso | Ruta | Régimen |
|-----|------|---------|
| Default (opción API `policy=rl`; pesos BC vigentes) | `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` | p=1, s=1 |
| Cinta | `online_policy_ml/artifacts/models/mlp_v1_p3s2.pt` | p=3, s=2 |
| Sin PyTorch | `online_policy_ml/artifacts/models/linear_v1.json` | p=1, s=1 |
| Humo (no producción) | `examples/online_policy_linear_v1.json` | — |

```text
POST /api/v1/algorithms/drl_policy_3d_bpp/execute
POST /api/v1/online/learned/execute
POST /api/v1/online/rl/execute
```

MLP: `pip install 'packing-services[torch]'`.

Notebooks de la corrida: [`notebooks/README.md`](notebooks/README.md). Índice de docs: [`docs/README.md`](docs/README.md).
