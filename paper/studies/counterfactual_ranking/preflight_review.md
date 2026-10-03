# Preflight de rendimiento

Corrida única del comando declarado. El borrador sigue siendo un borrador: no se ha congelado ni se ha aplicado la puerta. Los retornos de esta página no cambian la muestra, las alternativas ni la decisión de entrenar.

## Cambio de arnés anterior a la corrida

El reloj de 900 s solo se consultaba antes de empezar cada pedido. La captura y la auditoría quedaban fuera de ese presupuesto y fuera del timeout de la continuación. El arnés nuevo arma una señal de reloj sobre todo el proceso y, además, consulta el mismo plazo antes de obtener estados, antes de cada continuación, antes de capturar y antes de auditar. Si el plazo vence, `Q_hat` queda `null` con motivo `wall_clock`. El directorio de salida existente se rechaza. Dataset, manifiesto y los dos identificadores se comprueban antes de empaquetar.

Ese cambio no altera la selección, el contrato ni la puerta. Los hashes del código que llegó a ejecutarse están en `preflight_results/preflight.json`.

| Archivo | SHA256 |
| --- | --- |
| `tools/run_preflight.py` | `c7c5f418370908e43768f26ec0b1797c9fd02d6ceab6e027321c800d95e3aaf7` |
| `tools/diagnostic.py` | `8d95f84c50b15a46dcf361a303889be18ba6b8487f605f28c850fa0012f9d4aa` |
| `tools/select_sample.py` | `f3e83aa7fc3f5958587ae5eb29f91da2344e0f2442b3d03d89efff93d0220280` |
| `protocol_draft.json` | `cda879555db890f9108e4fb495cfaa7d1881bd61fa4f3e18ce950f3ca5ca84a6` |
| `sample_manifest.json` | `149d5f09b53652374d9af0d4a67ad9601d78c51aa11bc6c53fb5b630eee78120` |
| dataset | `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc` |
| `paper/tools/compact_study.py` | `93409b31b093702e80c43da4fe6030cb3913707493756f1df9296c37326af476` |
| `paper/tools/pilot_metrics.py` | `26275cea5fdcfb2ac09cd9da61bba389b2daf95a50070ef92c1f2529b25a7fad` |
| `paper/tools/pilot_problems.py` | `c347f00ab5b10bcf817954aee4ed9e12bacdaf55e128dba3c5d26f4701494b5e` |
| `paper/tools/audit_internal_solution.py` | `e3d874726260b4c84fabd963cb591075c1eefcdddc0e27057de83a8a499028ac` |

## Casos

Estado: `completed`. Pedidos ejecutados, en este orden: `00109938` (euro-pallet) y `00105640` (rollcontainer). Un estado por pedido, el primero con al menos dos candidatas. Dos alternativas por estado, la de Greedy y una orientación distinta en el mismo punto extremo inicial. No hubo sustitución de pedidos. No hubo reintento.

Cada estado parte del contenedor vacío. El sufijo guardado es la secuencia completa: 54 ítems y 42 ítems. Las dos alternativas de un pedido comparten esa geometría y ese sufijo. La primera colocación de cada captura coincide con la acción guardada. En el estado inicial, la alternativa Greedy es la continuación de referencia del episodio. `p=s=1`, un contenedor, contención y no solape activos, peso, estabilidad y load-bearing inactivos. `physical_stability_verified` es `null`.

La reauditoría de las cuatro capturas, hecha sobre el JSON guardado, no encontró fallos de geometría ni de entrada. `Q_hat` y `A_hat` recalculados coinciden con los guardados. Retornos desconocidos: 0.

| Pedido | Acción | Orientación (mm) | Empaquetados | `Q_hat` | `A_hat` |
| --- | --- | --- | --- | --- | --- |
| 00109938 | Greedy | 430 × 350 × 190 | 54 / 54 | 0.6741677083333333 | 0 |
| 00109938 | alternativa | 430 × 190 × 350 | 53 / 54 | 0.6615635416666666 | -0.012604166666666639 |
| 00105640 | Greedy | 330 × 190 × 290 | 28 / 42 | 0.5801589285714286 | 0 |
| 00105640 | alternativa | 330 × 290 × 190 | 33 / 42 | 0.6744714285714286 | 0.09431250000000002 |

Estos números son el retorno de una continuación concreta. En el rollcontainer, la otra orientación examinada queda por encima de Greedy en ese estado. Eso mide una diferencia entre las dos candidatas ya elegidas. La elección se fijó antes de ver el retorno. No es el rendimiento de una política, no muestra que un modelo pueda predecirla y no autoriza entrenamiento.

## Tiempos

Un solo proceso. Las cifras son tiempos de pared de fases sucesivas. Su suma no es un coste de CPU.

