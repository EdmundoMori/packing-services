# R09 — Corpus inicial industrial BED-BPP

## Procedencia
HEAD de ejecución: f808147918d35dcb6c16f4fb0e1840487232912f.
Fase de corpus bajo protocolo congelado; sin entrenamiento PPO.

## Resultados
64 episodios confirmados y auditados; 2360 transiciones.
64 terminaciones naturales; cero truncaciones.
Verificación posterior desde disco: verified.
Auditoría de identidad, orientación, volumen, contención y no solape.
physical_stability_verified permanece null.

## Coste registrado
Trabajador: 83.63347693800006 segundos.
Supervisor: 88.08378875000017 segundos; límite 600 segundos.
Sin timeout ni reinicio automático.
ru_maxrss del trabajador: 707216 KB, máximo del proceso completo
en Linux/WSL, no memoria incremental ni suma de procesos.

## Alcance científico
Experiencias de tres reglas fijas y selección uniforme sobre 16 pedidos train.
No son experiencias PPO ni entrenamiento offline de PPO.
Se respalda generación e integridad del corpus bajo este contrato y muestra.
No se afirma representatividad general, estabilidad física,
mejora de política, superioridad ni novedad establecida.
Los ocho pedidos de evaluación no se ejecutaron en esta fase.

## Decisión
Fase inicial de corpus completada.
Continuar con implementación y congelación de la demostración PPO;
su entrenamiento y evaluación siguen pendientes.
