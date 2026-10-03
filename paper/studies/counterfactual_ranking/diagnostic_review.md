# Diagnóstico counterfactual de desarrollo

Corrida única, terminada. Código de salida 0. Clasificación: margen suficiente para diseñar el experimento de aprendizaje. Esa clase no autoriza entrenamiento automático y no demuestra mejora de una política online.

## Comando

```text
.venv/bin/python paper/studies/counterfactual_ranking/tools/run_diagnostic.py \
  --protocol paper/studies/counterfactual_ranking/protocol_frozen.json \
  --dataset /home/edmundo/bed-bpp-env/example_data/benchmark_data/bed-bpp_v1.json \
  --preflight paper/studies/counterfactual_ranking/preflight_results/preflight.json \
  --output paper/studies/counterfactual_ranking/diagnostic_results
```

Estado: `completed`. Pedidos pendientes: ninguno. El directorio de salida no existía y se rechazaría si se relanzara.

El protocolo congelado, SHA256 `e8fafb399a59863fc7a03f011b91f93e22af78f3a0d7aa78520c4a9e035717c1`, se escribió y se hasheó antes de las continuaciones nuevas. El borrador sigue en `cda879555db890f9108e4fb495cfaa7d1881bd61fa4f3e18ce950f3ca5ca84a6`. La equivalencia registrada es semántica. El preflight `b0fb7cd9958202c8cec7e90170bbc9c6b177ed49b5ec03ed75abefd8c47e3dfd` y `diagnostic.py` `8d95f84c50b15a46dcf361a303889be18ba6b8487f605f28c850fa0012f9d4aa` no se modificaron.

## Casos

Se reutilizaron 4 continuaciones, dos de `00109938` y dos de `00105640`, referenciadas por `preflight_results/preflight.json` y su SHA256. Se contaron una sola vez. Sus capturas no se duplicaron en los JSON de pedido.

Se ejecutaron 391 continuaciones nuevas. No quedó trabajo pendiente ni retorno desconocido. Cinco estados tenían tres candidatas legales, así que el programa real fue 395 continuaciones, por debajo del techo de 400.

Los 100 estados previstos se capturaron. Los dos estados del preflight ya estaban contados; los 98 restantes son nuevos y salen de la trayectoria Greedy. Volver a recorrer esa trayectoria para llegar a un estado posterior no repite las cuatro continuaciones ya evaluadas.

Claves `(pedido, estado, acción)`: 395, sin duplicados.

## Cobertura

| | Pedidos | Estados | Continuaciones |
| --- | ---: | ---: | ---: |
| Previstos por el diseño | 20 | 100 | hasta 400 |
| Inspeccionados y completos | 20 | 100 | 395 programadas |
| Válidas, con `Q_hat` conocido | 20 | 100 | 395 |
| Desconocidas o no ejecutadas | 0 | 0 | 0 |
| Sin cobertura | 0 | 0 | — |

Las 391 capturas nuevas reproducen `Q_hat` al recalcular el volumen orientado partido por el volumen del contenedor. `physical_stability_verified` queda `null` en todas. Las cuatro del preflight ya se habían auditado en su archivo.

`A_hat` sobre las 395 alternativas de estados completos: 96 positivas (`> 1e-9`), 234 en cero y 65 negativas. El mejor candidato examinado supera a Greedy en 47 de los 100 estados. La mediana de ese máximo por estado es 0, la media es 0.027264194940476192 y el máximo observado es 0.15474799107142856. Es la oportunidad entre las candidatas examinadas en estados visitados por Greedy. No es el rendimiento de una política, ni una cota, ni una comparación con PCT.

Los estados de un mismo pedido no se tratan como observaciones independientes. `f_i` y `m_i` resumen cada pedido, y las medias dan el mismo peso a cada uno de los 20.

## Por pedido

`f_i` es la fracción de estados completos con alguna alternativa mejor que Greedy. `m_i` es la mediana de las ventajas positivas de las alternativas evaluadas en esos estados, o 0 si no hay ninguna.