| Fase | 00109938 | 00105640 |
| --- | ---: | ---: |
| Construcción del problema | 0.173 s | 0.0006 s |
| Obtención del estado | 0.0017 s | 0.0007 s |
| Restauración y continuación Greedy | 2.618 s | 0.283 s |
| Captura Greedy | 0.0005 s | 0.0002 s |
| Auditoría Greedy | 1.097 s | 0.276 s |
| Restauración y continuación alternativa | 2.744 s | 0.407 s |
| Captura alternativa | 0.0003 s | 0.0002 s |
| Auditoría alternativa | 1.005 s | 0.449 s |

Arranque del proceso, incluida la carga y el contraste de hashes: 1.654 s. Escritura: 0.014 s. Pared del trabajo después del arranque: 9.073 s. Pared aproximada del proceso: 10.7 s. El límite de 900 s no se agotó.

La obtención del estado fue casi inmediata porque el primer ítem ya tenía seis candidatas. Esta corrida no mide el coste de caminar hasta un estado más tardío.

## Presupuesto recomendado

La extrapolación medida, si estas cuatro continuaciones fueran típicas, usa el máximo observado de continuación + captura + auditoría, 3.75 s. Cuatrocientas continuaciones a ese ritmo son unos 1500 s, del orden de media hora, más el arranque y la obtención de estados posteriores. La media de las cuatro es 2.22 s.

Dos pedidos y cuatro continuaciones no estiman la cola. El euro-pallet tardó unas siete veces más que el rollcontainer en la continuación. Un pedido más difícil puede quedar lejos de 3.75 s.

El límite global de la corrida futura sigue siendo cuatro horas, 14400 s. El preflight ya ha consumido unos 10.7 s de esa pared, 2 estados de 100 y 4 continuaciones de 400.

Timeout recomendado por continuación: 60 s para restaurar y seguir con Greedy. El máximo medido de esa fase fue 2.74 s. Otros 60 s como tope de captura y auditoría, que aquí llegó a 1.10 s. Los dos topes viven dentro de las cuatro horas: si las 400 continuaciones consumieran 60 s cada una, sumarían 24000 s y el reloj global cerraría la corrida antes de terminarlas. Con auditoría aparte al mismo tope, el peor caso es todavía mayor. El reloj de cuatro horas es el tope que manda.

La corrida completa parece viable si los tiempos se parecen a los medidos, y deja de ser una garantía si la cola se acerca al timeout. Antes de congelar el alcance hay que decidir si se acepta que las cuatro horas puedan dejar estados sin evaluar, o si se baja el número de continuaciones para que el peor caso quepa en ese reloj. Con 60 s por continuación, 240 continuaciones agotan justo las cuatro horas y todavía no incluyen la auditoría. Esta revisión no aplica ese recorte.

## Cómo se integra sin repetir

La corrida futura puede reutilizar estas cuatro continuaciones válidas si siguen coincidiendo el contrato, el dataset `6ecc91d9…`, el manifiesto `149d5f09…`, el protocolo `cda87955…` y los hashes de `diagnostic.py`, `compact_study.py`, `pilot_metrics.py` y `audit_internal_solution.py`, además de la firma del checkpoint y la clave de la acción.

En cada uno de estos dos estados faltan las otras alternativas deterministas hasta el máximo de cuatro. Se eligen con la misma regla de orientación y posición, sin mirar los retornos ya vistos. Los fallos de esta corrida, que no los hubo, se conservarían con su motivo y seguirían contando como exposición. El tiempo de este preflight entra en las cuatro horas. Estos dos casos no se vuelven a lanzar en silencio.

Si el contrato cambia, este directorio queda como evidencia operativa separada. `00109938` y `00105640` siguen observados.

## Puerta

Sigue pendiente de aprobación y no se ha aplicado. Es una regla de ingeniería, no un contraste estadístico:

- Cobertura: al menos 15 de 20 pedidos con un estado completo y al menos 40 estados completos.
- Margen: media, con igual peso por pedido, de la fracción de estados completos con alguna ventaja positiva, al menos 0.25.
- Magnitud: media, con igual peso por pedido, de la mediana de las ventajas positivas; un pedido sin margen aporta 0; umbral 0.01 de `U_geom`.
- Coste: menos del 5 % de retornos desconocidos y finalización dentro de 14400 s.

El mejor retorno de un estado describe la oportunidad entre las candidatas examinadas. No describe una política realizable. Un margen no demuestra que un MLP pueda predecirlo. Los estados recorridos por Greedy no representan los estados que visitaría un actor aprendido. Limitar la comparación a cuatro candidatas deterministas limita lo que el diagnóstico puede ver.
