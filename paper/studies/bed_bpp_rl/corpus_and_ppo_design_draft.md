# BED-BPP-RL: corpus y demostración PPO — borrador

## Pregunta
¿Cómo ofrecer interacción y experiencias reproducibles a partir de BED-BPP
para estudiar RL con observabilidad, acciones, retornos y coste explícitos?

## Evidencia existente
Preflight: 4 pedidos, 16 episodios, 648 transiciones; verificación desde
artefactos y copia portable. No constituye demostración de aprendizaje.

## Muestra propuesta, todavía no seleccionada
16 pedidos train: 8 euro-pallet y 8 rollcontainer.
8 pedidos evaluation: 4 euro-pallet y 4 rollcontainer.
Selección determinista, disjunta por pedido y firma geométrica.
Excluir los cuatro pedidos del preflight y los tests reservados históricos.
Auditar fuentes de exclusión antes de emitir IDs.
No afirmar independencia absoluta por ausencia de exposición registrada.

## Corpus inicial propuesto
Cuatro políticas de comportamiento en los 16 pedidos train:
tres reglas fijas y uniforme con semilla declarada; máximo 64 episodios.
Los episodios de evaluación se conservan en un conjunto separado.
No utilizar evaluación para ajustar normalización, pérdidas o hiperparámetros.
No transformar experiencias heurísticas en supuestas experiencias PPO.

## Demostración PPO propuesta
CPU, observación y acciones del entorno BED-BPP-RL.
Tres semillas; idéntico cupo inicial de 2048 decisiones por semilla.
Checkpoint final, sin escoger mejor semilla ni seleccionar por evaluación.
PPO genera experiencias nuevas durante interacción; el corpus inicial
no se presenta como entrenamiento offline de PPO.
Persistir observación, máscara, acción, reward, cierre y metadatos de política.
Datos auxiliares necesarios para auditar PPO se especificarán antes del ajuste.
Arquitectura, optimizador, rollout y demás hiperparámetros siguen pendientes
de especificación y pruebas sintéticas; no se heredan sin revisión.

## Evaluación prevista
Política determinista final de cada semilla en los mismos 8 pedidos eval.
Referencias internas: tres reglas fijas y uniforme.
Informar todos los resultados, sin exigir superar Greedy como condición
para validar el recurso y sin inferir superioridad general.
Pedidos y semillas son niveles distintos; no tratar pasos como réplicas.

## Presupuesto operativo propuesto, no demostrado
Corpus inicial: 600 segundos.
Entrenamiento: 600 segundos por semilla, sin ampliar automáticamente.
Evaluación: 600 segundos.
Si el reloj impide completar el cupo, registrar cobertura e incompletitud.
No comparar como presupuestos iguales semillas con cupos distintos.
Medir fases y RSS; cuatro pedidos no demuestran cola de tiempos.

## Verificaciones antes de avanzar
G1: contrato y exportación completos; preflight ya verificado.
G2: selección, esquema y ejecutores sintéticos verificados antes del corpus.
G3: entrenamiento finito, política auditable y experiencias consistentes.
Si G3 falla, detener antes de evaluación.
G4: episodios de evaluación y lectura portable verificados.
Cambiar tensores no demuestra aprendizaje eficaz; registrar además
probabilidades y acciones antes/después sobre observaciones train fijadas.
No exigir un signo favorable para documentar funcionamiento del recurso.

## Manuscrito
Contribución candidata: entorno, corpus verificable y uso efectivo por PPO.
Pendientes: demostración RL, caracterización, disponibilidad y relevancia.
Sin promesa de novedad, superioridad ni aceptación editorial.
