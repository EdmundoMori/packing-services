# 12 — entrenamiento de la ablación de normalización

Entrenamiento terminado el 2026-10-03 sobre `836a4a55ae729b62077db0adf670e8dc8a49b25a`, rama `research/paper-online-packing`. El manifiesto de `paper/results/11_normalization_ablation/` está completo. No hubo packing ni un segundo entrenamiento. No hay commit ni push.

La verificación nueva está en `paper/results/11_normalization_ablation/training_verification.json`. Los checkpoints y el manifiesto generado no se reescribieron. No hay discrepancias ni valores no finitos.

## Diez modelos

Cada fila es un ajuste. La `val_acc` es la del epoch elegido por menor `val_loss`. Ninguna semilla representa al brazo.

| Semilla | Brazo | best_epoch | best_val_loss | val_acc |
| --- | --- | --- | --- | --- |
| 42 | raw | 3 | 2.6537529745955397 | 0.33146067415730335 |
| 42 | normalized | 4 | 2.5025232845472694 | 0.3455056179775281 |
| 43 | raw | 10 | 2.754664874158203 | 0.32303370786516855 |
| 43 | normalized | 3 | 2.5110633372665343 | 0.36235955056179775 |
| 44 | raw | 3 | 2.683919194593942 | 0.3146067415730337 |
| 44 | normalized | 2 | 2.5203212713145815 | 0.36235955056179775 |
| 45 | raw | 10 | 2.6588890784409607 | 0.3258426966292135 |
| 45 | normalized | 4 | 2.4856905410098906 | 0.33707865168539325 |
| 46 | raw | 7 | 2.647412235861686 | 0.32303370786516855 |
| 46 | normalized | 8 | 2.4720713668117407 | 0.34831460674157305 |

Un `val_loss` menor no dice nada sobre el packing. Esta tabla no aplica la regla de avance.

## Emparejamiento

En las cinco semillas los dos brazos comparten el hash de pesos iniciales y las mismas diez permutaciones. Cada permutación recorre las 1006 transiciones de train. La igualdad de tensores iniciales la comprobó `torch.equal` al entrenar. Esta lectura posterior compara los hashes y los índices guardados; no reconstruye esos tensores ni ejecuta forward.

## Dependencias de la ejecución

Commit `836a4a55ae729b62077db0adf670e8dc8a49b25a`.

- `online_policy_ml/src_ml/train_mlp.py`: `874d8f667439ef3609a067588b87b6664c21cf8a156c2e6f5c2d27ff8f03e19d`
- `src/packing_services/online/features.py`: `69885b32bb019ae90bcb65637db3cc357b91aaa635f779bb86c8c012cbd2d702`
- `online_policy_ml/src_ml/config.py`: `09b52b3ffaa80b28036e7a8d20b0cf46d9a3d6da9bc4b407af49d3032145f656`

Los hashes de datos, estadísticas, protocolo y congelado coinciden con los archivos actuales. El protocolo 10 sigue con el entrenamiento marcado como no ejecutado en sus campos históricos.

## Evidencia

La carpeta ocupa 1045517 bytes. El archivo mayor es un pairing de 110045 bytes. Los diez checkpoints pesan entre 46779 y 46849 bytes.

## Limitaciones

No hay packing ni comparación con GreedyBestFit. La muestra de desarrollo no se ha usado. La identidad histórica del archivo BC respecto del checkpoint de producción sigue no comprobada.
