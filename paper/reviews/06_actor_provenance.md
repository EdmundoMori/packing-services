# 06 — procedencia del actor y candidatos de ambos targets

HEAD de trabajo: `4112c5b6f97c2e9e5712090379bb9bfcf8993b12` en `research/paper-online-packing`. Este paso no entrena, no infiere y no elige N. El protocolo del piloto y `paper/results/04_internal_pilot/` quedan como estaban. Los `.pkl` no se deserializan.

Tres niveles de evidencia se mantienen separados. **A** es lo que el código prescribe. **B** es lo que una ejecución dejó escrito. **C** es lo que se demuestra sobre los archivos evaluados en este paso.

## Cadena del checkpoint

1. Etiquetas. **A:** `collect_dataset` escribe un pickle con `order_ids`, transiciones y `order_id` en cada fila (`online_policy_ml/src_ml/collect.py`). **B:** el notebook `02_etiquetas_maestro.ipynb` lee `data/train`, `data/val` y `data/test`, registra 24/8/8 pedidos y guarda `transitions_p1s1.pkl` en esas carpetas. La salida impresa cuenta 1006 transiciones de train p=1 s=1. **C:** los dos pickle que esa llamada usaría siguen en disco. Su contenido de pedidos no se ha leído.

2. BC. **A:** `fit_mlp` ajusta `mlp_v1` y conserva el estado de menor `val_loss`. **B:** el notebook `03_imitacion.ipynb` carga `transitions_path("train", 1, 1)` y `transitions_path("val", 1, 1)` y exporta `artifacts/models/mlp_v1_p1s1.pt`. `artifacts/reports/03_validacion.json` registra `best_epoch` 3, `select_best=val_loss` y esa ruta. **C:** el archivo carga con `weights_only=True` como contrato `packing-services-online-policy` v1, `mlp_v1`, `feature_version` 1, `hidden_size` 64. El epoch que produjo esos tensores no está guardado dentro del archivo.

3. PPO. **A:** `fit_ppo` clona el actor de `init_path` antes del bucle. `best_epoch` empieza en 0 y solo cambia si una época posterior supera la utilización media de validación en más de `1e-12`. El estado elegido se exporta con `export_mlp_pt`. **B:** el notebook `05_rl_ppo.ipynb` inicializa con `mlp_v1_p1s1.pt`, entrena con `data/scale/train/order_ids.json`, selecciona con `data/scale/val/order_ids.json` y exporta `mlp_v1_p1s1_ppo.pt`. La salida impresa es 80 train, 20 val y 6 epochs. `artifacts/reports/05_rl_ppo.json` registra `best_epoch` 0, `best_val_util` 0.6874582 e `init_path` igual al BC. Hay otro informe, `artifacts/reports/05_ppo.json`, con `best_epoch` 5 y la misma ruta de salida. Su marca de tiempo de archivo es anterior a la del `.pt` vigente.

4. Producción. **A:** `model_path_mlp_ppo_production(1, 1)` apunta a `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt`. **C:** ese es el archivo comparado aquí. `versions/v1` y `versions/v2` guardan otros cortes. Un manifiesto archivado demuestra exposición del actor actual solo cuando hay una relación registrada con este archivo.

## Comparación exacta de pesos

Carga permitida: `torch.load(..., map_location="cpu", weights_only=True)` sobre los dos `.pt` locales. Los dos documentos son dict con `state_dict`. Las claves son `0.weight` (64, 35), `0.bias` (64,), `2.weight` (1, 64) y `2.bias` (1,), todas `float32`. Cada par coincide en clave, forma, dtype y valores (`torch.equal`). Resultado: **igualdad comprobada**.

Los SHA256 de archivo difieren (`0c17dc62e9a9fcb10ae1bfe2b1e02113977f9730c348c8d84daa214f11870aa6` el BC, 12037 bytes; `6139beb5c13c6a3f9c701626a1765cf690234f253c2a9b9e4c03185b0228ec24` el PPO, 12077 bytes). La igualdad de tensores se juzga sobre los valores, no sobre el hash del archivo. Los metadatos escalares coinciden: formato, versión 1, backend `torch`, arquitectura `mlp_v1`, `feature_version` 1, `hidden_size` 64. No hubo forward ni escritura de `.pt`.

