# BED-BPP-RL — diseño operativo PPO (borrador, no autorización)

Base publicada indicada por el usuario: 5d41b8d4ede5cdeddc19e4eb6561da6d83b76c72.
Este documento propone decisiones antes de implementar el ejecutor. No congela
el protocolo ni autoriza corpus industrial, entrenamiento o evaluación.

## Objetivo y evidencia
Demostrar uso de un recurso BED-BPP para interacción PPO, registro verificable
y ejecución CPU con coste explícito. No demostrar superioridad algorítmica.
Pruebas comunicadas: 12 del núcleo y 9 de integración sintética, todas OK.
Muestra draft: 16 train, 8 evaluation; preflight separado (16 episodios).

## Configuración propuesta
- Semillas 101, 102 y 103, todas informadas; CPU, ejecución serial.
- Un hilo Torch y uno de interoperación por proceso.
- Actor-crítico compartido: Linear(36,64), Tanh, actor Linear(64,3),
  crítico Linear(64,1). Actor final a cero: distribución inicial uniforme.
- Escalas de observación fijas del entorno; sin normalización ajustada con eval.
- gamma=lambda=1; ventajas centradas/divididas por desviación poblacional;
  desviación cero da ventajas cero, una vez sobre el rollout completo.
- Adam lr=3e-4, weight_decay=0, betas=(0.9,0.999), eps=1e-8;
  amsgrad/foreach/fused=false. Clip PPO 0.2; entropía 0.01;
  coeficiente de valor 0.5 aplicado a 0.5*MSE; sin clipping del valor;
  clip de gradiente L2 0.5; cuatro épocas, minibatch 64.
- 2048 decisiones por semilla; rollouts de 128 decisiones: 16 actualizaciones
  y 128 pasos Adam si el presupuesto se completa sin fallos.
- RNG separados y registrados para inicialización, acciones, orden de pedidos
  y permutaciones de minibatches. No reutilizar el corpus fijo como datos PPO.

## Pedidos y composición del rollout
Recorrer permutaciones completas de los 16 pedidos train; generar cada vuelta
antes de ejecutarla usando el RNG de orden. Un rollout puede abarcar episodios,
pero utiliza una única versión de la política y del crítico. Coleccionar
segmentos hasta 128 decisiones; calcular GAE en cada segmento con sus cierres,
concatenar los lotes y normalizar ventajas una sola vez en update.
Un episodio abierto al borde del rollout continúa después del update: se
conserva su estado, pero las nuevas acciones/valores usan la nueva política.
El borde del rollout no es truncación del episodio ni retorno completo.
No inventar pasos para pedidos con cero transiciones. Si una vuelta completa
produce cero decisiones, detener por ausencia de progreso.

## Cierre y tiempo
Cupo de entrenamiento: 600 s por semilla, sin transferencia ni ampliación.
Al reset, decision_budget = decisiones restantes de la semilla; así el paso
2048 cierra como truncación si no hay fin natural, con observación bootstrap.
Una terminación natural coincidente conserva prioridad.
El reloj incluye preparación, carga, colección, verificación, update y guardado.
El ejecutor debe comprobarlo entre fases y un supervisor debe imponer el límite:
no describir comprobaciones cooperativas como timeout duro.
Si interrumpe una fase, conservar el estado incompleto y el último checkpoint
confirmado; no llamar completo al cupo ni reanudar automáticamente.
Toda fila usada por Adam se persiste y verifica antes del update. Una colección
incompleta al vencimiento no se usa para un update extra fuera del reloj.
Persistir también filas no utilizadas y marcar su estado explícitamente.

## Artefactos necesarios
Por update: checkpoint de comportamiento (modelo y hash), RNG de acciones
antes/después, segmentos PPO audit-v1, lote derivado, verificación previa,
permutaciones, pérdidas/gradientes, checkpoint posterior y estado de Adam.
Un manifiesto con rutas relativas, tamaños y SHA256 relaciona esos artefactos;
archivo incompleto o no confirmado no cuenta como update íntegro.
Registrar captura y snapshot por episodio con auditoría AABB/volumen; los
registros PPO no sustituyen esa auditoría geométrica. Conservar episodios
incompletos con cierre honesto; physical_stability_verified permanece null.
Los checkpoints intermedios respaldan auditoría, no selección por rendimiento.

## Pruebas pendientes del ejecutor
Rollout 128 atravesando resets; GAE sin fuga entre episodios; continuidad de
estado con nueva política; cupo final con truncación y prioridad natural;
cero transiciones; lectura portable; recomposición de lote y log_prob desde
checkpoint; interrupción antes/durante update y archivos no confirmados.
No ejecutar entrenamiento industrial hasta pasar estas pruebas y publicar
protocolo operativo, hashes de implementación y manifiesto de muestra.

## Evaluación y paper
Solo tras integridad del entrenamiento: 8 pedidos evaluation, 3 políticas PPO
finales y 4 referencias internas (56 episodios). Uniforme: semilla 20261007,
una realización por pedido; no estimación precisa de su rendimiento esperado.
Corpus fijo: 64 episodios train, uniforme con semilla 20261006, sin ajuste PPO.
Cupos propuestos corpus/evaluation: 600 s cada fase, pendientes de implementación.
Informar cobertura, retorno, cierre, diversidad de acciones, tiempo y memoria.
Comparar probabilidades antes/después sobre observaciones train registradas;
esto describe cambio de política, no prueba por sí solo aprendizaje eficaz.
Paper: metodología puede describirse como diseño; resultados PPO siguen pendientes.
No condicionar la validez técnica del recurso a batir Greedy ni prometer publicación.
