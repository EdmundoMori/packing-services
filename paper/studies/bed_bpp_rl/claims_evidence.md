# Claims ↔ evidence (BED-BPP-RL)

## R01 (diseño)

| Afirmación | Evidencia |
|------------|-----------|
| Recurso definible reutilizando el repo | `reuse_matrix.md`, `reviews/R01_scope_and_reuse.md` |
| Contrato inicial alineado con implementaciones | `environment_contract_draft.json` (entonces draft) |

## R02 (implementación sintética)

| Afirmación | Evidencia | Estado |
|------------|-----------|--------|
| Interfaz `reset`/`step`/`close` con `(obs,r,terminated,truncated,info)` | `tools/environment.py` (`BedBppRlEnv`) | Verificado en pruebas sintéticas |
| 36 features documentadas (orden, fórmulas, unidades, terminal) | `tools/observation_spec.py` | Verificado |
| Observación ≠ Markov suficiente (sin evidencia) | `markov_sufficiency_claimed: false` | Explícito |
| Capas estado interno / obs / auditoría | `observation_spec.LAYERS` + contrato | Documentado |
| Terminación auto tras placement sin candidata siguiente | `environment.py` + `test_next_item_impossible_after_placement` | Pass |
| Cero transiciones si primer ítem imposible | `test_first_item_impossible_zero_transitions` | Pass |
| Truncación conserva obs/máscara bootstrap | `test_truncation_keeps_bootstrap_observation` | Pass |
| Terminación natural prioriza sobre presupuesto | `test_natural_termination_priority_over_budget` | Pass |
| Identidades de acción con geometría coincidente | `test_coincident_geometries_preserve_action_identity` | Pass |
| `step` tras cierre rechazado | `test_step_after_close_rejected` | Pass |
| Observación independiente del sufijo | `test_observation_independent_of_suffix` | Pass |
| Reward = U_geom vía volumen AABB recompuesto | `resource_verifier` + `test_reward_matches_audited_volume` | Pass |
| Corpus atómico + manifiesto; tmp/duplicados rechazados | `corpus_writer` + `test_interrupted_write_incomplete_and_duplicates` | Pass |
| Loader agente excluye auditoría | `corpus_loader` + `test_agent_loader_excludes_audit` | Pass |
| Sin `behavior_log_probs` / sin off-policy por importancia | `corpus_contract.off_policy_importance_supported=false` | Explícito |
| Motor post-C04 | `engine_check.verify_post_c04_engine` + `test_engine_post_c04` | Pass |
| `physical_stability_verified` permanece null | verifier + summaries | Pass |

### No afirmado en R02

- Superioridad o novedad demostrada
- Publicabilidad / tamaño de corpus real
- Suficiencia Markov de la observación
- Evaluación off-policy por importancia
- Rendimiento en pedidos BED-BPP reales
