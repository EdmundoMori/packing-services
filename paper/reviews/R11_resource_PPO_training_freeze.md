# R11 — Congelación de la demostración PPO

Seis pruebas sintéticas correctas; corpus inicial verificado antes del freeze.
Fase autorizada: entrenamiento PPO. Evaluación no autorizada.

Semillas: 101, 102, 103, ejecución serial.
2048 decisiones por semilla; rollouts de 128.
16 actualizaciones y 128 pasos Adam si se completa cada cupo.
Límite externo: 600 segundos por semilla, sin transferencia de tiempo
ni reinicio automático. Un fallo detiene el lanzamiento de semillas siguientes.
Checkpoint final confirmado; sin selección por rendimiento.

Experiencias PPO nuevas: el corpus de reglas no se usa para updates.
Probes sobre observaciones train visitadas; cambio de probabilidades
no demuestra por sí solo aprendizaje eficaz.
Auditoría AABB; physical_stability_verified permanece null.

Archivo protocolo:
26b04cfa8dfab735d376cc5dc09a6073d21a7c9e037db3449b7bb4b067505ceb
Digest interno:
45d28e939f42d2364c6f6ded9397f1cf78f16ba1912346aed2df25a41784557f

Entrenamiento industrial todavía no ejecutado.
Presupuesto y eficacia todavía no demostrados.
