# Anexo operativo del piloto PPO

Este anexo queda escrito antes del primer update. El JSON congelado es `protocol_frozen.json`, SHA256 `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`.

## Redes

El actor es Linear(36, 64), ReLU, Linear(64, 3). El último peso empieza en cero y el sesgo en [1, 0, 0]. El crítico es otra red Linear(36, 64), ReLU, Linear(64, 1), con la última capa a cero. La entrada es la observación ya definida, sin ítems futuros, sin identificadores y sin el número de ítems restantes.

## Optimización

gamma = 1 y lambda = 1. El clip de PPO es 0.2. La entropía entra con coeficiente 0.01 y el valor con 0.5. Hay cuatro épocas por rollout y minibatches de 128 transiciones. El recorte de gradiente usa la norma 2 con máximo 0.5.

La pérdida de valor es el error cuadrático medio. No hay clipping del valor. El coeficiente 0.5 multiplica esa pérdida fuera del error cuadrático.

Las ventajas se normalizan una vez sobre las 512 transiciones del rollout, con los valores de la recogida, antes de partir minibatches. Se resta la media y se divide por la desviación poblacional. Si esa desviación es cero, el lote normalizado es el vector centrado y queda en cero.

Adam usa estos parámetros efectivos:

```json
{
  "lr": 0.0003,
  "betas": [
    0.9,
    0.999
  ],
  "eps": 1e-08,
  "weight_decay": 0.0,
  "amsgrad": false,
  "maximize": false,
  "foreach": null,
  "capturable": false,
  "differentiable": false,
  "fused": null,
  "decoupled_weight_decay": false
}
```

## Datos y corte

Cada actualización consume un rollout nuevo de 512 decisiones. No se reutilizan rollouts antiguos. La log_prob antigua se conserva separada del grafo. Una actualización son las cuatro épocas; cada una hace cuatro pasos de Adam, dieciséis por actualización y 192 si la semilla termina.

El reloj se consulta antes de cada decisión y antes de cada actualización. Un rollout que no llega a 512 no se actualiza. El estado recuperable es el último checkpoint de un update terminado, más el checkpoint inicial. Una semilla que agota el reloj guarda ese estado y no se reintenta.

El calendario ordena los identificadores y aplica una permutación reproducible. No ordena por longitud. Si el rollout corta un episodio, el retorno usa el valor del estado siguiente y el mismo entorno continúa. Un final real no usa bootstrap. No hay recompensas nuevas.

CPU, dos workers como máximo y un hilo de Torch por worker. Tres generadores independientes comparten el número de semilla: uno para el calendario, otro para las acciones y otro para las permutaciones de las épocas.

La auditoría exhaustiva no entra en el rollout. Al cierre de cada semilla se audita la última captura de un episodio terminado, si existe. Las comprobaciones legales del motor siguen activas en cada decisión.
