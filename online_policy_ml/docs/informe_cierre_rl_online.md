# Informe de cierre del subproyecto RL online

> **Aviso de interpretación (C01, 2026-10-06).** Este documento es un **informe histórico**
> (fecha 2026-09-15) y se conserva sin reescribir su cuerpo. La lectura vigente de
> «empate estadístico», «supera PCT» y mejora PPO está en la errata
> [`paper/reviews/C01_current_claims_correction.md`](../../paper/reviews/C01_current_claims_correction.md)
> (holdout §3 aquí; PCT §4–5 aquí + protocolos Z/K/P; pesos BC / `best_epoch=0` en
> [`06_actor_provenance.md`](../../paper/reviews/06_actor_provenance.md); evaluación de 200
> pedidos en [`08_independent_evaluation_run.md`](../../paper/reviews/08_independent_evaluation_run.md)).
> La corrección documental **no** altera JSON, checkpoints ni resultados de esta corrida.

**Versión detallada (Word, con índice):** [`Informe_cierre_RL_online.docx`](Informe_cierre_RL_online.docx).

**Fecha:** 2026-09-15.
**Qué cierra:** el ciclo de construcción de una política aprendida sobre encoder v1 y `run_online_loop`, su `.pt` de API, y la comparación puntual con PCT (Zhao et al., ICLR 2022) en BED-BPP.
**Qué no cierra:** el producto packing-services. El execute sigue existiendo. Offline y el catálogo de 31 motores no se tocaron.

Fuente de las cifras: JSON de esta corrida (`artifacts/reports/06_evaluar_holdout.json`, sellos `07`/`08` v3, `09_homologar_pct.json`, `10_comparar_pct.json`). No se copian informes PPO de septiembre anteriores al relanzamiento.

---

## 1. Objetivo

Se construyó **otro motor online**, no un packer óptimo. La red solo puntúa candidatas ya legales del bucle EP. El default de API es `mlp_v1_p1s1_ppo.pt` (`policy=rl`, p=1 s=1) porque es la única política aprendida expuesta, no porque superara al heurístico.

Invariantes que se mantuvieron: `FEATURE_VERSION=1`, `FEATURE_DIM=35`, loader `Linear(35,64)→ReLU→Linear(64,1)`, holdout `00100001`–`00100004` y `00100408` nunca en train/tune, europalé 1200×800×2000 mm, sin algoritmo 32.

---

## 2. Camino

Una primera pista usó el maestro `privileged_volume_ep`: etiqueta tautológica (regla cerrada ~100 %). El accuracy de imitación no medía empaquetar. Se sustituyó por `receding_horizon_ep`.

Esta corrida (decisión 2026-09-14, semilla 42, holdout bloqueado) relanzó `01`–`05` y cerró producto con `06`–`08`. Homologación y comparación vs PCT fueron las fases 3 y 4 (`09`, `10`), no el cubo de val/holdout.

`versions/v1` y `versions/v2` son archivo (imitación histórica; recetas PPO 3 y 4 no promocionadas). No se ejecutan.

---

## 3. Método de producción

El PPO de esta corrida eligió `best_epoch=0`: el actor exportado es el de imitación BC (`mlp_v1_p1s1.pt`). Val_util bajó en los epochs PPO (0.6875 → 0.662). STEP y shaping no se promocionan. Cinta: `mlp_v1_p3s2.pt` (p=3 s=2), no es el default.

**Holdout de producto** (`06_evaluar_holdout.json`, n=5, `volume_utilization` de producto, un palé):

| Motor | Media | Ítems (suma) |
|-------|-------|----------------|
| Heurístico | 0.6682 | 187 |
| PPO `mlp_v1_p1s1_ppo.pt` | 0.6668 | 186 |

Δ(PPO − H) = **−0.0014**, IC95 **[−0.025, +0.019]**, cruza 0: **empate**. No se declara victoria.

**Multi-palé** (sello v3, holdout, 2 contenedores, sin reentrenar): first-fit `07` cierra 30→24 palés (util 0.373 → 0.499, 0 ítems fuera). El execute `08` iguala al `07` consolidado (24 palés, misma util). `consolidate` default si hay 2+ contenedores.

Pytest de contrato en verde (2 skips: el `.pt` ya existía).

---

## 4. Homologación (fase 3)

Zhao, Yu y Xu, ICLR 2022 (PCT) es el marco: online 3D-BPP, un bin **cerrado**, Uti. = volumen contenido / volumen del bin, Num. = ítems contenidos. Kagerer IJRR 2023 corrió ese código en BED-BPP (O3DBP, europalé 120×80×200 cm). No se copian las tablas ICLR en bins 10×10×10.

Pedido fijo a priori: **`00100408`** (holdout; no se entrenó con él). Setting de producto ≈ Zhao Setting 2 + `max_weight`. Un palé, p=1 s=1.

| Lado | Factible | Uti. Zhao | Num. | hn (m) |
|------|----------|-----------|------|--------|
| `mlp_v1_p1s1_ppo.pt` | sí | 0.646376 | 26 | 1.97 |
| PCT (xkpi publicado; plan LFS no materializado) | no | — | — | 2.105 |

PCT publicado: ηutil 0.614, νu=0. Sin packing plan no hay Uti. de PCT *dentro* de 2 m. Si se ignora la contención, el volumen de los 26 ítems empata (~0.646). ηutil Kagerer es otro juez.

---

## 5. Comparación con PCT (fase 4)

Tabla de comparabilidad en `10_comparar_pct.json`. La única columna que **decide** es la factibilidad Zhao (hn ≤ 2 m y cajas dentro). Uti. head-to-head = no.

**Veredicto (un pedido, no ranking BED-BPP, no Σalgo, no Table 1 10×10×10):**

En `00100408`, O3DBP p=1 s=1, bin 1200×800×2000 mm, `mlp_v1_p1s1_ppo.pt` **supera** a PCT porque la solución nuestra es factible y el packing publicado de PCT no (hn 2.105 m). En Zhao una colocación fuera del bin no es solución.

---

## 6. Uso en packing-services

```text
POST /api/v1/algorithms/drl_policy_3d_bpp/execute   # default: mlp_v1_p1s1_ppo.pt, policy=rl, p=1 s=1
POST /api/v1/online/learned/execute
POST /api/v1/online/rl/execute
```

`consolidate` se activa si hay 2+ contenedores (salvo `consolidate=false`). El heurístico `online_3d_bpp_heuristic` sigue siendo alternativa; en holdout empata con el PPO. Cinta: `mlp_v1_p3s2.pt`. Sin torch: `linear_v1.json`. El placeholder `examples/online_policy_linear_v1.json` no es producción.

---

## 7. Qué no se hizo

- `FEATURE_VERSION=2` / heightmap.
- RL desde cero; pesos de PCT/GOPT.
- Submit al leaderboard BED-BPP; Blender / Σalgo.
- N≥20 europalé ni reevaluación del plan LFS de PCT.
- Promocionar STEP o shaping; mezclar p=3 s=2 en el default.
- Declarar gana/empata/pierde vs PCT con el cubo del `06`.

Notebooks `01`–`10` y JSON de `artifacts/` se conservan como corrida. Este informe sustituye la hoja de ruta de cierre y los `eval_*.md` vivos (si existían).
