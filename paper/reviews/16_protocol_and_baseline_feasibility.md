# 16 — protocolo común y viabilidad de OnlineBPH

Preparado y probado el 2026-10-03 sobre `6fc55b6b74bfa46697b1fd25a6eb52cc4e71a1a2`, rama `research/paper-online-packing`. No hay `AGENTS.md` aplicable dentro del repositorio. Antes de este paso el árbol solo tenía los 17 pickle sin seguimiento. No hubo commit ni push.

Se conservan los resultados históricos. El paso 08 sigue no concluyente. La configuración de normalización del paso 13 sigue abandonada. El paso 15 midió una media de delta del teacher frente a GreedyBestFit de -0.021117453869047634. Los pesos del checkpoint histórico denominado PPO coinciden con los del actor BC y no hubo una mejora seleccionada mediante PPO. El generador interno es el de puntos extremos simplificado: no es EMS ni PCT. `physical_stability_verified` permanece null.

## Contrato

El protocolo es `paper/protocols/16_compact_selector_study.json`. Es una propuesta geométrica inspirada en el setting 2 del código continuo de Zhao et al., ICLR 2022. No es Table 1 de ese artículo ni la evaluación oficial de Kagerer, IJRR 2023.

Las condiciones comunes son la secuencia original de BED-BPP, un contenedor del target propio (euro-pallet 1200×800×2000 mm, rollcontainer 800×700×2000 mm), hasta seis permutaciones, contención y no solape, peso máximo, estabilidad y load-bearing inactivos, `p=s=1`, y terminación cuando el ítem actual no tiene candidata legal. El sufijo no se coloca. La primaria es `U_geom` sobre el volumen fijo del contenedor. El selector futuro no recibe dimensiones de ítems futuros ni `remaining_count`.

Ese terminal y ese peso inactivo cambian respecto de las corridas publicadas, que descartaban el ítem y seguían. Sus `U_geom` no se reutilizan como baseline.

La implementación está solo en `paper/`. Reutiliza `ExtremePointOnlineSession`, `ValidatorMask`, `GreedyBestFitPolicy`, `capture_document` y `evaluate_outcome`. No modifica `run_online_loop`. Las pruebas sintéticas cubren la parada al primer ítem imposible, el sufijo sin colocar, las dimensiones orientadas, las seis permutaciones, la observación sin información futura y el contraste del auditor.

## OnlineBPH

Copia aislada en `paper/external/pct`, ignorada por Git. Commit `5e7b4238b18310af4529e0f85157d17de605850c`, mensaje `Add MIT License to the project`, licencia MIT en `LICENSE`. El intérprete es `paper/external/pct/.venv`, con NumPy 1.26.4, gym 0.26.2 y torch 2.14.1+cpu. No se instaló CUDA ni se entrenó PCT. El entorno del proyecto no se modificó.

`heuristic.py --help` lista `--continuous`, `--setting`, `--load-dataset`, `--dataset-path` y `--heuristic`, con OnlineBPH entre las opciones. OnlineBPH es la heurística publicada en ese archivo, con la cita de Ha et al. en el comentario de la función. No es la política aprendida PCT.

El entorno continuo, con `setting == 2`, fija `orientation = 6`. `Space.check_box` devuelve verdadero de inmediato en ese setting, así que el chequeo de estabilidad posterior no se aplica. El contenedor de ejemplo en `givenData.py` es `[10, 10, 10]`. La entrada habitual es muestreo o un `.pt`, no un pedido BED-BPP.

Adaptaciones, todas fuera del repositorio externo y sin cambiar la regla de selección:

- Una secuencia finita en el orden de llegada sustituye al muestreo.
- Se llama `OnlineBPH(env, times=1)` y el segundo `reset`, el que borraría la geometría, no se ejecuta.
- Tras el último ítem real se ofrece un centinela mayor que el contenedor. Ese centinela no entra en la captura.
- `internal_node_holder` pasa a `max(80, n+5)` para que el registro de cajas cubra el pedido.
- Las dimensiones viajan en milímetros, sin redondeo. Con `test` falso, el entorno no aplica `round(..., 3)`.
- El generador sigue siendo el EMS de ese entorno. No se sustituye por el EP interno.

