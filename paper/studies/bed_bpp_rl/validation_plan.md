# Plan de validación previsto (post-R01; no ejecutado aquí)

El criterio de éxito es un **recurso correcto, reutilizable y utilizable por RL**.
No exige superar una heurística ni obtener mejora positiva.

## Verificaciones pequeñas (diseño)

| ID | Comprobación | Idea de prueba | Tamaño |
|----|--------------|----------------|--------|
| V1 | Observabilidad sin fuga de futuro | La observación no cambia al permutar el sufijo no visible; keys audit ≠ agent | Sintético + 1 pedido mock |
| V2 | Legalidad de acciones | `action ∈ {0,1,2}`; geometría de la regla ∈ candidatas legales | Unitaria sobre `propose_rules` |
| V3 | Suma de rewards = \(U_{\mathrm{geom}}\) | Episodio completo (terminated, no truncated) | Pocos episodios medidos |
| V4 | Terminación vs truncación | Sin candidata → terminated; corte de presupuesto → truncated sin inventar retorno | Unitaria + harness |
| V5 | Consistencia de transiciones | `obs_{t+1}` del registro = `obs` del siguiente; máscaras coherentes | Corpus sintético corto |
| V6 | Persistencia/lectura | Round-trip JSON/parquet del esquema v1 | Fixture pequeño |
| V7 | Reproducción con semillas | Misma semilla + misma política ⇒ mismas acciones/geometrías | 2 semillas × 1 pedido |
| V8 | Usable por RL mínimo | Un rollout + un update PPO (matemática existente) sin puerta de campaña | Smoke CPU corto |

## Qué no se fija en R01

- Tamaño final del corpus.
- Presupuesto de pared extrapolado.
- Manifiestos train/dev/test.
- Umbrales de mejora vs Greedy.

Esos valores se decidirán **después de un preflight medido** (R02+), no por
extrapolación desde campañas cerradas.
