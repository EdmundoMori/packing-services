# Protocolo congelado: valor relativo de colocaciones alternativas

Este documento congela la campaña de desarrollo. El borrador `protocol_draft.json` no se modifica. El hash de este protocolo es distinto del borrador; la equivalencia exigida es semántica.

## Pregunta

¿Existe un margen aprovechable para aprender a ordenar candidatas legales mediante las consecuencias de acciones alternativas, en lugar de copiar una elección del teacher?

Es un estudio exploratorio de desarrollo. No es confirmatorio. No hay garantía de que un margen observado sea aprendible. No reproduce LOLS, AggreVaTe, PCT, GOPT ni OPAL.

## Contrato

El mismo contrato geométrico del borrador: secuencia original, un contenedor del target propio, `p=s=1`, hasta seis permutaciones, contención y no solape, peso y estabilidad inactivos, parada en el primer ítem sin candidata y continuación Greedy sobre el sufijo real. `U_geom` es el volumen colocado partido por el volumen fijo del contenedor. `physical_stability_verified` queda `null`.

El diagnóstico es privilegiado. No es un baseline online ni una cota superior.

## Muestra y selección

Los 20 pedidos de `sample_manifest.json`, diez por target, en el orden ya registrado. Hasta cinco estados con elección por pedido y hasta cuatro candidatas por estado, incluida Greedy, con la selección determinista ya diseñada. Máximo de 100 estados y 400 continuaciones, contando el preflight.

## Presupuesto truncado

Se acepta que el peor caso no cabe en cuatro horas. La pared global es 14400 segundos e incluye el preflight, la carga, la generación de estados, la restauración, la continuación, la captura, la auditoría y la escritura. Cada continuación nueva dispone de 60 segundos para restaurar y continuar, y de otros 60 para capturar y auditar. Los dos plazos quedan subordinados al reloj que reste. Al agotarse, se detienen los trabajos nuevos y se registra lo pendiente. No se reduce la muestra, no se sustituyen pedidos, no se amplía el presupuesto y no hay reintentos selectivos.

## Preflight

`00109938` y `00105640` ya tienen cuatro retornos observados. Si el contrato, el dataset, el estado, el sufijo, la acción y el código de continuación coinciden, esas continuaciones se referencian y se cuentan una sola vez. El resto de alternativas y los estados posteriores se completan siguiendo la trayectoria Greedy.

## Puerta

Los umbrales se propusieron antes del preflight y se adoptan ahora.

Un estado completo exige captura auditada y `Q_hat` conocido en todas las alternativas previstas, incluida Greedy. Una ventaja positiva es `A_hat > 1e-9`. Para cada pedido con estados completos, `f_i` es la fracción de esos estados en los que alguna alternativa supera a Greedy, y `m_i` es la mediana de las ventajas positivas de las alternativas evaluadas en esos estados, o 0 si no hay ninguna. Las medias dan el mismo peso a cada pedido evaluable.

1. Al menos 15 pedidos con un estado completo y al menos 40 estados completos.
2. Media de `f_i` mayor o igual que 0.25.
3. Media de `m_i` mayor o igual que 0.01.
4. Menos del 5 % de retornos desconocidos entre las continuaciones programadas de los estados capturados, incluidas las pendientes por presupuesto.
5. Pared acumulada dentro de 14400 segundos.

Los estados no capturados y los pedidos sin cobertura se informan aparte. No cuentan como ausencia de margen.

Cobertura o integridad insuficiente: inconcluso. Cobertura suficiente con la puerta de margen incumplida: no avanzar. Todas las condiciones: margen suficiente para diseñar el experimento de aprendizaje. Esa última clase no autoriza entrenamiento automático ni demuestra una mejora online.
