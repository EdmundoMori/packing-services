# Etiquetas del piloto de aprendizaje

Corrida única, terminada, sin entrenamiento. Código de salida 0. Estado `completed`.

## Comando

```text
.venv/bin/python paper/studies/counterfactual_ranking/tools/run_learning_labels.py \
  --protocol paper/studies/counterfactual_ranking/learning_protocol_frozen.json \
  --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json \
  --output paper/studies/counterfactual_ranking/learning_labels
```

El protocolo congelado es `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`. El borrador no se reescribió. No se consultó el test final y no se usaron los 20 pedidos del diagnóstico.

## Contrato

Las 17 columnas de `counterfactual-actor-v1` se calculan desde el contenedor, el estado ya colocado, el ítem actual y la candidata. El sufijo queda solo en el campo de auditoría `suffix_ids_not_an_actor_input`, fuera del vector. La arquitectura `Linear(17, 64) → ReLU → Linear(64, 1)` y el ajuste de 40 épocas con semillas 11, 23 y 37 están congelados y no se ejecutaron. La normalización se ajustó con las 368 filas candidatas de los estados completos de train. Una columna constante usa denominador 1. Al releer esas filas, la media y la escala difieren del archivo guardado como máximo en 9.99e-16, el redondeo decimal del JSON.

## Cobertura

Los 36 pedidos se inspeccionaron. Cada uno aportó 4 estados etiquetados. Todos están completos. No hay estados incompletos, retornos desconocidos, fallos ni pedidos pendientes.

| Split | Target | Pedidos | Estados con elección en la trayectoria | Estados etiquetados | Continuaciones |
| --- | --- | ---: | ---: | ---: | ---: |
| train | euro-pallet | 12 | 660 | 48 | 187 |
| train | rollcontainer | 12 | 359 | 48 | 181 |
| development | euro-pallet | 6 | 291 | 24 | 94 |
| development | rollcontainer | 6 | 177 | 24 | 91 |
| Total | | 36 | 1487 | 144 | 553 |

El techo era 144 estados y 576 continuaciones. Se etiquetaron 144 estados y 553 continuaciones: 23 huecos corresponden a estados con menos de cuatro candidatas legales, no a trabajo omitido. Los índices coinciden con la regla de cuantiles. No hay claves duplicadas de pedido, estado y acción.

Las 553 capturas reproducen `Q_hat`. `physical_stability_verified` queda null. Frente a la continuación Greedy del mismo estado hay 74 ventajas positivas, 392 ceros y 87 negativas. Esas cifras no modifican el protocolo ni se usan como puerta de entrenamiento.

## Tiempo

La pared fue 1378.8725992719992 segundos, dentro de 14400. Por separado: adquisición de trayectorias 88.067 s, continuación 846.946 s, captura 0.164 s y auditoría 438.771 s. La suma de fases no es coste de CPU.

## Integridad

No hay discrepancia de retorno, de índice ni de split. La puerta de desarrollo no se aplica: no hay actores entrenados. Incumplirla, cuando se evalúe, significará no avanzar con esta configuración.
