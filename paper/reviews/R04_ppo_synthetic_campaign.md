# R04 — Núcleo, recolector y campaña PPO sintética

## Base
Rama: research/paper-online-packing.
HEAD de ejecución: 5d41b8d4ede5cdeddc19e4eb6561da6d83b76c72.

## Comprobaciones comunicadas
12 pruebas del núcleo, 9 del recolector y 6 del ejecutor: todas correctas.
Campaña sintética: 256 decisiones recopiladas y entrenadas,
2 actualizaciones confirmadas, 16 pasos Adam y 86 episodios iniciados.
Continuidad entre actualizaciones: 1. Episodio final abierto: false.
Pared registrada: 3.4524500479999745 segundos.

La verificación posterior confirmó 2 actualizaciones y 256 filas,
comprobando hashes y correspondencia de experiencias con el lote guardado.

## Evidencia
ppo_synthetic_validation_01/: 102 archivos, 809482 bytes,
7 archivos .pt, sin temporales según el inventario.
Mayor archivo: update_001/after.pt, 54930 bytes.

## Alcance
Solo problemas sintéticos; no pedidos industriales BED-BPP.
No demuestra mejora de política, convergencia ni superioridad.
No se reprodujeron los pasos Adam en la verificación posterior.
No se realizó auditoría geométrica de campaña.
physical_stability_verified permanece null.
El límite temporal del ejecutor es cooperativo, no timeout duro.

## Decisión
Integración PPO sintética verificada para continuar la implementación.
Protocolo operativo todavía en borrador.
Pendientes: auditoría geométrica, supervisor de tiempo e integración industrial.
No autoriza entrenamiento o evaluación industrial.
