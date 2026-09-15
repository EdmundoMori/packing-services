# PPO v1 — primera versión (congelada)

Instantánea del 13 de septiembre de 2026. No se reescribe. El trabajo nuevo
va a [`../v2/`](../v2/).

## Qué es esta versión

Pipeline `01`–`05` sobre encoder v1 (`FEATURE_DIM=35`) y contrato
`packing-services-online-policy` v1. Maestro `receding_horizon_ep`. Fine-tuning
PPO del actor `mlp_v1_p1s1.pt` (imitación P2O).

## Resultado de producto

Val scale n=20, p=1,s=1 (recompensa densa, 80 train, 2 rollouts):

| Motor | Utilización | Ítems |
|-------|-------------|-------|
| Heurístico | 0.6695 | 41.6 |
| Imitación | 0.6733 | 41.85 |
| PPO | 0.6802 | 42.2 |

PPO vs heurístico: Δ +0.0107, IC95 [−0.004, +0.026] — no significativo.
No se promocionó como default por evidencia estadística. En la plataforma
pasó a ser **la única** política aprendida (se retiró la opción de imitación).

## Contenido

| Carpeta | Qué hay |
|---------|---------|
| `notebooks/` | `01`–`05`, `10`, `_execute.py` (tal como se ejecutaron) |
| `src_ml/` | Código de entrenamiento e evaluación de esta versión |
| `docs/` | Documentación del subproyecto en este corte |
| `artifacts/models/` | `mlp_v1_p1s1.pt`, `mlp_v1_p1s1_ppo.pt`, `mlp_v1_p3s2.pt`, `linear_v1.json` |
| `artifacts/reports/` | `01`–`05` y evals de holdout |
| `data/` | `order_ids.json` y transiciones `.pkl` (sin los JSON BED-BPP) |

Informe canónico del PPO: `artifacts/reports/05_ppo.json`.
