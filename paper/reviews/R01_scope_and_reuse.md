# R01 — Alcance y reutilización de BED-BPP-RL

**Fecha:** 2026-10-06
**HEAD de trabajo:** `203d061c41ac8d7ae902cacbd6bd3a8377264d5b`
**Rama:** `research/paper-online-packing`
**Decisión:** `diseno_del_recurso_listo_para_implementacion`

Sin pedidos reales, entrenamiento, generación de corpus ni apertura de test.

## Pregunta y objetivo R01

Definir un recurso **realizable** reutilizando el repositorio: entorno + esquema
de experiencias + límites, verificando componentes existentes.

## Motor

EP simplificado **post-C04** (`_extreme_points.py` desde `a5fb468…`). No el
motor histórico de `learning_objectives` (`ee9e0ec`).

## Contrato verificado punto a punto

| Requisito R01 | Evidencia reutilizable |
|---------------|------------------------|
| Secuencia original BED-BPP | `build_compact_problem` / `sort_strategy=input_order` |
| Un contenedor del target | `len(containers)==1`; dims del pedido |
| p=s=1 | `_assert_contract` en `RuleSelectionEnv` |
| Hasta 6 orientaciones | sesión EP + `allow_rotation` |
| Contención y no solape | `COMPACT_FLAGS` + `ValidatorMask` |
| Parada sin candidata | `_stop_current` / `TERMINAL_REASON` |
| Peso/estabilidad/load-bearing fuera | flags compactos en false |
| Observación sin sufijo/futuro/retornos | `observation.py` (36-D) |
| Reward ΔV/V_bin | `RuleSelectionEnv.step` |
| γ=1 ↔ U_geom | `protocol_frozen` / `ppo_math` + `geometric_utilization` |
| Tres reglas con identidades | `rules.RULE_NAMES` + `propose_rules` |

No es el protocolo robótico oficial BED-BPP (`physical_stability_verified=null`).

## Matriz (resumen)

Ver `paper/studies/bed_bpp_rl/reuse_matrix.md`.

- **Reutilizar:** `order_to_problem` / `build_compact_problem`, sesión EP,
  máscara, `rules.py`, `observation.py`, `bedbpp_eval` (auditoría), matemáticas
  T/T de `ppo_math.py`.
- **Adaptar:** `RuleSelectionEnv` (exponer truncación / escritor de corpus),
  patrones runctl, captura (no como transición RL).
- **Excluir:** pesos/capturas/Q_hat de campañas cerradas; PPO de producto;
  OnlineBPH/PCT; protocolo robótico oficial.

## Contrato y esquema

- `environment_contract_draft.json` — alcance mínimo verificado contra la
  implementación reutilizable.
- `corpus_schema_v1.json` — campos agente vs auditoría; terminal / truncación.

## Límites y pendientes (no R02)

- Freeze formal del contrato; wrappers versionados.
- Preflight medido antes de fijar tamaños/presupuestos.
- Manifiestos y generación de experiencias.
- Condiciones de redistribución del dataset fuente (solo citadas, no copiadas).
- Novedad / venue: **no establecidas**.

## Manuscrito

Borrador LaTeX en `paper/manuscript/bed_bpp_rl/` (diseño y protocolo de
validación; resultados pendientes).

## Decisión

`diseno_del_recurso_listo_para_implementacion`
