# Matriz de reutilización — BED-BPP-RL (R01)

**Motor EP previsto para el recurso:** versión **post-C04** de
`src/packing_services/algorithms/_extreme_points.py`
(commit de corrección `a5fb46879c7bfbe16400eec2ab985dd23bf30385`; tip de rama
al abrir R01: `203d061…`). No reutilizar el motor histórico pre-C04
(`ee9e0ec`) de episodios `learning_objectives`.

Convención: **importar** herramientas existentes cuando el contrato sea
compatible; **adaptar** con wrappers versionados bajo `bed_bpp_rl/tools/`
(aún no implementados en R01); **excluir** contratos/pesos/resultados de
campañas cerradas.

| Componente | Archivo(s) | Responsabilidad | Decisión | Motivo |
|------------|------------|-----------------|----------|--------|
| Conversión BED-BPP → problema | `online_policy_ml/src_ml/problems.py` (`order_to_problem`); `paper/tools/compact_study.py` (`build_compact_problem`, `COMPACT_FLAGS`) | Pedido → `PackingProblem` moncontenedor, p=s=1, secuencia original | **Reutilizar** (import) | Ya impone el contrato geométrico compacto verificable |
| Sesión EP + candidatas | `src/packing_services/online/session.py` (`ExtremePointOnlineSession`) | Genera candidatas legales vía motor EP | **Reutilizar** | API estable; usará motor C04 del árbol actual |
| Máscara / validación | `src/packing_services/online/mask.py` (`ValidatorMask`) | Contención/no-solape según flags | **Reutilizar** | Misma máscara que el piloto de reglas |
| Políticas fijas (3 reglas) | `paper/studies/rl_rule_selection/tools/rules.py` | Propuestas `greedy_best_fit`, `lowest_top`, `least_height_increase` con identidades distintas aunque la geometría coincida | **Reutilizar** (import) | Encaja el espacio de acciones inicial; no copiar |
| Observación 36-D | `paper/studies/rl_rule_selection/tools/observation.py` | Ítem + estado + 3 propuestas; sin sufijo ni conteo futuro | **Reutilizar** con auditoría de fuga | Cumple observabilidad R01; no inventar fields |
| Entorno selección de reglas | `paper/studies/rl_rule_selection/tools/environment.py` (`RuleSelectionEnv`) | `reset`/`step`, reward = ΔV/V_bin, stop sin candidata | **Adaptar** | Falta `truncated` en la API de step; corpus RL nuevo; no arrastrar puertas/checkpoints del piloto cerrado |
| PPO / terminación–truncación | `rl_rule_selection/tools/ppo_math.py`, `train_loop.py` | Returns con `terminated` vs `truncated`; γ=1 | **Adaptar** (importar matemáticas; no el loop de campaña) | Separación T/T ya correcta; bucles/presupuestos del piloto no son el recurso |
| Actor/crítico mínimos | `rl_rule_selection/tools/model.py` | MLP 36→64→3 / 36→64→1 | **Adaptar** (opcional, solo validación RL mínima) | Útil para prueba de usabilidad; no reutilizar pesos históricos |
| Captura / auditoría | `paper/tools/pilot_problems.py` (`capture_document`); contrastes compactos | Snapshot de plan AABB | **Adaptar** | Capturas de packing ≠ transiciones RL; metadato C07 explícito si se usa |
| Persistencia / runctl | `labeling_runctl.py`, patrones de `atomic_write_json` | Control de proceso y presupuesto | **Adaptar** patrones | Reutilizar ideas de ledger; no los planes de campañas cerradas |
| Evaluador `bedbpp_eval` | `online_policy_ml/src_ml/bedbpp_eval.py` | U_geom / geometría AABB (C02/C07) | **Reutilizar** para auditoría | No como señal de entrenamiento; moncontenedor |
| PPO producción / BC | `online_policy_ml/src_ml/train_ppo.py`, checkpoints `mlp_v1_*` | Producto histórico | **Excluir** | MDP/recompensa/observación distintos; no contaminar el recurso |
| Etiquetas Q_hat / learning_objectives | `learning_labels*`, modelos seed_* | Supervisión counterfactual | **Excluir** como transiciones RL | No son (s,a,r,s'); son etiquetas de continuación greedy |
| Capturas rl_rule_selection development | `rl_rule_selection/development/cases/**` | Episodios del piloto cerrado | **Excluir** como corpus del recurso | Evidencia histórica del piloto; no corpus versionado BED-BPP-RL; regenerar bajo contrato R01+C04 |
| OnlineBPH / PCT | integraciones externas | Baselines ajenas | **Excluir** del recurso inicial | Fuera del espacio de 3 reglas |
| Estabilidad Blender / xkpi Kagerer | bed-bpp-env evaluation | Protocolo robótico oficial | **Excluir** del contrato inicial | R01 no es protocolo robótico BED-BPP oficial |

## Identidades de acción

El recurso estudia **RL de selección entre tres reglas** con índices 0/1/2
fijos (`RULE_NAMES`). Aunque dos reglas propongan la misma geometría, las
acciones permanecen distintas (redundancia documentada). No se amplía en R01
a un segundo espacio (p. ej. índice libre sobre todas las candidatas).
