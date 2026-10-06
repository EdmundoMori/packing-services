# Diseño resumido — BED-BPP-RL (R01)

## Pregunta

¿Cómo transformar pedidos industriales BED-BPP en un recurso reproducible de
interacción y experiencias para estudiar políticas de RL, manteniendo explícitos
la observabilidad, las acciones, los retornos y el presupuesto computacional?

## Respuesta de diseño (sin resultados empíricos nuevos)

Reutilizar el entorno de **selección entre tres reglas** ya implementado en
`rl_rule_selection`, bajo el contrato compacto moncontenedor, con motor EP
**post-C04**, reward incremental de volumen nominal / volumen del bin y
\(\gamma=1\) para que el retorno no descontado coincida con \(U_{\mathrm{geom}}\)
en episodios completos. Versionar un **corpus de transiciones** distinto de
capturas de packing y de etiquetas \(Q_{\hat{}}\).

## Alcance

- Acción: índice de regla \(\{0,1,2\}\); identidades preservadas.
- No segundo espacio de acciones en el recurso inicial.
- No protocolo robótico oficial BED-BPP; `physical_stability_verified=null`.
- No apertura de test; no selección de IDs en R01.

## Próximo paso autorizado (fuera de R01)

Implementación de wrappers `bed_bpp_rl/tools/`, freeze del contrato, preflight
medido y generación controlada de experiencias.
