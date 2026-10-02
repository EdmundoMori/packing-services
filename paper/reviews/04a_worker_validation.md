# 04A — validación de los resultados del worker

Origen: `research/paper-online-packing` en `150c2f731e267b9a1938ee02123ef3bf86bcd843`. El piloto no se ejecutó. No hubo inferencia, entrenamiento, commit ni push.

## Resultado del proceso

`invoke_worker()` ya no acepta un archivo de resultado solo porque exista. Un código de salida distinto de cero es un fallo de worker aunque el payload parezca válido. Un JSON ilegible, un payload que no es un objeto o una estructura sin `status` reconocible también lo son. El motivo queda en la fila y la evidencia diagnóstica en `worker.json`: código de salida, texto rechazado o payload rechazado. La captura no se puntúa. `U_geom` efectivo es 0 y la corrida sigue con los demás método/pedido. No hay reintentos.

Un error interno del evaluador no se convierte en un caso exitoso. Si la lectura del resultado se puede clasificar, queda como fallo de ese caso. Una excepción no prevista deja la corrida marcada como incompleta.

## Contraste con el snapshot

Cada caso recibe el snapshot del preflight. Antes de aceptar la captura se compara con ese snapshot, no con otra sección de la propia captura: pedido, método, identidades de ítems sin duplicados, dimensiones originales eje a eje, pesos, autorización de orientaciones, identidades y dimensiones de contenedor eje a eje, peso máximo, restricciones, p/s y los parámetros efectivos. La tolerancia numérica es 1e-6, la ya usada en peso y volumen. Dos contenedores con el mismo volumen y ejes distintos no se aceptan.

Esa discrepancia es salida inválida: `input_mismatch`, `U_geom` efectivo 0, evidencia en la auditoría y continuación de la corrida. La auditoría geométrica y la de peso se mantienen. La métrica, los pedidos, el orden, el tiempo límite y la permanencia de los fallos en el denominador no cambian.

## Cómo queda registrado cada fallo

- `nonzero_exit`: el proceso terminó con código distinto de cero. La fila lleva `worker_failure` y `method_failure`.
- `unreadable_json`: el archivo de resultado no es JSON. Se conserva un extracto del texto.
- `invalid_result`: el JSON no es un objeto o no trae la estructura esperada.
- `timeout`: el límite de 300 segundos se agota.
- `input_mismatch`: la captura no coincide con el snapshot. Puede convivir con una geometría internamente coherente; no se confunde con un ítem sin candidata ni con una violación de peso.
- `geometry_invalid` y `weight_violation`: siguen siendo las auditorías anteriores.

En todos esos fallos el `U_geom` efectivo es 0 y el caso permanece entre los 20.

## Comprobaciones

Los 42 tests de `paper/tests` pasaron con workers simulados. El preflight real, repetido el 2026-10-02T17:05:45Z con `--preflight-only`, volvió a aceptar los 20 pedidos y no cargó el checkpoint. `paper/results/04_internal_pilot` no existe. El protocolo 03 sigue con `pilot_executed=false`.