| Pedido | Target | Estados | Alternativas | f_i | m_i |
| --- | --- | ---: | ---: | ---: | ---: |
| 00109938 | euro-pallet | 5 | 20 | 0.0 | 0.0 |
| 00109266 | euro-pallet | 5 | 19 | 0.0 | 0.0 |
| 00102701 | euro-pallet | 5 | 20 | 0.0 | 0.0 |
| 00108060 | euro-pallet | 5 | 19 | 0.0 | 0.0 |
| 00104500 | euro-pallet | 5 | 20 | 0.0 | 0.0 |
| 00103525 | euro-pallet | 5 | 20 | 1.0 | 0.03564583333333338 |
| 00100812 | euro-pallet | 5 | 20 | 1.0 | 0.034510416666666766 |
| 00109602 | euro-pallet | 5 | 19 | 0.0 | 0.0 |
| 00109122 | euro-pallet | 5 | 20 | 1.0 | 0.027720833333333306 |
| 00104671 | euro-pallet | 5 | 20 | 0.0 | 0.0 |
| 00105640 | rollcontainer | 5 | 20 | 1.0 | 0.05399999999999994 |
| 00109225 | rollcontainer | 5 | 19 | 1.0 | 0.044039285714285725 |
| 00100129 | rollcontainer | 5 | 20 | 0.0 | 0.0 |
| 00103399 | rollcontainer | 5 | 20 | 0.4 | 0.05467399553571428 |
| 00105687 | rollcontainer | 5 | 20 | 0.6 | 0.028839285714285734 |
| 00107454 | rollcontainer | 5 | 20 | 1.0 | 0.018224999999999936 |
| 00109271 | rollcontainer | 5 | 19 | 1.0 | 0.10627656250000006 |
| 00105150 | rollcontainer | 5 | 20 | 1.0 | 0.04049999999999998 |
| 00109874 | rollcontainer | 5 | 20 | 0.4 | 0.0476428571428571 |
| 00101397 | rollcontainer | 5 | 20 | 0.0 | 0.0 |

Euro-pallet, 10 pedidos, 50 estados y 197 alternativas: media de `f_i` 0.3 y media de `m_i` 0.009787708333333344.

Rollcontainer, 10 pedidos, 50 estados y 198 alternativas: media de `f_i` 0.64 y media de `m_i` 0.03941969866071428.

## Puerta

1. Pedidos con estado completo: 20, frente a 15. Estados completos: 100, frente a 40. Cumplida.
2. Media de `f_i`: 0.47, frente a 0.25. Cumplida.
3. Media de `m_i`: 0.02460370349702381, frente a 0.01. Cumplida.
4. Retornos desconocidos: 0 de 395, tasa 0, por debajo del 5 %. Cumplida.
5. Pared acumulada: 1223.2690794659975 segundos, dentro de 14400. Cumplida.

Clasificación: `margen_suficiente_para_disenar_el_experimento_de_aprendizaje`. El recálculo desde los resultados por alternativa coincide con `verification.json`. `authorizes_training` queda en false. El margen observado no demuestra que sea aprendible, ni que una política online mejore, ni causalidad, ni predictibilidad del retorno.

La media de `m_i` en euro-pallet queda por debajo de 0.01. La puerta usa el promedio con igual peso sobre los 20 pedidos, y ese promedio sí la supera. El presupuesto aceptado sigue siendo truncado: esta corrida cupo en el reloj, y eso no afirma que el peor caso de 400 continuaciones a 60 segundos quepa en cuatro horas.

## Tiempos

El preflight aportó 10.726841075997072 segundos, suma exacta de `startup_seconds` y `work_wall_seconds`. La campaña añadió 1212.5422383900004 segundos de pared.

Dentro de la campaña, por separado: arranque 1.7606912800001737, adquisición de estados 0.3185677740002575, continuación nueva 896.8992479339977, captura 0.11227872898598434 y auditoría 311.57096390397055. La suma de fases no es coste de CPU. El presupuesto acumulado usado es 1223.2690794659975 de 14400 segundos.

## Archivos y pruebas

Antes de la campaña: `paper/tests` 122 pruebas OK y `paper/studies/counterfactual_ranking/tests` 25 pruebas OK. La suite del estudio se volvió a ejecutar después del último ajuste del reloj, también OK.

JSON válidos: protocolo congelado, manifiesto, compatibilidad del preflight, resultados, verificación y registro de exposición. `git diff --check` no reporta errores en el diff rastreado.

Evidencia: `diagnostic_results/manifest.json`, `preflight_compatibility.json`, `orders/`, `results.json`, `results_partial.json`, `verification.json`, `exposure_registry.json`. Los 20 pedidos inspeccionados están en el registro de exposición de esta campaña.

El cierre de la campaña compacta permanece. No hay commit ni push.
