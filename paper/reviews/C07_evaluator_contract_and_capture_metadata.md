# C07 — Contrato del evaluador y metadato de captura

**Fecha:** 2026-10-06
**HEAD de trabajo:** `2859678a00dd13f0141462085389a0f9da29da2d`
**Rama:** `research/paper-online-packing`
**Decisión:** `correccion_contractual_lista_para_revision`

Sin entrenamiento, inferencia, packing real ni campañas. Sin reescritura de
capturas, manifiestos, protocolos congelados ni resultados históricos.

## Hallazgos confirmados

1. **`actor_eval_mode`:** en 216/216 capturas de actor de
   `learning_development_eval_full`, `recipe.actor_eval_mode=false`. El campo se
   construía como `method == "actor"` en `pilot_problems.py`, mientras
   `episode_worker` pasa el nombre del brazo. El código de
   `actor_policy_s.py` sí llama `model.eval()` y `torch.no_grad()`. Errata
   independiente: `paper/reviews/errata_actor_eval_mode_learning_development_eval.md`.
2. **`kpis_zhao` pre-C07:** usaba `problem.containers[0]` sin exigir
   moncontenedor; solapes se omitían entre `container_id` distintos; `n_order`
   podía tomarse de `solution.metrics`.
3. **`kpis_zhao_from_plan`:** no recibe el pedido fuente; el alcance no estaba
   expuesto en la salida.

## Correcciones

| Área | Antes | Después |
|------|-------|---------|
| Contenedores | implícito `[0]` | exactamente 1 → si no, `EvaluatorContractError` |
| `container_id` ajeno | solapes omitidos entre ids distintos | `container_contract_valid=false`; solapes moncontenedor siempre; `geometry_valid` no True |
| `bin_lwh` explícito | caller_explicit | se conserva e identifica |
| Completitud | podía usar metrics | IDs de `problem.items`; `metrics_counter_coherence` separado |
| Plan | alcance implícito | `plan_validation_scope` en salida; `comparison_valid` C02 intacto |
| Metadato futuro | inferido del método | `capture_actor_eval_metadata_v1` + puente C07 (código histórico intacto) |

### Tipo de rechazo

- **Excepción de contrato** (`EvaluatorContractError`): 0 o >1 contenedores en
  el problema (no hay un único bin de contrato).
- **Salida inválida estructurada:** `container_id` desconocido/ajeno, solapes,
  IDs, orientación, etc. (`geometry_valid` ≠ true; no se inventa validez).

## Compatibilidad y consumidores

- Consumidores principales: pruebas C02/C03, notebooks históricos de KPI (lectura).
- `episode_worker.py` **no** modificado (hash en `evaluator_fix_hashes.json`).
- `pilot_problems.py` / `actor_policy_s.py` **no** modificados.
- `schema_version` permanece **2** (campos aditivos C07 + nota de migración).

## Errata histórica (sin sobrescritura)

`paper/reviews/errata_actor_eval_mode_learning_development_eval.md`

No deduce invalidez de entrenamiento/packing. No reconstruye cada forward.

## Pruebas

- C02: `test_bedbpp_eval_feasibility.py`
- C03: `test_yaw_export_contract.py`
- C07: `test_bedbpp_eval_contract_c07.py`

Ejecución: 51 tests OK (sin checkpoints ni pickle históricos).

## Límites / pendientes C08

- Integrar el puente C07 en un ejecutor futuro cuando se autorice nueva
  captura (sin reabrir campañas cerradas).
- Multibin real: fuera de alcance; este cierre solo restringe moncontenedor.
- Homologación externa / dataset: no inventada desde `kpis_zhao_from_plan`.
- Venue/novedad y test de campaña: intactos (cerrados).
