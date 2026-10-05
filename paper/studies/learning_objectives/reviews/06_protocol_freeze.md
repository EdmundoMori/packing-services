# 06 — Congelación del protocolo learning_objectives

HEAD de trabajo: `904038ff7f495510f1b8f3d398da3e4eb281a406` en `research/paper-online-packing`.
No hubo commit ni push. No se abrieron los 17 pickle históricos. No se modificó producción ni cierres históricos.

## Artefactos

- `protocol_frozen.json` / `protocol_frozen.md` (antecedente: `design_draft.md`)
- `sha256` del protocolo (campo interno): `a5959cb602ee00dfcb56b531de02d6e9d1dd618c42a54b7aa1e0d2214e6ad155`
- `sample_manifest.json`: train 48, desarrollo 24 (full.val); test 100 (full.test)
- `sample_manifest` SHA256: `782eb3abe10163270db8dec9594d099ea936e4491747278bee1b06a73accda62`
- Cadena: `learning-objectives-v1|20261005|{split}|{order_id}`

## Ambigüedades cerradas antes de congelar

- S = `greedy_plus_orientation_position_diversity_v1` con pseudocódigo de orientación, Chebyshev, desempates, orden, identidad y `float()`.
- Etiquetado y despliegue llaman a la misma fuente (`pipeline` / `support_api` → `candidate_support`).
- Tres pérdidas con signo «mayor es mejor»; `TIE_COEFFICIENT=1.0`; sin temperatura.
- Exposición positiva vs catálogos de ausencia: estos últimos no vacían full.test.
- Firmas de test: exposición positiva + train/dev seleccionados (sin propagar el bloqueo de todo full.test vía `blocked_val`).

## Autorizaciones

`authorizes_labeling=false`, `authorizes_training=false`, `authorizes_full_campaign=false`.
