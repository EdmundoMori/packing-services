# 03A — el piloto conserva el target de cada pedido

Origen: `research/paper-online-packing` en `3ec56590d9ef59446f9b2bb46c66a1c459bbc378`. No se ejecutó packing.

## Conflicto detectado

El protocolo 03 exigía un único contenedor EURO_PALLET de 1200×800×2000 mm para los 20 pedidos de `scale.val`. Al leer los targets, 13 son rollcontainer y 7 son euro-pallet. El subconjunto y el dataset fuente coinciden. La conversión `_resolve_target_container` no sustituye el target: un rollcontainer sale como 800×700×2000 mm. Forzar el pallet habría cambiado el problema. Por eso el protocolo 03 quedó bloqueado y no eliminó pedidos.

## Cambio previo a resultados nuevos

03A retira solo ese bloqueo. Los 20 ids y su orden se mantienen. Cada pedido usa el contenedor de su target registrado. Euro-pallet y rollcontainer tienen volúmenes distintos, 1920000000 mm³ y 1120000000 mm³. `U_geom` divide por el volumen del contenedor de ese pedido.

La segunda lectura de fuente y subconjunto no encontró targets distintos. El peso máximo efectivo es 1500 kg en los dos targets, porque `_resolve_target_container` asigna `DEFAULT_PALLET_MAX_WEIGHT_KG` en ambos. Las banderas de `3D_BPP` tampoco cambian con el target: no solape, contención, rotación y peso máximo activos; estabilidad básica, load-bearing, fragilidad y secuencia de descarga en false.

El agregado primario queda fijado antes de ejecutar: media aritmética de los 20 `delta_i`, mismo peso por pedido, más el desglose obligatorio por target. Ese número describe esta mezcla de 7 y 13 pedidos. No se reinterpretará después eligiendo otro agregado.

## Condiciones que siguen pendientes

El evaluador piloto todavía no existe y no se ha ejecutado. `best_epoch=0` sigue siendo la selección del actor inicial, no una mejora demostrada mediante PPO. La estabilidad física no está verificada: las banderas correspondientes permanecen apagadas.

La reserva confirmatoria queda como en el paso 03. Los cuatro ids con cruce en el train scale de `versions/v1` siguen excluidos por precaución. Los 675 candidatos con exposición incierta no se declaran limpios. No se elige N y no se abren `.pkl` ni checkpoints.

## Alcance

La comparación, cuando se implemente, es interna: el actor seleccionado y `GreedyBestFitPolicy` sobre las mismas candidatas, la misma máscara y el mismo problema convertido. No autoriza una frase de superioridad frente a un método externo ni una afirmación de generalización.
