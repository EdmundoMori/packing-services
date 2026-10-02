# 10 — ablación de normalización congelada

Protocolo de desarrollo. No está ejecutado. No entrena ni empaqueta. No confirma el paso 08 y no certifica estabilidad física.

La comparación tiene dos brazos de BC nuevo. El brazo A usa las 35 características originales. El brazo B usa esas mismas 35 características estandarizadas. La transformación de características es la única intervención experimental. Etiquetas, orden de candidatas, hiperparámetros, semillas y presupuesto quedan emparejados.

## Datos

Transiciones BC ya auditadas en el paso 06A:

- `online_policy_ml/data/train/transitions_p1s1.pkl`, SHA256 `e2080aeac0ff787489c7d4ba3302e04135a39711dab4ec210b40d397a115e6e4`, 1006 transiciones, 24 ids, 40231 filas candidatas.
- `online_policy_ml/data/val/transitions_p1s1.pkl`, SHA256 `21c6837d96c1c6bf2b6a57d85f7b6aca23d09990fb4a69ab127c7663ebee671c`, 356 transiciones, 8 ids.

Los hashes se comprobaron antes y después de la lectura de este paso y coinciden con 06A. La identidad histórica del archivo respecto de la corrida que produjo el checkpoint sigue no comprobada. Se conservan las 23 transiciones de una sola candidata: 19 en train y 4 en val.

## Hiperparámetros

Ambos brazos usan la llamada registrada para p=1 y s=1 y los defaults que esa llamada no reescribe.

Argumentos explícitos en el notebook 03, `fit_mlp(tr["transitions"], va["transitions"], hidden_size=HIDDEN_SIZE, epochs=MLP_EPOCHS, lr=mlp_lr(p, s), seed=SEED)`:

- `hidden_size=64`, `config.HIDDEN_SIZE`.
- `epochs=10`, `config.MLP_EPOCHS`. El default de `fit_mlp` también es 10.
- `lr=0.001`. `mlp_lr(1, 1)` devuelve `MLP_LR`. `MLP_LR_P3S2` queda reservado a p=3 y s=2.
- La corrida histórica usó `seed=42`, `config.SEED`.

Defaults de `fit_mlp` que el notebook no pasa:

- `clip_grad=1.0`.
- `weight_decay=1e-4`, `config.MLP_WEIGHT_DECAY`.
- `select_best="val_loss"`.
- `keep_epochs=False`.
- `require_informative=True`.
- `require_val=True`.

`artifacts/reports/03_validacion.json` registra, para el MLP p1s1, `select_best=val_loss`, `lr=0.001`, `hidden_size=64` y `seed=42`. Su `best_epoch=3` es un resultado de aquella corrida. Cada ajuste nuevo vuelve a elegir el checkpoint por `val_loss` sobre el mismo val BC del brazo.

Arquitectura `mlp_v1`: lineal 35 a 64, ReLU, lineal 64 a 1. La última capa se pone a cero después de su inicialización. Adam recibe `lr` y `weight_decay`. En torch 2.14.0+cpu quedan `betas=(0.9, 0.999)`, `eps=1e-8` y `amsgrad=False`. La pérdida es la entropía cruzada de cada transición, con características en float32.

Semillas emparejadas: 42, 43, 44, 45 y 46. Dentro de cada semilla, `torch.manual_seed` precede a la inicialización y a `torch.randperm` sobre el mismo número de transiciones. El orden por epoch, el optimizador, el presupuesto de 10 epochs, el clipping y el weight decay son los mismos. El checkpoint es el de menor `val_loss` en el val BC de ese brazo. El desempate de `val_loss` no existe: se sustituye solo cuando la pérdida es estrictamente menor. Cada semilla se informa. El promedio de las cinco representa el brazo.

CPU. `fit_mlp` no mueve el modelo de dispositivo. La corrida histórica no fija hilos. Antes de cualquiera de los dos brazos, y una sola vez en el mismo proceso, se fijan `torch.set_num_threads(1)` y `torch.set_num_interop_threads(1)`. Ningún brazo lo cambia.

## Transformación

El módulo es `paper/tools/normalization_features.py`.

