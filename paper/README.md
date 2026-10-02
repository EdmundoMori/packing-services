# Campaña científica — packing-services

Documentación de investigación. No es el producto ni un resultado publicable.

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
- Paso 07: evaluación independiente congelada, [`reviews/07_evaluation_freeze.md`](reviews/07_evaluation_freeze.md). Protocolo: [`protocols/07_independent_evaluation.md`](protocols/07_independent_evaluation.md). Muestra: [`results/07_sample_freeze.json`](results/07_sample_freeze.json). No está ejecutada.
