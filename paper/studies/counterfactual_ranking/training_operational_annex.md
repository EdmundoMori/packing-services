# Anexo operativo del ajuste

Este anexo fija, antes del primer paso de Adam, lo que el protocolo congelado no separaba del emparejamiento. No cambia pérdidas, datos ni hiperparámetros, y no sustituye a `learning_protocol_frozen.json`.

## Actualización

Hay un solo paso de Adam por época. El objetivo de la época es la media aritmética, en float32, de las pérdidas de todos los estados de train. `optimizer.zero_grad(set_to_none=True)` precede a esa media. Después se recorta la norma 2 del gradiente a 1.0 y un valor no finito aborta esa pareja. No hay minilotes ni early stopping.

## Orden dentro de la media

El protocolo fija la media de todos los estados y prohíbe buscar una política de barajado. Para que los dos brazos de una semilla acumulen en el mismo orden, cada época usa una permutación de `torch.randperm` obtenida de un `torch.Generator` de CPU inicializado con esa semilla. La permutación solo ordena la suma. No es un hiperparámetro elegido después de ver el resultado.

## Softplus

El término de preferencia usa `softplus` con umbral 40, el mismo corte que la pérdida de referencia en Python. Por encima de 40 el valor se devuelve tal cual; por debajo de −40 coincide con el exponencial hasta la resolución de float32.

## Retornos y logits

La tolerancia de empate `1e-9` se aplica a los retornos en float64. Los logits, los pesos y Adam están en float32. Así un empate definido en el protocolo no depende de que float32 pueda representar `1e-9`.

## Desempate de la evaluación

La candidata elegida es la de mayor logit. Si varios logits son exactamente iguales, se elige el menor índice original dentro del estado. El desempate no usa `Q_hat` ni la identidad de Greedy. El regret es el máximo `Q_hat` examinado menos el `Q_hat` de esa candidata.

## Normalización

Las medias y escalas guardadas con las etiquetas se aplican una vez, al construir los tensores. No se recalculan durante las 40 épocas. Los dos brazos reciben esos mismos tensores.

## Lo que no se hace

No se reescribe el protocolo congelado. No se excluyen los estados cuyos retornos son todos iguales. No se comparan entre sí los valores numéricos de las dos pérdidas. No se elige época, semilla ni configuración a partir del ranking.
