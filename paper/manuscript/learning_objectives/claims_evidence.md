# Claims and evidence (manuscrito learning_objectives / C06)

Estado de campaña: `no_avanzar_con_esta_configuracion`; test **no** ejecutado
(conforme al protocolo; no se propone abrirlo aquí).
Artefacto primario de cifras: `forensics/campaign_closure_verification.json`.
Motor de candidatas en los episodios: EP simplificado en commit `ee9e0ec` (pre-C04).

## Afirmaciones factuales del alcance development

| Afirmación limitada | Evidencia | Tipo / límite |
| --- | --- | --- |
| Protocolo y muestra congelados | `protocol_frozen.json`, `sample_manifest.json` | Factual |
| Encoder de **17** features presentes (nombres/unidades del encoder del estudio) | `counterfactual_ranking/tools/actor_features.py` + `normalization_train.json` | Factual; ≠ encoder producción 35 |
| Normalización **solo train** (`fit_on=train_rows_only`; sin refit dev/test) | `normalization` en protocolo + JSON de fit | Factual |
| Soporte $S$ idéntico en etiquetado y despliegue | protocolo + tools de soporte/actor | Factual |
| $Q_{\mathrm{hat}}$ = continuación Greedy concreta | formulación + etiquetado | Factual; **no** óptimo |
| Pérdidas = fórmulas §4 (RD = adaptación Mandi, no reproducción exacta) | losses hasheados | Factual |
| 9 modelos; 40 Adam full-batch; checkpoint época 40; `seed_selection=false` | `architecture` + `meta.n_optimizer_steps` | Factual; sin selección por resultados |
| Development 240 auditados (24 Greedy + 216 actores) | `learning_development_eval_full/` | Factual; **≠ test** |
| Agregación: semillas dentro del pedido → media entre pedidos | `aggregation` en verificación | Factual; 3 semillas ≠ 3 pedidos |
| Pref−class ≈ −0.00808; brazos bajo Greedy (descriptivo) | `exact_contrasts` | Factual; puerta **no** exige batir Greedy |
| Puerta no cumplida; test no abierto | `gate` + cierre | Factual |
| Piloto counterfactual ≠ esta campaña (muestra/$S$/protocolo propios) | § resultados piloto | Factual; **sin** causalidad del signo |
| EP de la campaña ≠ C04 | `_extreme_points.py` en `ee9e0ec` | Factual |
| `physical_stability_verified=null` | capturas | Factual; no se reclama estabilidad física |

## Planos de valoración (no mezclar)

| Plano | Estado |
| --- | --- |
| (a) Coherencia técnica del borrador development-only | Alineado en C06 |
| (b) Afirmaciones limitadas anteriores | Respaldadas por artefactos citados |
| (c) Novedad / relevancia / venue | **No establecido** |

No se presentan como requisitos universales de publicación: superar Greedy,
obtener margen positivo, abrir el test del protocolo, ni demostrar estabilidad
física para afirmaciones solo AABB. Ampliar generalización exigiría evaluación
independiente **autorizada**; no autoriza nueva experimentación en este cierre.
