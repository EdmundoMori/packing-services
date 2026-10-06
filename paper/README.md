# Campaña científica — packing-services

Documentación de investigación. No es el producto ni un resultado publicable.

## Estado vigente (C01)

Resumen alineado con la evidencia publicada (incluye resultados negativos o no concluyentes):

- **Campañas cerradas:** compacta/corta, counterfactual ranking, rl_rule_selection, learning_objectives, robust_packing_management (y cierres previos en `reviews/` / `studies/*/campaign_closure.md`).
- **learning_objectives:** completó etiquetas, entrenamiento (9 modelos) y evaluación de desarrollo; **puerta incumplida**; **test no ejecutado** (`no_avanzar_con_esta_configuracion`).
- **robust_packing_management:** cerrado por justificación insuficiente; **sin RL evaluada**; G2 estocástico no ejecutado.
- **Infraestructura reutilizable:** motor EP, evaluate/capture, runctl/presupuestos, loaders, contratos geométricos y arneses de estudio — sin reinterpretar cierres como éxito algorítmico.
- **Superioridad y publicabilidad:** **no establecidas.** El intervalo de la evaluación independiente de 200 pedidos incluye cero (`no_concluyente`); no se demostró superioridad frente a PCT; el checkpoint default `mlp_v1_p1s1_ppo.pt` tiene tensores vigentes iguales al BC (`best_epoch=0`).

Errata de afirmaciones documentales: [`reviews/C01_current_claims_correction.md`](reviews/C01_current_claims_correction.md).

Corrección de semántica de factibilidad del evaluador histórico (`bedbpp_eval` schema v2): [`reviews/C02_feasibility_semantics_correction.md`](reviews/C02_feasibility_semantics_correction.md). No regenera JSON 09/10.

Corrección del contrato de exportación yaw 0/1 (`packing_plan_actions` estricto): [`reviews/C03_yaw_export_contract_correction.md`](reviews/C03_yaw_export_contract_correction.md). No regenera planes 09/10 ni 01A/01C/01E.

Corrección de intercepción en franjas EP del motor simplificado (`_support_z`: cima máxima XY con área positiva): [`reviews/C04_extreme_point_projection_correction.md`](reviews/C04_extreme_point_projection_correction.md). No reevalúa campañas cerradas ni altera protocolos congelados.

Corrección de portabilidad de pruebas (rutas de repo vía `__file__`; sin `/home/edmundo/...` ejecutables): [`reviews/C05_test_portability_and_reproducibility.md`](reviews/C05_test_portability_and_reproducibility.md). Entorno actual: [`reviews/C05_current_verification_environment.json`](reviews/C05_current_verification_environment.json). No altera protocolos ni resultados históricos.

## Objetivo provisional

Evaluar si el selector aprendido de colocaciones mejora al heurístico del mismo entorno, o si mantiene calidad comparable a PCT con menor coste. La superioridad y la publicación no están demostradas. Esta carpeta no busca confirmar una conclusión previa.

## Protocolos que no se mezclan

- **Z — homologación con Zhao.** Protocolo del artículo PCT (bin, Uti., Num. y restricciones tal como los defina ese paper). No se copia aquí una definición que no se haya vuelto a leer en el PDF.
- **K — evaluación BED-BPP de Kagerer.** Métricas y empaquetados publicados en ese benchmark (xkpi, ηutil, hn, score). No es Table 1 de Zhao.
- **P — producto packing-services.** `volume_utilization` del execute, heurístico del mismo bucle y holdout de producto.

Un número de un protocolo no decide otro.

## Resultados históricos

Los informes y JSON ya existentes en `online_policy_ml/` son corridas previas. No demuestran superioridad del selector aprendido ni frente al heurístico ni frente a PCT.

## Dónde está el estado

Las entradas siguientes son **registros del estado en cada paso** (cronología). Frases como «etiquetas no ejecutadas» u «piloto no ejecutado» describen el momento de esa revisión, **no** necesariamente el presente; el resumen vigente está arriba.

