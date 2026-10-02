# Anexo operativo del evaluador piloto

Este anexo cierra decisiones de ejecución. No cambia la métrica, la muestra ni las restricciones del protocolo `03_internal_pilot.json` (ajuste 03A). No marca ese protocolo como ejecutado.

La regla vigente es 03A: cada pedido conserva su target. No se aplica el bloqueo a rollcontainer de `pilot_orders()` en `audit_confirmatory_reserve.py`.

## Ejecución

- El tiempo límite es de 300 segundos por método y pedido. Incluye el arranque del worker y la carga del modelo.
- Hay una sola ejecución por método y pedido. No hay reintentos selectivos.
- Actor y heurística corren en CPU.
- El actor no muestrea y queda en modo de evaluación según el loader existente: `TorchMlpV1Backend` llama a `model.eval()` al cargar, y `LearnedPlacementPolicy.decide` elige por argmax.
- El orden es el del manifiesto: dentro de cada pedido, primero el actor y después la heurística.
- El tiempo es diagnóstico. No permite afirmar mayor eficiencia.

## Preflight

Antes de cualquier inferencia se comprueban los hashes registrados del dataset fuente, del subconjunto de validación, del manifiesto y del checkpoint. El dataset fuente y el subconjunto se identifican por separado. `--preflight-only` no carga el checkpoint.

Un fallo de preflight aborta la corrida completa.

## Corrida

Cada método y pedido usa un proceso nuevo, con estado nuevo y el mismo camino de conversión, generador y máscara. El algoritmo de producción no se copia. Se conservan las dimensiones orientadas reales. Un fallo de método no detiene los demás casos.

## Métricas

`U_geom` es el volumen colocado, con dimensiones verificadas, dividido por el volumen del contenedor de ese pedido. `delta_i` es la diferencia actor menos heurística. El agregado primario es la media aritmética de los 20 delta, con el mismo peso por pedido. La mediana, con un número par de pedidos, es la media de los dos valores centrales. El empate es `abs(delta) <= 1e-9`.

Crash, timeout o salida inválida dejan `U_geom` efectivo en 0. Las métricas brutas se conservan cuando pueden calcularse. Esos casos siguen en el denominador. Una solución parcial válida no es un fallo.

No se usa `feasible` del motor como certificado. `physical_stability_verified` permanece null.
