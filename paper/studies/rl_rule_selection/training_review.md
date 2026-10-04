# Revisión del piloto PPO reducido

El piloto se ejecutó una vez, con el protocolo congelado antes del primer update. Las tres semillas completaron el presupuesto común. Esta revisión no elige semilla ni checkpoint, no aplica la puerta de desarrollo y no afirma convergencia ni publicabilidad.

## Integridad

HEAD `c7191d5fc87b4125795cd168b49c4709bb95a9b8` en `research/paper-online-packing`.

SHA256 de `protocol_frozen.json`: `61923d12ef9069cc0bdb95e547b22a89f05fe1db703f80182420bc79350b9c25`.

Hashes del código congelado:

| Archivo | SHA256 |
| --- | --- |
| `tools/ppo_math.py` | `1fb214abc798931b3eb7a3857c49f890a49869318e98482a26f43eb3cf3033fc` |
| `tools/model.py` | `1777aa425785845ecf9dbb57c2a6165a0421657c9158340167e44b6cbdb8a5c6` |
| `tools/train_loop.py` | `1ace8d2b7acf6eb9d15f4dee401131cef630d9306ae391d0b7903ce27e68c8ae` |
| `tools/environment.py` | `3111f00dca1434cecc9a8c9ff527ddfca00d2bc4ec0722e85573bd7ddd5e6125` |
| `tools/observation.py` | `252c641df75386b8bf5302f450e0cbb75f85ef5f54ad430cb9fd2e57c089da87` |
| `tools/rules.py` | `251fc3709d09863a2473cb59c159e8b015e79be53ed45582c7f529cf5c0e2f08` |
| `tools/sample_audit.py` | `019fe20f6ef0ac13af4391d4ae24e492b46a02a934318efab7e500165752a042` |
| `tools/run_training.py` | `e9963c2d7199e2de37b85c2f9eeaeac8303ac59519350cf08136a05b369a9f7c` |

El presupuesto de 6144 decisiones sale del tiempo del preflight: el bucle más lento hizo 98 decisiones en 62.830 s, 0.641 s por decisión. A esa tasa, 60000 decisiones no cabían en 4800 s y 6144 sí. U_geom no intervino en el corte. El techo antiguo de 1000 episodios no fue el criterio. `physical_stability_verified` permanece null.

Hay 40 pedidos de desarrollo, veinte por target, con cero solapes de identificador o de firma respecto de train y cero clones descartados. Sus episodios no se ejecutaron. El test final no se seleccionó.

## Semillas

Las tres quedaron `completa`, con 6144 decisiones, 12 actualizaciones y 192 pasos de Adam. Comparten presupuesto. Las recompensas de train quedan registradas y no seleccionan checkpoint ni semilla.

| Semilla | Decisiones | Propuestas distintas | Actualizaciones | Pasos Adam | Episodios | Tiempo de pared (s) | CPU usuario (s) | `ru_maxrss` (KB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 101 | 6144 | 4972 | 12 | 192 | 160 | 266.867 | 244.148 | 692336 |
| 102 | 6144 | 4945 | 12 | 192 | 158 | 275.714 | 252.385 | 691080 |
| 103 | 6144 | 4981 | 12 | 192 | 160 | 249.748 | 228.014 | 695404 |

Causas de cierre registradas, incluido el episodio que seguía abierto al llegar a 6144 decisiones:

| Semilla | `sin_candidata` | `secuencia_agotada` | episodio abierto al corte de interacciones |
| --- | ---: | ---: | --- |
| 101 | 114 | 45 | `00106506`, rollcontainer, 45 ítems, 5 decisiones |
| 102 | 111 | 46 | `00101736`, euro-pallet, 58 ítems, 6 decisiones |
| 103 | 117 | 42 | `00107704`, euro-pallet, 40 ítems, 29 decisiones |

Ese episodio abierto lleva la etiqueta `corte_de_presupuesto` porque el cupo de interacciones terminó dentro del pedido. El reloj de 4800 s no cortó ninguna semilla. El entorno de ese pedido no se reanuda.

Cada actualización hizo 16 pasos de Adam. No hubo valores no finitos ni pérdidas no finitas. La fracción de clip fue 0 en las doce actualizaciones de cada semilla. La KL aproximada media fue 0.000135, 0.000475 y 0.000066. La entropía media fue 0.996, 0.992 y 0.994. La recompensa media por decisión, dentro de los rollouts de train, fue 0.01675, 0.01637 y 0.01643.

## Memoria y auditoría

El muro de la campaña fue 522.952 s. El máximo de la suma muestreada de VmRSS del padre y de los workers vivos fue 1601520 KB, en 509 muestras. El `ru_maxrss` del padre fue 219384 KB. Esas dos cifras miden cosas distintas.

Cada semilla tiene una captura final auditada. Las tres tienen geometría interna válida, cero solapes y cero cajas fuera del contenedor. `physical_stability_verified` es null. La auditoría no se ejecutó dentro de cada rollout.

## Pruebas

Pasaron las tres suites antes del entrenamiento: 27 pruebas del estudio, 55 de counterfactual ranking y 122 de `paper/tests`. El aviso de tensor en `test_learning_pilot.py` ya estaba en esa suite.

## Qué queda sin hacer

La puerta de desarrollo está escrita y no se aplicó. No hay episodios de desarrollo ni de test. No hay ampliación de presupuesto, commit ni push.
