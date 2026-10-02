# 10 — diseño de la ablación de normalización

Congelado el 2026-10-02 sobre `557e2ef477e6173cee20fae5f83c435d59652d76`, rama `research/paper-online-packing`. No hubo entrenamiento, forward ni packing. No hay commit ni push.

La evaluación independiente sigue no concluyente. Esta muestra es de desarrollo y no la confirma.

## Qué queda comparado

Dos BC nuevos, con las mismas 1006 transiciones de train y las mismas 356 de val. El brazo A deja las 35 características como están. El brazo B les aplica la estandarización ajustada solo con las 40231 filas candidatas de train. Las 23 transiciones de una sola candidata permanecen.

Los hashes, leídos antes y después, coinciden con 06A:

- train `e2080aeac0ff787489c7d4ba3302e04135a39711dab4ec210b40d397a115e6e4`
- val `21c6837d96c1c6bf2b6a57d85f7b6aca23d09990fb4a69ab127c7663ebee671c`

La identidad histórica de esos archivos respecto del checkpoint sigue no comprobada.

## Hiperparámetros efectivos

La llamada del notebook 03 para p=1 y s=1 pasa `hidden_size=64`, `epochs=10`, `lr=mlp_lr(1, 1)=0.001` y, en la corrida histórica, `seed=42`. `fit_mlp` aporta `clip_grad=1.0`, `weight_decay=1e-4`, `select_best="val_loss"`, `keep_epochs=False`, `require_informative=True` y `require_val=True`. El informe `03_validacion.json` registra esa selección por `val_loss`. Su `best_epoch=3` no se copia: cada ajuste elige de nuevo el menor `val_loss`.

Adam, en torch 2.14.0+cpu, conserva `betas=(0.9, 0.999)`, `eps=1e-8` y `amsgrad=False`. Las semillas de la ablación son 42, 43, 44, 45 y 46. Las cinco entran en el promedio. CPU, con un hilo de cómputo y un hilo de interoperación fijados una vez para los dos brazos. La corrida histórica no fijaba hilos; aquí el control es compartido para que los brazos no dependan del valor de la máquina.

## Quince columnas, no trece

En train y en train+val la desviación poblacional es 0 en las mismas quince columnas: `item_can_rotate`, `bin_index_n`, `buffer_index_n` y las doce `preview_*`. El diagnóstico 09 escribe «13» en la hipótesis 2 y a la vez enumera esas quince. No hay columnas constantes distintas entre train y train+val. El diagnóstico 09 no se ha reescrito. Esas columnas se conservan; si la desviación no supera `1e-12`, el denominador pasa a ser 1.

Hash de las estadísticas: `9a8604afe01455e5cd1e075ec32f408d42c464e1256173b0c970a7b15c69e266`.

## Muestra

`full.val` tiene 680 euro-pallet y 820 rollcontainer. La unión de exclusiones tiene 440 ids. Dentro de `full.val` salen 49: 8 de val BC, 20 de scale val, 15 del scale train archivado en v1 y 6 del scale val archivado en v1. Quedan 662 y 789. Se toman 25 y 25.

Hash de la lista: `f2b969649484166fe02052fbd26c09ba25337f898b74e17ff4ba86db2fd4ae69`.

Los 20 ids de scale test no tienen una lista de evaluación histórica que los identifique. No se han excluido por ese motivo y no están en `full.val` ni en los 50.

## Regla de avance

Para cada semilla, la media de `U_geom` normalizado menos `U_geom` raw en los mismos 50 pedidos. Se informan las cinco diferencias y su promedio, y cada brazo frente a GreedyBestFit. La heurística se ejecuta una vez por pedido. Se sigue con esta configuración si el promedio normalizado-raw es positivo, la diferencia es positiva en al menos cuatro semillas y el promedio del brazo normalizado frente a GreedyBestFit es positivo. Si falla, se abandona esta configuración. No se ensayan variantes dentro del mismo experimento.

## Archivos

- `paper/tools/normalization_features.py`
- `paper/tools/freeze_normalization_sample.py`
- `paper/tools/freeze_normalization_ablation.py`
- `paper/protocols/10_normalization_ablation.json`
- `paper/protocols/10_normalization_ablation.md`
- `paper/results/10_normalization_freeze.json`
- `paper/tests/test_normalization_ablation.py`
