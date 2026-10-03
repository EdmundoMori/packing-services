# Borrador: valor relativo de colocaciones alternativas

Este documento es un borrador. Tiene decisiones pendientes de revisión. No es un protocolo congelado ni un preregistro.

## Pregunta

¿Existe un margen aprovechable para aprender a ordenar candidatas legales mediante las consecuencias de acciones alternativas, en lugar de copiar una elección del teacher?

Es una hipótesis nueva. No reproduce LOLS, AggreVaTe, PCT, GOPT ni OPAL, y no hereda sus garantías.

## Contrato

Se reutiliza el contrato geométrico del paso 16: secuencia original, un contenedor del target propio, `p=s=1`, hasta seis permutaciones, contención y no solape. Peso, estabilidad y load-bearing permanecen inactivos. El episodio se detiene en el primer ítem actual sin candidata legal; el sufijo no se coloca ni se descarta para seguir. `U_geom` es el volumen colocado dividido por el volumen fijo del contenedor. `physical_stability_verified` queda `null`.

Estos resultados no se mezclan con protocolos que descartaban un ítem y continuaban.

## Observabilidad

El diagnóstico puede mirar el sufijo real del pedido. Es un diagnóstico privilegiado de entrenamiento y desarrollo. No es un baseline online homologado, no es una solución óptima y no es evidencia de superioridad online. No usa el teacher `receding_horizon_ep`.

`Q_hat(s,a)` es el `U_geom` de una continuación concreta con GreedyBestFit. No es un valor óptimo. El mejor de cuatro candidatas no es una cota superior global. La selección de candidatas queda fijada antes de observar retornos.

Los estados salen de trayectorias Greedy. El diagnóstico no prueba que un selector nuevo mejore episodios completos ni que funcione en los estados que él mismo visitaría.

## Muestra

Pool: `full.val`, 1500 pedidos, SHA256 `530b1f623f19867f5a178564180d77667597c43d491a0eff1596f1615f8df2b5`. Dataset `bed-bpp_v1.json`, SHA256 `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`.

Tras las fuentes inspeccionadas quedan 637 euro-pallet y 763 rollcontainer. Salen 100 identificadores del pool. No se declara independencia absoluta.

La ordenación es el SHA256 UTF-8 de `counterfactual-v1|20261003|` + `order_id`. Se toman los diez primeros de cada target. La firma de clon es el SHA256 del JSON canónico del snapshot compacto, antes de colocar. En este recorrido no hubo clones descartados. La lista, el orden y las firmas están en `sample_manifest.json`, cuyo SHA256 es `149d5f09b53652374d9af0d4a67ad9601d78c51aa11bc6c53fb5b630eee78120`.

Ejecución prevista: los diez euro-pallet y después los diez rollcontainer.

## Diagnóstico previsto

Como máximo cinco estados por pedido con al menos dos candidatas legales, y cuatro alternativas por estado. La de Greedy entra siempre. Las otras buscan una orientación nueva y, entre ellas, la posición más lejana. Un timeout o un fallo dejan `Q_hat` en null. Un estado solo produce etiquetas si todas sus continuaciones previstas son válidas. No hay reintentos selectivos.

## Presupuesto propuesto

Tope: 100 estados y 400 continuaciones. Timeout de 60 s por continuación, con la auditoría cronometrada aparte. Reloj global propuesto: 14400 s. El producto 400 × 60 s es 24000 s, así que el reloj puede cerrar la corrida antes de agotar todos los timeouts. Estas cifras son topes, no una medición de la calibración anterior, y quedan pendientes de revisión después del preflight y antes del diagnóstico completo.

## Preflight

El primer euro-pallet (`00109938`) y el primer rollcontainer (`00105640`), con un estado y dos alternativas cada uno. Cuenta dentro de los 20 pedidos y del presupuesto. No puede cambiar la muestra.

```
/home/edmundo/packing-services/.venv/bin/python /home/edmundo/packing-services/paper/studies/counterfactual_ranking/tools/run_preflight.py --protocol /home/edmundo/packing-services/paper/studies/counterfactual_ranking/protocol_draft.json --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json --output /home/edmundo/packing-services/paper/studies/counterfactual_ranking/preflight_results
```

Ese comando no se ha ejecutado.

## Análisis

Antes de ejecutar queda fijado qué se contará: estados y alternativas válidas, fracción de estados completos con alguna alternativa por encima de Greedy, magnitud del margen positivo, resultados por pedido y target con igual peso por pedido, diversidad de orientación y posición, coste de la etiqueta separado de la captura y la auditoría, cobertura, fallos y la distribución de las diferencias, ceros incluidos.

Los estados de un mismo pedido no son observaciones independientes. El máximo por estado no es el rendimiento de un método desplegable. No se afirma que unas características predigan los retornos.

## Puerta propuesta

Sigue pendiente de revisión. No autoriza entrenamiento automático. La justificación está en `design_review.md`.
