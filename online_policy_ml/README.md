# Política online aprendida

Subproyecto de entrenamiento e inferencia para `packing_mode=online`.
El execute de packing-services **solo carga** checkpoints.

**Fuente de verdad del cierre:** [`docs/informe_cierre_rl_online.md`](docs/informe_cierre_rl_online.md).

`versions/` es archivo de campañas (v1 imitación; v2 recetas PPO no promocionadas). No se ejecuta desde ahí.

---

## Estado (2026-09-15)

- Default de API: `artifacts/models/mlp_v1_p1s1_ppo.pt` (`policy=rl`, p=1 s=1). Pesos = actor BC (`best_epoch=0`).
- Holdout n=5: **empate** con `online_3d_bpp_heuristic` (Δ −0.0014, IC95 cruza 0).
- Multi-palé: first-fit `07` 30→24 palés; execute `08` iguala. `consolidate` si hay 2+ contenedores.
- Vs PCT (Zhao ICLR 2022) en `00100408`, bin cerrado 2000 mm: **supera** por factibilidad (hn 1.97 m vs 2.105 m publicado). No es ranking BED-BPP ni Uti. Table 1.

---

## Invariantes

Encoder v1 (`FEATURE_VERSION=1`, `FEATURE_DIM=35`), loader `mlp_v1`, bucle `run_online_loop`, holdout `00100001`–`00100004` y `00100408` nunca en train, europalé 1200×800×2000 mm, offline y catálogo intocados.

---

## Checkpoints y API

| Uso | Ruta | Régimen |
|-----|------|---------|
| Default (RL / PPO) | `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` | p=1, s=1 |
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