- Estado de la campaña: [`state.json`](state.json).
- Revisiones por paso: [`reviews/`](reviews/).
- Paso 00, primera ejecución: [`reviews/00_inventory.md`](reviews/00_inventory.md) (`inv-00-20261002T122453Z`).
- Paso 00, segunda ejecución: [`reviews/00_inventory_inv-00-20261002T123046Z.md`](reviews/00_inventory_inv-00-20261002T123046Z.md). El registro anterior no se sustituye.
- Paso 01A: [`reviews/01a_export_audit.md`](reviews/01a_export_audit.md). Resultado geométrico: [`results/01a_export_audit_00100408.json`](results/01a_export_audit_00100408.json).
- Paso 01C: [`reviews/01c_internal_geometry.md`](reviews/01c_internal_geometry.md).
- Paso 01E: [`reviews/01e_orientation_contract.md`](reviews/01e_orientation_contract.md). Informe yaw: [`results/01e_yaw_compatibility_00100408.json`](results/01e_yaw_compatibility_00100408.json).
- Paso 02: [`reviews/02_effective_protocol.md`](reviews/02_effective_protocol.md). Exposición de splits: [`results/02_split_exposure.json`](results/02_split_exposure.json).
- Paso 03: protocolo del piloto [`protocols/03_internal_pilot.md`](protocols/03_internal_pilot.md). Cruces: [`results/03_split_cross_audit.json`](results/03_split_cross_audit.json). Reserva: [`results/03_confirmatory_candidates.json`](results/03_confirmatory_candidates.json).
- Ajuste 03A: cada pedido conserva su target, [`reviews/03a_pilot_target_amendment.md`](reviews/03a_pilot_target_amendment.md). El piloto no está ejecutado.
- Paso 04: evaluador implementado, [`reviews/04_evaluator_implementation.md`](reviews/04_evaluator_implementation.md). Anexo: [`protocols/04_evaluator_operational.md`](protocols/04_evaluator_operational.md). El preflight de los 20 pedidos pasó. No hubo inferencia.
- Paso 04A: validación de resultados del worker, [`reviews/04a_worker_validation.md`](reviews/04a_worker_validation.md).
- Paso 05: primera corrida del piloto interno, [`reviews/05_internal_pilot_run.md`](reviews/05_internal_pilot_run.md). Resultados: [`results/04_internal_pilot/`](results/04_internal_pilot/). Es una comparación interna en este conjunto de desarrollo.
- Paso 06: procedencia del actor y candidatos de ambos targets, [`reviews/06_actor_provenance.md`](reviews/06_actor_provenance.md). Clasificación: [`results/06_candidate_exposure_by_target.json`](results/06_candidate_exposure_by_target.json). No evalúa esos candidatos.
- Paso 06A: IDs de las transiciones BC, [`reviews/06a_bc_transition_provenance.md`](reviews/06a_bc_transition_provenance.md). Lectura: [`results/06a_bc_transition_ids.json`](results/06a_bc_transition_ids.json). Candidatos: [`results/06a_candidate_exposure_by_target.json`](results/06a_candidate_exposure_by_target.json).
- Paso 07: evaluación independiente congelada, [`reviews/07_evaluation_freeze.md`](reviews/07_evaluation_freeze.md). Protocolo: [`protocols/07_independent_evaluation.md`](protocols/07_independent_evaluation.md). Muestra: [`results/07_sample_freeze.json`](results/07_sample_freeze.json). La corrida está en el paso 08.
- Paso 08: primera corrida de esa evaluación, [`reviews/08_independent_evaluation_run.md`](reviews/08_independent_evaluation_run.md). Resultados: [`results/07_independent_evaluation/`](results/07_independent_evaluation/). Análisis: [`results/07_independent_evaluation/independent_analysis.json`](results/07_independent_evaluation/independent_analysis.json). El intervalo incluye el cero y la clasificación predefinida es no concluyente (**no** equivalencia).
- Paso 09: diagnóstico exploratorio posterior al resultado, [`reviews/09_exploratory_diagnosis.md`](reviews/09_exploratory_diagnosis.md). Lectura: [`results/09_policy_diagnostics.json`](results/09_policy_diagnostics.json). Pedidos ya observados: [`results/09_exposed_evaluation_ids.json`](results/09_exposed_evaluation_ids.json). No cambia la clasificación del paso 08.
- Paso 10: ablación de normalización congelada, [`reviews/10_normalization_design.md`](reviews/10_normalization_design.md). Protocolo: [`protocols/10_normalization_ablation.md`](protocols/10_normalization_ablation.md). Estadísticas y muestra: [`results/10_normalization_freeze.json`](results/10_normalization_freeze.json). No entrena ni empaqueta.
- Paso 11: ejecutor de esa ablación, [`reviews/11_ablation_runner.md`](reviews/11_ablation_runner.md). Entrada: [`paper/tools/run_normalization_ablation.py`](tools/run_normalization_ablation.py). No ejecuta las etapas reales.
- Paso 12: entrenamiento de los diez modelos, [`reviews/12_ablation_training.md`](reviews/12_ablation_training.md). Evidencia: [`results/11_normalization_ablation/`](results/11_normalization_ablation/). No empaqueta y no elige una semilla.
- Paso 12A: contrato del packing de esa ablación, [`reviews/12a_ablation_packing_contract.md`](reviews/12a_ablation_packing_contract.md). Corrige el proceso por caso, el timeout y el contraste con el snapshot. No empaqueta ni reentrena.
- Paso 13: packing de desarrollo de los 550 casos, [`reviews/13_normalization_development.md`](reviews/13_normalization_development.md). Resultados: [`results/11_normalization_ablation/packing/`](results/11_normalization_ablation/packing/). La regla congelada abandona esta configuración. No es una confirmación.
- Paso 14: diagnóstico preparado del teacher frente a GreedyBestFit, [`reviews/14_teacher_probe_design.md`](reviews/14_teacher_probe_design.md). Protocolo: [`protocols/14_teacher_probe.md`](protocols/14_teacher_probe.md). No ejecuta los 50 pedidos.
- Paso 15: diagnóstico ejecutado del teacher en esos 50 pedidos, [`reviews/15_teacher_utility_run.md`](reviews/15_teacher_utility_run.md). Resultados: [`results/14_teacher_probe/`](results/14_teacher_probe/). Recálculo: [`results/14_teacher_probe/verification.json`](results/14_teacher_probe/verification.json). La media de delta es negativa. El protocolo 14 permanece sin el campo `executed` alterado.
- Paso 16: contrato geométrico común y prueba de OnlineBPH, [`reviews/16_protocol_and_baseline_feasibility.md`](reviews/16_protocol_and_baseline_feasibility.md). Protocolo: [`protocols/16_compact_selector_study.md`](protocols/16_compact_selector_study.md). El smoke está en [`results/16_baseline_smoke/`](results/16_baseline_smoke/). Esos cinco resultados de OnlineBPH siguen en `method_failure`. La cuadrícula no se ejecutó.
- Paso 16A: contrato de captura de OnlineBPH, [`reviews/16a_onlinebph_capture_contract.md`](reviews/16a_onlinebph_capture_contract.md). Verificación nueva: [`results/16a_onlinebph_capture_smoke/`](results/16a_onlinebph_capture_smoke/). El diagnóstico posterior del smoke original no sustituye esos fallos. Esta corrida sí atraviesa el runner y la auditoría. La calibración no se ejecutó.
- Paso 17: calibración del selector compacto, [`reviews/17_compact_calibration_run.md`](reviews/17_compact_calibration_run.md). Protocolo: [`protocols/17_compact_calibration.md`](protocols/17_compact_calibration.md). Resultados: [`results/17_compact_calibration/`](results/17_compact_calibration/). La cuadrícula de 32 configuraciones se ejecutó. La regla congelada abandona la configuración elegida. No es una comparación con OnlineBPH ni una confirmación.
- Cierre de la campaña corta: [`reviews/18_short_campaign_closure.md`](reviews/18_short_campaign_closure.md). Esta vía se cierra. No continúa a comparación externa ni a test confirmatorio con la configuración elegida. El informe no es un artículo listo para envío.
- Estudio posterior de desarrollo: [`studies/counterfactual_ranking/README.md`](studies/counterfactual_ranking/README.md). El diagnóstico está en [`studies/counterfactual_ranking/diagnostic_review.md`](studies/counterfactual_ranking/diagnostic_review.md). Las etiquetas del piloto están en [`studies/counterfactual_ranking/learning_labels_review.md`](studies/counterfactual_ranking/learning_labels_review.md). El ajuste de los dos brazos está en [`studies/counterfactual_ranking/training_review.md`](studies/counterfactual_ranking/training_review.md). Los episodios de development y la puerta están en [`studies/counterfactual_ranking/packing_review.md`](studies/counterfactual_ranking/packing_review.md). El cierre está en [`studies/counterfactual_ranking/campaign_closure.md`](studies/counterfactual_ranking/campaign_closure.md). No reabre la cuadrícula compacta. La puerta no se cumple: no se avanza con esta configuración. El test final no se selecciona ni se ejecuta.
- Piloto de selección de reglas, cerrado: [`studies/rl_rule_selection/campaign_closure.md`](studies/rl_rule_selection/campaign_closure.md). Matriz: [`studies/rl_rule_selection/claims_evidence.md`](studies/rl_rule_selection/claims_evidence.md). La política determinista seleccionó Greedy en el desarrollo y la puerta no se cumple. No hay más entrenamiento ni test. No reabre la campaña compacta ni la de counterfactual ranking. La búsqueda experimental de mejora algorítmica se detiene en estas configuraciones.
- Iniciativa de objetivos de aprendizaje — **cerrada tras puerta de desarrollo fallida**: [`studies/learning_objectives/campaign_closure.md`](studies/learning_objectives/campaign_closure.md). Etiquetas, entrenamiento y desarrollo **sí** se ejecutaron en esa campaña; el test permanece cerrado. La entrada cronológica anterior que decía «etiquetas no ejecutadas» es un registro de un paso previo, no el estado presente. No reabre campañas cerradas.
- Estudio de gestión de packing bajo incertidumbre geométrica — **cerrado**: [`studies/robust_packing_management/campaign_closure.md`](studies/robust_packing_management/campaign_closure.md). Decisión: `cerrar_linea_por_justificacion_insuficiente`. Preflight determinista de arnés (8 episodios) conservado como histórico; G2 estocástico y RL **no** ejecutados. Manuscrito preliminar archivado: [`manuscript/robust_packing_management/`](manuscript/robust_packing_management/). No reabre campañas cerradas.
