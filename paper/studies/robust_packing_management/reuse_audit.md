# Auditoría de reutilización (sin modificar `src/` salvo necesidad demostrada)

**Reglas:** reutilizar por import/adaptador; no copiar motores; no cargar checkpoints ni pickle históricos; distinguir infraestructura PPO de contrato/recompensa/pesos.

## 1. Lectura y conversión BED-BPP

| Pieza | Ubicación |
|-------|-----------|
| Detección / listado de pedidos | `src/packing_services/datasets/bed_bpp.py` — `looks_like_bed_bpp_orders`, `list_order_ids`, `extract_orders_and_id` |
| Conversión a input de packing | `convert_order_to_pack_input`, `convert_order_to_benchmark_input`, `normalize_execute_payload` |
| Contenedor desde target del pedido | `_resolve_target_container` (usa `properties.target` salvo `target_override`) |
| Ítems desde secuencia | `_items_from_sequence` |
| Wrapper estudio ML | `online_policy_ml/src_ml/problems.py` — `order_to_problem`, `online_params` |
| Dataset externo referenciado | `/home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json` (fuera del índice; no abrir pickle) |

**Reutilizar:** parser/conversión.
**No reutilizar como evidencia:** resultados de campañas cerradas.

## 2. Target propio por pedido

| Pieza | Ubicación |
|-------|-----------|
| Target en properties del pedido BED-BPP | `bed_bpp.convert_order_to_pack_input` (lee `props["target"]`) |
| Construcción de problema de estudio | `paper/tools/pilot_problems.py` — `build_problem` |
| Snapshot de entrada | `problem_snapshot`, `shared_config` |
| Muestreo por target en estudios previos | `paper/tools/compact_study.py` — `propose_calibration_orders`, filtros por `euro-pallet` / `rollcontainer` |

**Contrato provisional de esta línea:** un contenedor = target propio del pedido; no forzar un único bin global.

## 3. Generación de candidatas

| Pieza | Ubicación |
|-------|-----------|
| Sesión extreme points | `src/packing_services/online/session.py` — `ExtremePointOnlineSession.candidates` |
| Orientaciones | `orientations_for` → `unique_orientations` (`domain/geometry`) |
| Factibilidad | `packer._feasible` dentro de `candidates` |
| Generador simplificado (no EMS/PCT) | Documentado en campañas cerradas: extreme points; **no** presentar como PCT |

**Falta para esta línea:** candidatas con **envolvente protegida** (ítem inflado / holgura) sin alterar el volumen nominal reportado.

## 4. GreedyBestFit

| Pieza | Ubicación |
|-------|-----------|
| Política | `src/packing_services/online/policies.py` — `GreedyBestFitPolicy` |
| Uso en workers de estudio | `paper/studies/learning_objectives/tools/episode_worker.py` |
| Uso en captura compacta | `paper/tools/compact_study.py` — `run_compact_greedy` |

**Nota:** OnlineBPH es heurística distinta (`compact_study.capture_online_bph`); **no** es PCT aprendido.

## 5. Orientaciones

| Pieza | Ubicación |
|-------|-----------|
| Generación | `ExtremePointOnlineSession.orientations_for` |
| Validación de yaw / permutación | `paper/tools/audit_internal_solution.py` — `_yaw_representable`, `_is_permutation` |
| Contrato histórico de orientación | `paper/reviews/01e_orientation_contract.md` (no modificar; solo referencia) |

## 6. Captura

| Pieza | Ubicación |
|-------|-----------|
| Documento de captura | `paper/tools/pilot_problems.py` — `capture_document` |
| Workers | `paper/tools/pilot_worker.py`, `compact_worker.py`, `paper/studies/learning_objectives/tools/episode_worker.py` |

## 7. Contraste de entrada

| Pieza | Ubicación |
|-------|-----------|
| Contraste captura vs snapshot | `paper/tools/pilot_metrics.py` — `contrast_capture` |
| Contraste export / histórico | `audit_internal_solution.contrast_export`, `contrast_historical` |

## 8. Auditoría geométrica

| Pieza | Ubicación |
|-------|-----------|
| Contención / no solape / validez interna | `paper/tools/audit_internal_solution.py` — `audit_document` → `internal_geometry_valid` |
| Validador de producto | `src/packing_services/validation/validator.py` |
| Utilización geométrica recompuesta | en estudios: `campaign.recompute_u` (learning_objectives); no usar nombres Zhao (`Uti.`) ni Kagerer (`xkpi`, `Σalgo`) de forma intercambiable |

**Separar:** solape/contención (sí en alcance geométrico) vs estabilidad física, accesibilidad y trayectoria (fuera del alcance provisional; `physical_stability_verified` permanece no afirmado).

## 9. Workers y control de presupuesto

| Pieza | Ubicación |
|-------|-----------|
| Presupuesto de información online p/s | `src/packing_services/online/budget.py` — `InformationBudget` |
| Control de corridas / heartbeat | `paper/studies/learning_objectives/tools/labeling_runctl.py` |
| Ledger de presupuesto de estudio | `labeling_budget.budget_ledger` |
| Loop online | `src/packing_services/online/loop.py` |

**Reutilizar patrón** de runctl/ledger; **nuevo ledger** propio de esta línea (no mezclar cupos de campañas cerradas).

## 10. Infraestructura PPO

| Pieza | Ubicación | Reutilizable como… |
|-------|-----------|-------------------|
| Entrenador PPO | `online_policy_ml/src_ml/train_ppo.py` — `fit_ppo`, `rollout_episode`, `_ppo_update` | Infraestructura (optimizador, bucles) |
| Recompensas actuales | `place_reward`, `discard_penalty`, `terminal_reward` | **No** reutilizar contrato sin rediseño |
| Actor/checkpoint loaders | `load_actor_from_pt`, `online_policy_ml/.../checkpoint.py` | **No** cargar pesos históricos para esta línea |
| Encoder de features de producto | `src/packing_services/online/features.py`, learned backends | Solo si el MDP de protección lo justifica; no por inercia |
| Teacher / BC | `online_policy_ml/src_ml/teacher.py` | Fuera de alcance salvo baseline no-RL |

**Distinción crítica:** reutilizar *código de entrenamiento* ≠ reutilizar *MDP, recompensa, soporte S, ni checkpoints* de learning_objectives / PPO histórico.

## Qué falta (aún no existe)

1. Modelo de incertidumbre geométrica sintética y muestreo de escenarios (diseñado, no ejecutado).
2. Acción de “protección” que modifique factibilidad sin contar volumen de margen.
3. Baselines de margen uniforme / margen derivado / adaptativo determinista bajo la **misma** información.
4. Criterio de riesgo operativo (p. ej. tasa de fallo geométrico) acoplado a volumen nominal.
5. Preflight sintético corto y diagnóstico posterior (propuestos en `decision_gates.md`, **no ejecutados**).
6. Adaptadores de holgura sin tocar el motor salvo necesidad demostrada tras G1.

## Política respecto a `src/`

No modificar `src/` en esta pasada. Cualquier cambio futuro exige: fallo reproducible del adaptador + justificación en revisión G1.