Un episodio sintético, anterior al smoke y fuera de los cinco pedidos, colocó dos cajas y se detuvo ante una caja de 5000 mm sin colocar el sufijo.

## Smoke

La regla se fijó antes de observar utilizaciones: los tres primeros euro-pallet y los dos primeros rollcontainer de la muestra de desarrollo, ordenados por posición. Pedidos `00100084`, `00100101`, `00100802`, `00100909` y `00101315`. Cinco pedidos, diez casos, CPU, un intento, 300 segundos. El preflight quedó escrito antes de los casos.

GreedyBestFit terminó `ok` en los cinco. El auditor no marcó fallo de geometría ni de entrada. `physical_stability_verified` es null.

| Pedido | Target | U_geom Greedy | Bucle (s) | Arranque (s) | Auditoría y escritura (s) | Pared del proceso (s) |
| --- | --- | --- | --- | --- | --- | --- |
| 00100084 | euro-pallet | 0.7013752604166666 | 1.967927993999183 | 1.972367658998337 | 0.7346199760013405 | 4.317389940999419 |
| 00100101 | rollcontainer | 0.6188446428571429 | 0.4109390639987396 | 1.891299867998896 | 0.35312901100041927 | 2.6148898089995782 |
| 00100802 | rollcontainer | 0.51999375 | 0.25995925799907127 | 1.8084581479997723 | 0.23687768099989626 | 2.3638488260003214 |
| 00100909 | euro-pallet | 0.6318796875 | 5.307002068999282 | 1.8372784090006462 | 1.7284196749988041 | 7.45789335399968 |
| 00101315 | euro-pallet | 0.6106265625 | 4.989618006000455 | 1.8588238219999766 | 1.252810201000102 | 7.132126914000764 |

La pared del proceso incluye arranque, bucle y construcción de la captura. No es la latencia de la política. El bucle es la columna que mide el empaquetado.

OnlineBPH sí ejecutó los cinco episodios: la salida estándar imprimió una utilización y una longitud, y `worker.json` guarda el episodio en `rejected_payload`. El arnés `invoke_worker` rechazó cada resultado porque `status` era `ok` y `capture` era null. `result.json` queda, por tanto, en `method_failure` con `U_geom` 0. Esos ceros no se han reescrito. No hubo reintento.

Una lectura posterior, `online_bph_posthoc_audit.json`, aplicó el auditor al payload ya guardado. No es una segunda corrida y no sustituye `result.json`. En los cinco, la geometría y la entrada pasaron, `input_changed` fue falso y `physical_stability_verified` quedó null. Las `U_geom` de esa lectura coinciden con la utilización impresa por el entorno: 0.6017633463541666, 0.6188446428571429, 0.46617053571428574, 0.4891484375 y 0.5235161458333333. Los bucles medidos en esos payloads fueron 0.42787421499997436, 0.35814404000120703, 0.23018653400140465, 0.5877127330004441 y 0.6071603930013225 segundos, con unos 2.0–2.2 segundos de importación de gym y torch en cada proceso.

Este smoke no permite afirmar superioridad. Las cifras de Greedy y las de la lectura posterior de OnlineBPH describen integraciones distintas de generador. No se comparan con números publicados de otros protocolos.

## Coste y presupuesto

Medias de los cinco Greedy: bucle 2.587089278199346 segundos, pared 4.7772297688000 segundos aproximadamente. La calibración propuesta es 32×40 = 1280 casos. A la pared media de Greedy serían unas 1.7 horas; al bucle medio, unas 0.9 horas si el proceso no se reinicia en cada caso. El caso Greedy más lento de este smoke tardó 7.46 segundos de pared: 1280 casos a ese ritmo serían unas 2.7 horas. La validación 3×50 = 150 casos quedaría, a la misma pared media, en unos 12 minutos. Una evaluación de 200 pedidos por método, con tres métodos, serían 600 procesos y del orden de una hora a esa pared.