- A, `raw`: identidad. Conserva el orden de las 35 columnas.
- B, `normalized`: por columna, media y desviación estándar poblacional (`ddof=0`) de las filas candidatas de train BC. Cada fila candidata pesa igual. La transformación es `(x - media) / desviación`. Si la desviación es menor o igual que `1e-12`, el denominador es 1. No se eliminan columnas ni se recortan valores. Val, los pedidos de desarrollo y los de evaluación no entran en las estadísticas.

La misma transformación se usa al entrenar y al puntuar candidatas. Un checkpoint normalizado no se entrega al loader de producción como si sus entradas fueran crudas.

Hash canónico de las estadísticas, nombres y regla de ponderación: `9a8604afe01455e5cd1e075ec32f408d42c464e1256173b0c970a7b15c69e266`.

## Columnas constantes

Con desviación poblacional menor o igual que `1e-12`, train y train+val tienen las mismas 15 columnas, todas con desviación 0:

`item_can_rotate`, `bin_index_n`, `buffer_index_n` y las doce `preview_0_*`, `preview_1_*` y `preview_2_*`.

El diagnóstico 09 dice en la hipótesis 2 «Las 13 características constantes» y, al enumerarlas, nombra esas mismas quince. No aparece un subconjunto de 13. Este protocolo no reescribe ese diagnóstico. `CONSTANT_FEATURE_STD=1e-8` de `config.py` es otro umbral de diagnóstico; estas quince también quedan por debajo porque su desviación es 0.

## Muestra de desarrollo

Cincuenta pedidos de `full.val`: 25 euro-pallet y 25 rollcontainer. Es desarrollo. No es confirmatoria. No usa `full.test` y no se evalúa en este paso.

Selección sin resultados. SHA256 UTF-8 de

`packing-study-normalization-dev-v1|20261002|TARGET|ID`

Dentro de cada target se ordena por hash y después por id, y se toman los primeros 25. El orden de ejecución es el id ascendente.

Pools de `full.val`: 680 euro-pallet y 820 rollcontainer. Tras las exclusiones quedan 662 y 789. El hash de la lista de 50 ids, con salto de línea final, es `f2b969649484166fe02052fbd26c09ba25337f898b74e17ff4ba86db2fd4ae69`.

Exclusiones aplicadas, aunque varias no intersectan `full.val`: train y val BC, train y val de scale, test de working, manifiestos v1 de working y de scale train/val, holdout de producto, los 220 pedidos ya observados y los cruces archivados del paso 06A. Dentro de `full.val` salen 49 ids: los 8 de val BC, los 20 de scale val, que son el piloto, 15 de `versions/v1` scale train y 6 de `versions/v1` scale val que no están en el scale val vivo.

`data/scale/test/order_ids.json` tiene 20 ids y no hay una lista de evaluación histórica que los identifique. No se excluyen por ese motivo. Ninguno está en `full.val` ni en la muestra.

## Geometría

Se conserva el contrato del paso 07: target propio, p=1, s=1, orden de llegada, hasta seis permutaciones, no solape, contención, rotación y peso máximo de 1500 kg. Estabilidad básica, load-bearing, fragilidad y secuencia de descarga permanecen desactivadas. Sin candidata legal se descarta el ítem y se continúa. Auditor independiente. CPU, 300 s, una tentativa. Un fallo entra con `U_geom=0` y permanece en el denominador. `physical_stability_verified` sigue nulo.

## Comparación primaria de desarrollo

Para cada semilla, la media pareada de `U_geom(normalizado) - U_geom(raw)` sobre los mismos 50 pedidos. Se informan las cinco diferencias y su promedio. También se compara cada brazo con GreedyBestFit. La heurística se ejecuta una vez por pedido si el contrato geométrico es el mismo. Las 250 observaciones pedido/semilla son cinco mediciones de los mismos 50 pedidos.

## Regla de avance

Se continúa con esta configuración solo si se cumplen las tres condiciones:

- el promedio de normalizado menos raw es positivo;
- la diferencia es positiva en al menos cuatro de las cinco semillas;
- el promedio del brazo normalizado frente a GreedyBestFit es positivo.

Es una regla de avance de ingeniería. No es una prueba estadística ni una garantía de relevancia práctica. Si no se cumple, se abandona esta configuración de normalización. No se prueban variantes retrospectivas dentro del mismo experimento.
