# 11 — ejecutor de la ablación de normalización

Implementado el 2026-10-02 sobre `158c5dc0b6c02b50a638f2678cd05482cecd5052`, rama `research/paper-online-packing`. No se entrenó ni se empaquetó la muestra real. No hay commit ni push.

El protocolo `paper/protocols/10_normalization_ablation.json` y el congelado `paper/results/10_normalization_freeze.json` siguen intactos. La carpeta `paper/results/11_normalization_ablation/` no se ha creado.

## Emparejamiento

Para cada semilla, cada brazo llama a `fit_mlp` después de `torch.manual_seed`. El algoritmo de `fit_mlp` no cambia. En `paper/` un envoltorio observa tres cosas y devuelve el resultado original:

- el `state_dict` justo después de `build_mlp_v1`;
- cada `torch.randperm` de epoch;
- el dtype de cada entrada al modelo.

La igualdad de pesos es `torch.equal` en todos los tensores. El hash inicial es el SHA256 de, en orden de clave, `clave|forma|dtype|` en UTF-8 seguido de los bytes contiguos del tensor. El hash de permutaciones es el SHA256 del JSON UTF-8 de la lista de índices, con `separators=(",", ":")` y sin espacios. Si una semilla no coincide, la etapa queda incompleta y se detiene. No se descarta esa semilla ni se elige otra.

La corrida histórica no fijaba hilos. Aquí, una vez por proceso y antes del trabajo con torch, quedan `torch.set_num_threads(1)` y `torch.set_num_interop_threads(1)`. Los dos brazos comparten ese proceso.

Las estadísticas salen del congelado. El ejecutor comprueba su hash canónico y no vuelve a ajustarlas. `FEATURE_NAMES` se compara con el encoder de producción. Las características entran al modelo en float32, como ya hace `fit_mlp`. La selección es el menor `val_loss` estricto; se conserva el primer mínimo. `keep_epochs` sigue en falso, así que el índice se contrasta con la historia y no se guardan los pesos de cada epoch.

## Artefacto

Cada modelo nuevo vive en la carpeta de la ejecución. El formato es `packing-services-research-normalization-ablation`. El loader de investigación usa `torch.load(..., map_location="cpu", weights_only=True)` y rechaza otro formato, otro orden de columnas, otra regla de selección o un hash de estadísticas distinto. La serialización que se hashea es el JSON canónico guardado en el propio artefacto.

El loader de producción exige `packing-services-online-policy`. Un artefacto de esta ablación no cumple ese contrato. Un checkpoint normalizado no puede usarse como si sus entradas fueran crudas.

## Etapas

A. Entrenamiento de los diez modelos. Rechaza la carpeta si ya existe. Un corte deja el manifiesto en `incomplete` y conserva lo escrito. No hay reintento selectivo.

B. Packing, solo con el entrenamiento completo y los diez artefactos verificados. Son 550 casos: 500 de los actores y 50 de GreedyBestFit. La heurística se ejecuta una vez por pedido. La conversión, las candidatas y la máscara son las de producción. La política es `LearnedPlacementPolicy` y el bucle es `run_online_loop`. La captura y `evaluate_outcome` son los del evaluador anterior. Un fallo entra con `U_geom=0` y permanece en el denominador.

La agregación informa las cinco medias de `U_geom(normalizado) - U_geom(raw)`, su promedio, cada brazo frente a GreedyBestFit y el desglose por target. Evalúa las tres condiciones de avance. No elige semilla y no produce una conclusión confirmatoria.

## Comandos futuros

Entrenamiento:

```
cd /home/edmundo/packing-services
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_normalization_ablation.py train --protocol /home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json --freeze /home/edmundo/packing-services/paper/results/10_normalization_freeze.json --output /home/edmundo/packing-services/paper/results/11_normalization_ablation
```

Packing, después de esa carpeta completa:

```
cd /home/edmundo/packing-services
CUDA_VISIBLE_DEVICES= /home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/tools/run_normalization_ablation.py pack --protocol /home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json --freeze /home/edmundo/packing-services/paper/results/10_normalization_freeze.json --run-dir /home/edmundo/packing-services/paper/results/11_normalization_ablation --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json
```

## Cobertura de las pruebas

Las pruebas usan transiciones sintéticas y, en el emparejamiento real, tres epochs. La etapa real leerá diez epochs del protocolo; esa lectura está comprobada y no se ha ejecutado. El plan de 550 casos se construye desde el protocolo congelado. El packing de prueba es un pedido sintético de dos ítems. No se abren los pickle BC ni el checkpoint histórico. La orquestación de los diez archivos usa un ajuste sustituido para no lanzar las cinco semillas reales; el emparejamiento de verdad queda en la prueba que llama a `fit_mlp`.

## Archivos

- `paper/tools/ablation_contract.py`
- `paper/tools/ablation_train.py`
- `paper/tools/ablation_pack.py`
- `paper/tools/ablation_aggregate.py`
- `paper/tools/run_normalization_ablation.py`
- `paper/tests/test_ablation_runner.py`