OnlineBPH, en los bucles recuperados del payload, estuvo por debajo de 0.61 segundos, más unos 2 segundos de importación por proceso. Esa muestra son cinco pedidos ya elegidos, no los 40 de train ni los 200 finales. Un pedido mucho más largo puede cambiar el coste del EMS. La estimación cabe holgadamente en 12 horas solo si el coste por caso sigue cerca de estos cinco. No se garantiza la duración.

## Viabilidad

| Método | Fuente consultada | Tipo | Compatibilidad con este contrato |
| --- | --- | --- | --- |
| OnlineBPH | Código clonado, `heuristic.py` y `space.py`; Ha et al. citado en el comentario de la función | Implementación publicada en el repositorio. El PDF de Zhao respondió 403: la página de Setting 2 queda no verificada | El código corre en milímetros, con seis orientaciones, EMS propio y parada al primer ítem imposible. El arnés del smoke no aceptó la captura, así que todavía no es un comparador auditado por el runner |
| PCT | Zhao, Yu y Xu, ICLR 2022, OpenReview `bfuGjlCwAq` | Artículo revisado por pares. El PDF no se pudo abrir | No se entrenó ni se ejecutó. No es este selector. Table 1 no se reproduce |
| GOPT | Xiong et al., IEEE RA-L 2024, 9(11), 10335–10342; también arXiv:2409.05344. README del repositorio: bin por defecto 10×10×10 | Revista revisada por pares. El PDF de la revista no se abrió: condiciones de página, no verificadas | Generador de subespacios y política Transformer. No se ejecutó. Sus cifras no se comparan con las nuestras |
| OPAL | Poolavaram, Chugh y Dorn, arXiv:2607.28257 | Preprint. No se vio un venue de revista en la ficha consultada | La formulación ordena los ítems por huella descendente antes de empaquetar. Este contrato conserva la secuencia original. Su media 0.49 sobre 1500 pedidos BED-BPP es una cifra suya, sin homologación |
| BED-BPP oficial | Kagerer et al., IJRR 2023. README de `bed-bpp-env` rama `paper-implementation`: script `p=3`, `s=2` | Artículo de revista. La página del PDF no se releyó: métricas oficiales, no verificadas en página | Este experimento usa `p=s=1` y otro terminal. No es esa evaluación |

## Selector futuro

Sin ejecutar. La puntuación propuesta es contacto normalizado, menos `a` por el incremento de altura normalizado, menos `b` por el techo normalizado, más `c` por el apoyo. La cuadrícula es `a,b` en {0, 0.5, 1, 2} y `c` en {0, 0.25}: 32 configuraciones. El ajuste propuesto usa 20 euro-pallet y 20 rollcontainer de `train_order_ids_full.json`, en el orden del archivo, fuera de los 50 de desarrollo, de los 200 de la evaluación 07 y de sus exclusiones. La validación propuesta toma las tres mejores de train sobre esos mismos 50. La puerta de ingeniería pide mejora media de al menos 0.005 frente a Greedy y medias no negativas en ambos targets. No es una prueba estadística. No se eligieron coeficientes.

## Decisión

Bloqueado. El contrato interno y GreedyBestFit pasan las pruebas y el smoke auditado. OnlineBPH llega a producir geometría que el auditor acepta cuando se le entrega el payload guardado, pero el runner la clasificó como fallo antes de esa auditoría. Hasta que una corrida nueva deje esa captura dentro del resultado puntuado, no corresponde abrir la calibración de las 32 configuraciones.

## Evidencia

`paper/results/16_baseline_smoke` ocupa 1739239 bytes según `du -sb` y 1669607 bytes de contenido en 63 archivos. El mayor es `cases/00100909/greedy/audit.json`, con 509401 bytes. `paper/external/pct` no entra en el índice.
