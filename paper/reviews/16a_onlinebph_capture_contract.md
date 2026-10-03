# 16A — Contrato de captura de OnlineBPH

HEAD de trabajo: `6fc55b6b74bfa46697b1fd25a6eb52cc4e71a1a2`. Este paso no crea commit. No calibra, no entrena y no compara estadísticamente cinco casos con GreedyBestFit.

`physical_stability_verified` permanece `null`. Eso no es estabilidad demostrada.

## Tres registros distintos

1. Smoke original, `paper/results/16_baseline_smoke/`. OnlineBPH terminó en `method_failure` y `U_geom` efectivo 0. Esos cinco `result.json` no se modificaron.
2. Diagnóstico posterior, `paper/results/16_baseline_smoke/online_bph_posthoc_audit.json`, con `replaces_pipeline_score: false`. Recuperar la geometría después no sustituye el fallo de contrato.
3. Verificación nueva, `paper/results/16a_onlinebph_capture_smoke/`. El worker corregido escribió la captura dentro del JSON que lee `invoke_worker`.

## Causa

`online_bph_worker.py` escribía `status: ok` y `capture: null`, y dejaba la geometría en `episode`. `_structure_error` (`paper/tools/pilot_execute.py`, líneas 47-48) rechaza ese esquema con «estructura de resultado inválida: status ok sin captura». `_worker_failure` (líneas 87-96) devuelve `status: crash` y `capture: null`. `evaluate_outcome` (líneas 319-323) corta ahí, con `method_failure` y `U_geom` efectivo 0, sin auditar. El runner del paso 16 solo armaba la captura si el resultado ya era `ok`, así que esa reconstrucción no se ejecutaba.

El auditor y el contraste no se debilitaron. El hueco estaba en el adaptador: la captura no viajaba en el archivo que el arnés valida.

## Corrección

El worker aislado construye la captura con `capture_online_bph` a partir de las cajas que colocó OnlineBPH y del snapshot independiente que recibe el job. Conserva identidades, dimensiones originales, dimensiones orientadas, coordenadas, contenedor, unidades, restricciones, colocados, no colocados, `p`/`s` y la parada. Excluye el centinela. `physical_stability_verified` queda `null`. El algoritmo registrado es `online_bph`.

La selección, el generador EMS, el commit externo `5e7b4238b18310af4529e0f85157d17de605850c`, la secuencia, las seis orientaciones, la contención, el no solape y la parada al primer ítem imposible no cambiaron. El código de producción no se tocó. El protocolo 16 no se reescribió; sus hashes de código siguen siendo los del smoke original.

## Pruebas del recorrido

`paper/tests/test_online_bph_capture_contract.py` usa archivos temporales y un worker sintético. Cada caso pasa por `invoke_worker` y después por `evaluate_outcome`:

1. Captura válida: se acepta y se audita.
2. Captura ausente: sigue rechazándose.
3. Captura incompatible con el snapshot: `input_mismatch` y `U_geom` efectivo 0.
4. La altura orientada se conserva cuando cambia respecto de la original.
5. El centinela no entra en la captura.
6. El sufijo queda sin colocar, con su motivo.
7. Geometría inválida: `U_geom` efectivo 0.
8. Salida distinta de cero: no se puntúa aunque el archivo traiga captura.

`.venv/bin/python -m unittest discover -s paper/tests -p 'test_*.py'` : 114 pruebas, OK. `git diff --check` no señaló espacios finales.

## Verificación nueva

Registrada antes de empaquetar en `preflight.json`. Motivo: comprobar el contrato corregido, sin sustituir los `method_failure`. Dataset `bed-bpp_v1.json`, SHA256 `6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc`. CPU, un intento, timeout 300 s. Orden: 00100084, 00100101, 00100802, 00100909, 00101315. La URL, la licencia MIT, las versiones del entorno aislado y los comandos usados quedan en `paper/protocols/16_external_online_bph.json`.

Hashes del adaptador usado:

| Archivo | SHA256 |
| --- | --- |
| `paper/tools/compact_study.py` | `d179140db16e22e1d7ba9b443467a6a3851c2b12f326416e88c261eef10b4843` |
| `paper/tools/online_bph_case.py` | `67b5dfeac94f0ee84bc39bc5b47b2120b2fbd4f71ab6a1708e4da56224acf644` |
| `paper/tools/online_bph_worker.py` | `81fa4e6be397d0d17038f2ff1b840b02c0282dadde2df88099dd2cef414a5d03` |
| `paper/tools/run_onlinebph_capture_check.py` | `611d788b74c1b33ace05ead0625cf5658c3f255ab8fea320c6982ed483c8cdd8` |

`online_bph_case.py` conserva el hash del paso 16. El worker y la captura cambiaron.

| Pedido | worker_status | captura | input_mismatch | geometría | U_geom efectivo | fallos |
| --- | --- | --- | --- | --- | --- | --- |
| 00100084 | ok | sí | false | válida | 0.6017633463541666 | ninguno |
| 00100101 | ok | sí | false | válida | 0.6188446428571429 | ninguno |
| 00100802 | ok | sí | false | válida | 0.46617053571428574 | ninguno |
| 00100909 | ok | sí | false | válida | 0.4891484375 | ninguno |
| 00101315 | ok | sí | false | válida | 0.5235161458333333 | ninguno |

Los cinco `result.json` anteriores siguen en `method_failure` con `U_geom` efectivo 0. Sus SHA256 coinciden con los registrados en el preflight de esta corrida. `previous_results_unchanged` es true. GreedyBestFit no se relanzó.

## Decisión

Listo para calibración. Los cinco casos nuevos atravesaron el runner y la auditoría con la entrada independiente y sin fallos de contrato. La calibración de la cuadrícula no se ejecutó en este paso.
