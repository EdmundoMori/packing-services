# C01 — Corrección de afirmaciones científicas vigentes

**Fecha:** 2026-10-06
**HEAD de trabajo:** `295dd08e0387ff918378c4acfdf91fdb3a95aaef`
**Rama:** `research/paper-online-packing`
**Alcance:** solo documentación vigente (+ entrada de mantenimiento en `state.json`).
**No altera:** JSON de resultados, capturas, protocolos congelados, checkpoints, revisiones/cierres históricos (salvo aviso en el informe 2026-09-15), código fuente ni manuscritos.

Esta corrección documental **no** valida evaluadores históricos ni cambia cifras publicadas.

## Tabla

| Archivo | Afirmación anterior | Corrección | Evidencia | Alcance |
|---------|---------------------|------------|-----------|---------|
| `online_policy_ml/README.md` | Holdout: «empate» | IC incluye 0 → **no concluyente**; no igualdad ni equivalencia | Informe histórico §3 (Δ=−0.0014, IC95 cruza 0); no reinterpreta el JSON | Subproyecto |
| `online_policy_ml/README.md` | Evaluación 200 confusa con holdout / «empate» | Protocolo 07 / paso 08 distinto; `no_concluyente`; no equivalencia | `paper/reviews/08_independent_evaluation_run.md` (media ≈ −0.00059; IC incluye 0; igualdad sin demostrar) | Subproyecto |
| `online_policy_ml/README.md` | `00100408`: «supera» PCT por factible | Caso histórico inspeccionado; captura interna auditada en ese flujo; hn publicado = transferencia PCT (Kagerer); límite de altura propio ≠ ICLR homologado ni BED-BPP completo; **no** superioridad PCT; MLP ≠ reproducción PCT | Informe histórico §4–5 (pedido único, columna factibilidad, hn 2.105 m publicado); protocolos Z/K/P en `paper/README.md` (no se mezclan). **No** `06_actor_provenance` | Subproyecto |
| `online_policy_ml/README.md` | Default «RL/PPO» = método de pesos | Nombre archivo + opción API ≠ método de pesos; tensores vigentes = BC; `best_epoch=0` no es mejora PPO | `paper/reviews/06_actor_provenance.md` (igualdad de tensores; `05_rl_ppo.json` con `best_epoch` 0) | Subproyecto |
| `docs/roadmap.md` | «empate estadístico»; «supera» PCT | Misma reinterpretación; holdout n=5 ≠ evaluación 200 | Filas anteriores (informe §3–5; 08; 06) | Hoja de ruta |
| `docs/README.md` | «empate vs heurístico, veredicto puntual vs PCT» | Informe **histórico** + enlace errata C01 | Este archivo | Índice docs |
| `docs/api_examples.md` | «empate estadístico»; «PPO de producción» | No concluyente / no equivalencia; pesos = BC | informe §3; 06; 08 | Ejemplos API |
| `docs/architecture.md` | «empate estadístico»; RL como método de pesos | Opción API `policy=rl`; pesos BC vigentes | `06_actor_provenance.md` | Arquitectura |
| `README.md` (raíz) | «política … (RL / PPO)» como producción | Infraestructura online; nombre/opción ≠ método de pesos | `06_actor_provenance.md` | README producto |
| `online_policy_ml/docs/informe_cierre_rl_online.md` | Cuerpo con «empate» / «supera» | **Conservado**; aviso C01 al inicio | Diff: solo bloque aviso | Informe 2026-09-15 |
| `paper/README.md` | Cronología leíble como presente («etiquetas no ejecutadas») | Resumen **Estado vigente (C01)**; cronología = registros por paso; LO/RPM actualizados | `studies/learning_objectives/campaign_closure.md`; `studies/robust_packing_management/campaign_closure.md`; paso 08 | Campaña científica |
| `paper/reviews/08_independent_evaluation_run.md` | — | **Sin reescritura** (ya correcto) | propio | Evaluación 200 |
| `paper/reviews/06_actor_provenance.md` / `06a_…` | — | **Sin reescritura** (ya correcto) | propios | Procedencia |

## Separación de evidencias

- **Procedencia BC / `best_epoch=0`:** solo `06_actor_provenance.md` (y el informe de corrida PPO que cita).
- **Holdout n=5 no concluyente:** informe histórico §3 / `06_evaluar_holdout.json` (vía ese informe).
- **Evaluación 200 `no_concluyente`:** `08_independent_evaluation_run.md`.
- **No homologación / no superioridad PCT:** informe §4–5 + distinción de protocolos Z/K/P; **no** se usa la procedencia del actor como prueba de protocolos.

## Coincidencias conservadas (no son errores de afirmación vigente)

- Cierres y claims de estudios (`campaign_closure.md`, matrices): conclusión acotada o rechazo explícito de superioridad/equivalencia.
- Literatura / hipótesis («política Transformer/PPO» de GOPT, preguntas de diseño).
- «Equivalencia» geométrica de rebuild, desempates de reglas, W/T/L con tolerancia numérica.
- Manuscritos: fuera de alcance de C01.
- Estudios PPO / RL posteriores: procedencia y cierre propios (p. ej. `rl_rule_selection`, `learning_objectives`).

## Verificación de intención

1. **PCT:** no superioridad demostrada; un caso + hn publicado de transferencia ≠ protocolo ICLR homologado.
2. **«Empate»:** ausencia de diferencia concluyente ≠ equivalencia; 200 pedidos clasificados `no_concluyente`.
3. **Checkpoint:** nombre archivo / opción API / método de pesos separados; `best_epoch=0` no es mejora PPO.
4. **Estado:** campañas cerradas; LO con etiquetas+train+dev y puerta fallida; RPM sin RL evaluada.