Esa igualdad es lo que la regla `best_epoch=0` exporta a partir del inicializador. El informe `05_rl_ppo.json` registra esa selección. El informe `05_ppo.json` registra otra selección sobre el mismo nombre de ruta y queda como ejecución anterior: sus tensores de la época 5 no están en un archivo aparte para compararlos con el documento vigente.

## Datos de entrenamiento y de selección

El BC del actor evaluado consumiría, según el notebook 03:

| Papel | Ruta | Bytes | SHA256 |
| --- | --- | --- | --- |
| Train p=1 s=1 | `online_policy_ml/data/train/transitions_p1s1.pkl` | 12868929 | `e2080aeac0ff787489c7d4ba3302e04135a39711dab4ec210b40d397a115e6e4` |
| Val p=1 s=1 | `online_policy_ml/data/val/transitions_p1s1.pkl` | 3322081 | `21c6837d96c1c6bf2b6a57d85f7b6aca23d09990fb4a69ab127c7663ebee671c` |

El esquema documentado por `collect_dataset` incluye `order_ids` y `order_id` por transición. Eso es **A**. Esos campos no se leyeron. La identidad de pedidos dentro del pickle queda sin demostrar.

Las copias archivadas del mismo nombre tienen el mismo tamaño y otro SHA256 (`7e6ce3bf…` y `df6f5719…`). Bytes distintos: el archivo v1 no es el pickle vigente de esas rutas. El notebook 05 no carga pickles; lanza rollouts sobre los ids de `data/scale/train` y elige con `data/scale/val`.

Manifiestos que esas llamadas leen hoy, cruzados con los 1499 ids de `full.test`:

- Entrenamiento registrado: `data/train/order_ids.json` y `data/scale/train/order_ids.json`. Cruces: 0 en euro-pallet y 0 en rollcontainer.
- Selección registrada: `data/val/order_ids.json` y `data/scale/val/order_ids.json`. Cruces: 0 y 0.

El cruce vacío con esos cuatro manifiestos vigentes deja la independencia sin demostrar, porque el pickle sigue cerrado y el informe de entrenamiento no guarda el hash del archivo.

## Candidatos por target

`full.test` tiene 1499 pedidos: 679 euro-pallet y 820 rollcontainer. Cero sin target. La evaluación futura no queda limitada a euro-pallet. `called_clean` y `called_contaminated` quedan en false. N no se elige.

| Target | n | Entrenamiento registrado | Selección registrada | Evaluación histórica | Cruce archivado incierto | Evidencia faltante | Sin cruce en las fuentes leídas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| euro-pallet | 679 | 0 | 0 | 0 | 4 | 679 | 675 |
| rollcontainer | 820 | 0 | 0 | 1 | 5 | 820 | 815 |

Los cuatro euro-pallet archivados están en `versions/v1` scale train (manifiesto y `scale_split`): `00101249`, `00102764`, `00108147`, `00109619`. Sigue vigente la exclusión por precaución. Es un cruce archivado. No es un entrenamiento demostrado del actor vigente: el manifiesto scale train que lee el notebook 05 no los contiene.

Rollcontainer, cruce archivado de train v1: `00100348`, `00104068`, `00108237`, `00109274`. El quinto, `00108193`, está en el val scale v1 y también en `artifacts/reports/05_ppo.json` (rutas `mlp_v1_p1s1.pt` y `mlp_v1_p1s1_ppo.pt`), en la copia v1 de ese informe, en `versions/v2/artifacts/reports/05_ppo.json` y en `05_step.json` (este último con `mlp_v1_p3s2.pt` y el actor STEP). El informe `05_rl_ppo.json`, el de la selección `best_epoch=0`, no lo lista. `00108193` ocupa a la vez evaluación histórica y cruce archivado.

Los 675 y los 815 sin cruce en las fuentes leídas permanecen dentro de evidencia faltante, igual que los nueve ids con algún cruce. La ausencia en un informe no certifica independencia.

## Comprobación que falta

Para fijar una reserva defendible falta abrir, en un paso posterior, los dos pickle p=1 s=1 de `data/train` y `data/val` y contrastar su campo `order_ids` con los manifiestos, más un anclaje del hash de esos archivos en el momento del ajuste. Hasta entonces el cruce archivado v1 y la evaluación histórica de `00108193` se conservan aparte del entrenamiento demostrado del archivo vigente. Este paso no fija N, ni pedidos finales, ni un umbral, y no modifica el actor después del piloto.
