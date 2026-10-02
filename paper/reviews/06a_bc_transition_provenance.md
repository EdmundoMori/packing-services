# 06A — IDs de las transiciones BC

HEAD de trabajo: `4112c5b6f97c2e9e5712090379bb9bfcf8993b12` en `research/paper-online-packing`. Se leyeron solo `online_policy_ml/data/train/transitions_p1s1.pkl` y `online_policy_ml/data/val/transitions_p1s1.pkl`, cada uno en un proceso aparte, con `pickle.load` y un límite de 120 s. El SHA256 coincidió antes y después. No hubo entrenamiento, inferencia, commit ni push.

## IDs demostrados en los archivos actuales

Los dos objetos son dict con las claves de `collect_dataset`. Cada transición tiene `order_id`, `step`, `features`, `label`, `n_options` y `label_volume`. La primera fila de train tiene 6 vectores de ancho 35. Esos vectores no se copian aquí.

| Archivo | Bytes | SHA256 | Transiciones | IDs declarados |
| --- | --- | --- | --- | --- |
| `data/train/transitions_p1s1.pkl` | 12868929 | `e2080aeac0ff787489c7d4ba3302e04135a39711dab4ec210b40d397a115e6e4` | 1006 | 24, sin duplicados |
| `data/val/transitions_p1s1.pkl` | 3322081 | `21c6837d96c1c6bf2b6a57d85f7b6aca23d09990fb4a69ab127c7663ebee671c` | 356 | 8, sin duplicados |

Train: `00100463`, `00101060`, `00101462`, `00101694`, `00101750`, `00101904`, `00101960`, `00102415`, `00102791`, `00102884`, `00104471`, `00104763`, `00105094`, `00105561`, `00106336`, `00106775`, `00106895`, `00106942`, `00107147`, `00107701`, `00108482`, `00108624`, `00108712`, `00109288`.

Val: `00101450`, `00101506`, `00104020`, `00104335`, `00105244`, `00106072`, `00106539`, `00109074`.

El campo `n_transitions` coincide con el número de filas. El `order_id` de cada fila coincide, como conjunto y como lista de ids únicos en el orden del manifiesto, con `order_ids` y con `data/train/order_ids.json` o `data/val/order_ids.json`. `per_order` guarda `bed-bpp-` más ese mismo id: es el `request_id` que escribe `collect_order_transitions` en las estadísticas. `collect_dataset` sustituye el `order_id` de la fila por el id del manifiesto y deja `per_order` como estaba. `fit_mlp` consume las filas.

Esos 32 ids son la evidencia A sobre los archivos vigentes. El cruce con los 1499 de `full.test` es 0 en euro-pallet y 0 en rollcontainer. La intersección con el val de selección PPO (`data/scale/val`) también es vacía. Los 8 ids de val son el conjunto de selección BC ya identificado en el paso 06.

## Identidad histórica

B. `artifacts/reports/02_transitions.json` registra 24 pedidos y 1006 transiciones en train, y 8 y 356 en val, para p=1 s=1. El notebook 03 imprimió `train p1s1 1006 | val 356`. Esos conteos coinciden con los archivos vigentes. El informe no lista los ids.

C. La identidad entre estos archivos y los que vio el ajuste BC queda **no comprobada**. `02_transitions.json`, `03_validacion.json` y los notebooks 02 y 03 no contienen un SHA256 del pickle. El hash de la revisión 06 se calculó en esta campaña sobre el archivo ya presente. No se reconstruye una cadena criptográfica hacia atrás. La marca de tiempo no se usa.

## Cruce con candidatos

No aparece ningún id de `full.test` en las filas leídas. No se añade una exclusión nueva por este cruce. Se mantienen las anteriores: 4 euro-pallet archivados y 5 rollcontainer entre archivo incierto y evaluación histórica. `00108193` sigue en esa evaluación histórica.

| Target | n | Entrenamiento registrado | Selección registrada | Evaluación histórica | Archivo incierto | Cruce con estos pickle | Ausencia en lo inspeccionado | Exclusión positiva | Abiertos con identidad histórica no comprobada |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| euro-pallet | 679 | 0 | 0 | 0 | 4 | 0 | 675 | 4 | 675 |
| rollcontainer | 820 | 0 | 0 | 1 | 5 | 0 | 815 | 5 | 815 |

La ausencia está comprobada en los manifiestos, informes y estos dos pickle. La independencia absoluta no queda declarada: falta el ancla histórica del archivo. Los 675 y 815 abiertos siguen con esa incertidumbre.

## val_loss y val_acc

La llamada de `fit_mlp` en el notebook 03 no pasa `select_best`. El default de `train_mlp.py` es `val_loss`. `artifacts/reports/03_validacion.json` guarda `select_best=val_loss` para p1s1, con `best_epoch` 3. El párrafo del informe 02 nombra la rama `val_acc`, que solo actúa si el argumento es `val_acc`. Esa rama no es la de esta llamada. `fit_mlp_numpy` sí prioriza `val_acc`, y el notebook solo entra ahí si falta torch. La salida guardada y el campo `select_best` del informe corresponden a la ruta torch. Hay una sola configuración registrada para esta corrida: `val_loss`. El informe 02 no se reescribe.

## Rutas posibles

Quedan abiertas las dos, sin elegir:

- Evaluar el actor vigente y declarar que los ids de los pickle actuales están leídos y que su identidad con la corrida BC histórica no tiene hash.
- Entrenar más adelante un actor nuevo, con los datos y los hashes congelados en el momento del ajuste, si hace falta una cadena trazable de punta a punta.

La falta de ese hash no demuestra contaminación. El informe de PPO registra `best_epoch` 0 y el paso 06 comprobó que los tensores vigentes coinciden con el BC. Este paso no presenta ese actor como una mejora obtenida por PPO. No se elige N ni se ajusta el modelo.
