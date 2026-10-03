# Revisión de diseño

## Decisiones

Se reutilizan el contrato compacto, `GreedyBestFit`, la captura, la auditoría independiente, el snapshot del motor y los hashes. El snapshot no incluye el sufijo y copia cajas y puntos por referencia. El diagnóstico guarda una copia profunda y la tupla de identificadores restantes, y vuelve a localizar la candidata por geometría. La continuación vive en este estudio porque el recorrido compacto existente siempre empieza desde cero. No se modifica `src/` ni el selector de la campaña cerrada. No se usa el teacher de horizonte recesivo.

La muestra sale de `full.val` después de retirar identificadores registrados como observados o usados en entrenamiento, calibración o selección. El orden es determinista. La regla de clones está en el código y en el borrador, y se aplicó antes de dar por preparada la lista. No aparecieron clones en el tramo necesario para completar los veinte.

## Límites

- No hay independencia absoluta. `full.val` ya fue origen de otras muestras. Los 17 pickle no se abrieron, así que un pedido presente solo dentro de ellos no quedó excluido. Tampoco se leyeron los cuerpos de las auditorías ni los identificadores que aparezcan solo en prosa.
- El protocolo 14 no embebe los cincuenta identificadores; se recuperaron por el directorio de casos. El protocolo 10 no excluía el scale test; esta selección sí lee esas listas.
- Los archivos `val_order_ids_full.json` vivo e histórico no se usan como exclusión: son el pool, no una lista de uso.
- Quedan 637 euro-pallet y 763 rollcontainer. Del pool de 1500 se retiran 100.
- Los estados son de trayectorias Greedy. Un margen aquí no demuestra un selector desplegable.
- Un retorno desconocido no es una etiqueta 0. Los estados incompletos se conservan y no entran en las ventajas.
- `Q_hat` no es óptimo. El mejor de cuatro no es una cota global.
- La estabilidad física no está verificada.

## Presupuesto

La estimación estática cuenta como máximo 20 × 5 estados y 100 × 4 continuaciones, recortados a 100 y 400. Cada continuación restaura, aplica una acción, sigue con Greedy y después se audita. No se midió ese coste sobre pedidos reales. El timeout propuesto es 60 s para la continuación, con la auditoría aparte. El reloj de 14400 s puede cerrar la corrida antes del peor caso serial de 24000 s. Esas cifras esperan la revisión posterior al preflight.

El preflight usa `00109938` y `00105640`, un estado y dos alternativas. Son cuatro continuaciones como máximo y 900 s de reloj. Consumen presupuesto y no rehacen la muestra.

## Puerta propuesta, pendiente de revisión

No se entrena aunque aparezca margen. Antes del diagnóstico completo hay que aceptar o cambiar estos umbrales:

- Cobertura: al menos 15 de 20 pedidos con un estado completo y al menos 40 estados completos. Pide observación en los dos targets sin sostener la decisión en unos pocos pedidos.
- Margen: la media, con igual peso por pedido, de la fracción de estados completos con alguna ventaja positiva es al menos 0.25. Por debajo, superar a Greedy sería poco frecuente en estos estados.
- Magnitud: cada pedido aporta la mediana de sus ventajas positivas, o 0 si no tiene ninguna. La media de esos veinte valores es al menos 0.01 de `U_geom`. Ese uno por ciento del contenedor queda por encima de un empate numérico, y la mediana más el cero limitan el efecto de un solo estado.
- Coste: menos del 5 % de las continuaciones previstas con retorno desconocido, y la corrida dentro de las 14400 s.

No es un contraste estadístico. No convierte el máximo por estado en rendimiento de un método.
