# Diseño resumido — BED-BPP-RL (R01→R02)

## Pregunta

¿Cómo transformar pedidos industriales BED-BPP en un recurso reproducible de
interacción y experiencias para estudiar políticas de RL, manteniendo explícitos
la observabilidad, las acciones, los retornos y el presupuesto computacional?

## Estado

- **R01:** diseño y reutilización.
- **R02:** implementación sintética verificada (`BedBppRlEnv` + corpus atómico +
  verificador). Decisión:
  `implementacion_sintetica_verificada_para_disenar_preflight_real`.

## Respuesta implementada (sintético)

Reutilizar reglas/encoder de `rl_rule_selection` sin mutar artefactos hasheados;
adaptar wrappers en `bed_bpp_rl/tools/` con motor EP **post-C04**, reward
\(\Delta V/V_{\mathrm{bin}}\), \(\gamma=1\), terminated/truncated separados, y
corpus con campos agente vs auditoría.

## Próximo paso (no ejecutado en R02)

Diseñar preflight real medido antes de fijar tamaños/presupuestos y generar
experiencias industriales.
