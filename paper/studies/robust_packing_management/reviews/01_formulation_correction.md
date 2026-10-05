# Revisión 01 — corrección de formulación

**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2` · rama `research/paper-online-packing`
**AGENTS.md:** ausente
**Ejecutado:** solo documentación. Sin simulación, packing, muestras, train, commit, push.
**Sin tocar:** campañas cerradas, `src/`, pickle, checkpoints.

## Cambios de formulación

1. **B** pasa a candidata operativa: incertidumbre dimensional sintética + revelación **exacta** tras éxito.
2. **A** queda como baseline/referencia de garantía (protección calculable).
3. Alcance inicial **solo dimensiones**; pose/deformación/estabilidad/trayectoria/recovery inactivos.
4. Tabla de información antes/después fijada; filtraciones prohibidas listadas.
5. Modelo generativo: relación \(\phi\), positividad, ejes/orientación sin remuestreo, B1 vs B2 conceptual; **sin** fijar distribución ni niveles numéricos.
6. Acción = menú de protección; chooser fijo; envolvente por inflación + mismo FLB; eventos `stop_no_conservative_candidate` ≠ `geometric_failure`.
7. Objetivo primario **recomendado: Obj-B**; riesgo separado; sin coeficientes PPO.
8. Baselines B0/B1u/B1a/B1d/B2h + etiqueta oracle; RL solo post-G2.
9. G1 rediseñado como preflight sintético de integridad; G2 diagnóstico de oportunidad — **ninguno ejecutado ni autorizado**.

## Necesidad de RL

Secuencialidad y posible POMDP (B2) **no** demuestran que RL sea mejor. B1 puede colapsar a cuantil/regla; B2 a adaptación \(\hat\theta\). Residual: **sin demostrar**.

## Decisión

**`listo_para_preflight_sintetico`**

Interpretación: la formulación ya no bloquea el **diseño** de G1; **no** autoriza ejecutar G1 ni entrenar. Una pasada futura debe autorizar explícitamente el preflight.
