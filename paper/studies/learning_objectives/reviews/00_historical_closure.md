# Cierre histórico comprobado

HEAD de este paso: `904038ff7f495510f1b8f3d398da3e4eb281a406`, rama `research/paper-online-packing`. No hay `AGENTS.md`. No se reescribieron decisiones ni se eliminaron intentos abortados. No hubo episodios, etiquetas ni entrenamiento nuevos.

Las campañas no se suman. Cada bloque conserva su protocolo y su muestra.

## 1. Campañas internas históricas

### 1.1 Actor histórico (evaluación independiente)

- Pregunta y contrato: comparar el actor PPO histórico frente a una heurística en 200 pedidos congelados (`paper/protocols/07_independent_evaluation.json`; revisión `paper/reviews/08_independent_evaluation_run.md`).
- Resultado principal: media de delta `-0.0005938201577380936`; intervalo bootstrap percentil 95 % `[-0.006293330782645088, 0.005043209075334814]`; clasificación `no_concluyente`.
- Decisión de cierre: consolidada en `paper/reviews/18_short_campaign_closure.md`; no se trata como mejora demostrada.
- Evidencia y límites: 400 filas únicas; `physical_stability_verified=null`; sin comparación con PCT.
- Artefactos reutilizables: `paper/results/07_independent_evaluation/`, protocolo 07, herramientas de piloto interno.

### 1.2 Ablación de normalización

- Pregunta y contrato: raw frente a normalizado con la misma arquitectura (`paper/reviews/13_normalization_development.md`).
- Resultado principal: media de semillas normalized−raw `0.001397889732142849`; ambos brazos por debajo de la heurística en media.
- Decisión: configuración abandonada por su propia regla.
- Límites: 50 pedidos × 5 semillas; no son 250 pedidos independientes.
- Artefactos: `paper/results/11_normalization_ablation/`.

### 1.3 Diagnóstico del teacher

- Pregunta y contrato: utilidad del teacher privilegiado frente a GreedyBestFit (`paper/reviews/15_teacher_utility_run.md`).
- Resultado principal: media teacher−Greedy `-0.021117453869047634`.
- Decisión: no justifica avanzar esa vía como mejora demostrada.
- Artefactos: `paper/results/14_teacher_probe/`.

## 2. Campaña compacta

- Pregunta y contrato: calibrar el selector `compact_contact_height_v1` bajo el contrato geométrico del paso 16 (`paper/reviews/17_compact_calibration_run.md`, cierre `paper/reviews/18_short_campaign_closure.md`).
- Resultado principal: 1520 casos; configuración elegida en desarrollo `a=1`, `b=0.5`, `c=0`; puerta incumplida (A y B fallan, C cumple).
- Decisión: cerrar la vía; no comparación externa ni test confirmatorio con esa configuración.
- Evidencia y límites: OnlineBPH del smoke original sigue en `method_failure`; estabilidad física null; no superioridad frente a PCT.
- Artefactos reutilizables: `paper/tools/compact_study.py`, protocolo 17, `paper/results/17_compact_calibration/`.

## 3. Counterfactual ranking

- Pregunta y contrato: ¿aprender diferencias de retorno entre candidatas mejora el packing frente a aprender solo la identidad de la mejor candidata, con los mismos datos, observabilidad, arquitectura y motor? Protocolo SHA256 `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`.
- Resultado principal (recalculado desde 84 `result.json`):
  - preferencias−clasificación = `0.03094863126240079`
  - preferencias−Greedy = `-0.019783628885582008`
  - clasificación−Greedy = `-0.050732260147982794`
  - 12 pedidos de desarrollo (6 euro-pallet, 6 rollcontainer), semillas 11/23/37, 84 episodios únicos.
- Decisión: no avanzar con esta configuración; test final no abierto (`campaign_closure.md`).
- Evidencia y límites: etiquetado con hasta cuatro candidatas frente a hasta 142 legales en despliegue; `Q_hat` de continuación Greedy; intento abortado en `learning_training_aborted_missing_checkpoint_dir/`; estabilidad null.
- Artefactos reutilizables: etiquetas, seis checkpoints, `learning_packing/`, código de pérdidas y agregación.

Comprobación: las tres medias coinciden exactamente con `learning_packing/aggregate.json` tras releer `effective_u_geom` por pedido y semilla. No se reejecutaron métodos.

## 4. Selección PPO de reglas

- Pregunta y contrato: PPO elige entre tres reglas geométricas con presupuesto reducido (`paper/studies/rl_rule_selection/protocol_frozen.json`, SHA256 `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`).
- Resultado principal (recalculado desde capturas y `rule_counts`): la política determinista eligió `greedy_best_fit` en 1577 de 1577 decisiones por semilla (101/102/103); en 120 de 120 parejas el plan guardado coincide con Greedy (ítem, `flb_mm`, dimensiones orientadas y no colocados); RL−referencia = 0; puerta false, false, true, true, true.
- Decisión: configuración cerrada; se detiene la búsqueda experimental de mejora algorítmica en estas configuraciones (`campaign_closure.md`).
- Límites: observaciones de train no guardadas; no auditoría exhaustiva de cada update; no inferioridad general de RL.
- Artefactos: checkpoints, desarrollo 360 casos, intentos abortados de harness conservados aparte.

## 5. Estado conjunto

Todas las campañas anteriores permanecen cerradas. Este estudio `learning_objectives` no las reabre. Los 17 `transitions_*.pkl` históricos siguen sin seguimiento y no se abrieron.
