# Protocolo congelado de selección de reglas

Estado: congelado antes del primer update del piloto. No es una preregistración confirmatoria. No afirma convergencia ni publicabilidad. `physical_stability_verified` permanece null.

SHA256 de este JSON hermano: `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`.

## Presupuesto

Semillas 101, 102 y 103. Cada una tiene 6144 decisiones, doce rollouts de 512 y 4800 segundos. El entrenamiento global tiene 14400 segundos. Una decisión es cada llamada real a `step`, también si las tres reglas proponen la misma colocación. El límite anterior de 1000 episodios no es el criterio. El presupuesto no usado no se reasigna.

El corte sustituye al techo de 60000 decisiones por el tiempo del preflight, medido antes de este entrenamiento. El bucle más lento hizo 98 decisiones en 62.830 segundos, 0.641 segundos por decisión. A esa tasa, 60000 decisiones superan las cuatro horas de un worker y 6144 quedan dentro de los 4800 segundos con margen. U_geom no intervino en el corte. Cuatro pedidos no caracterizan el resto de train.

Si una semilla no completa las 6144 decisiones y las doce actualizaciones, la campaña queda incompleta. Esas semillas no se comparan como ajustes de igual presupuesto.

## Qué se conserva

Las tres reglas, la observación de 36 entradas, los 128 pedidos de train, el contrato compacto y las escalas fijas. El actor empieza con logits [1, 0, 0]. No se cargan checkpoints históricos.

## Desarrollo

Hay 40 pedidos, veinte por target, elegidos por el mismo hash y separados de train, de los pedidos ya observados y de los clones. Sus episodios no se ejecutan y no se calculan estadísticas. El test final no se selecciona ni se consulta.

## Puerta

La puerta queda escrita y no se aplica. Es una puerta de ingeniería. La regla de referencia será la de mayor media en desarrollo, con desempate al menor índice si la diferencia absoluta no supera 1e-12. La aleatoria uniforme usa las semillas 101, 102 y 103. OnlineBPH queda como comparación externa posterior y no se llama PCT aprendido.
