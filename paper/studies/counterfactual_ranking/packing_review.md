# Revisión de los episodios de development

Corrida única en `learning_packing/`. 84 casos, verificación `ok`, tiempo de pared de la campaña 244.25330769499993 s. HEAD `83b5e1c59808bd761f4c6fc47234c7dc232468d1`. Protocolo `5fd74cc0a6fc52aaf248a977934d9e199919096aa82c3ae6b0309a03e6aa6946`.

La clasificación de la puerta es **no avanzar con esta configuración**. No es una refutación universal del aprendizaje de preferencias. No se elige semilla, no se sustituye el brazo y no se abre el test final. `physical_stability_verified` permanece `null`.

## Procedencia del ajuste

La nota completa está en `learning_packing/provenance_aborted_attempt.md`. Hay dos registros.

El intento `learning_training_aborted_missing_checkpoint_dir/` duró 4.102623733000655 s y quedó `incomplete`. Las semillas 11, 23 y 37 fallaron con `RuntimeError: Parent directory .../learning_training/checkpoints does not exist.`, la frase de `torch.save` cuando falta el directorio padre. No guardó historiales, ranking ni pesos. Su verificación tiene `checkpoints` vacío.

La campaña `learning_training/` es posterior. Los hashes de inicialización y de permutaciones coinciden con los del intento abortado, y esos hashes se calculan antes del bucle de cada brazo. No había pesos que reanudar. El proceso nuevo construye la inicialización documentada y un Adam nuevo. Los seis checkpoints son la época 40 de ese reinicio.

Si el fuente abortado ordenaba el ajuste antes del guardado, classification habría dado 40 pasos en memoria y preferences no habría empezado. El fuente de ese ejecutor no está en git: su hash es `820ab396a9061bd1b7b8a010c54b8cb2d742ecc6746a8fc440a4e5820d8a292a` y el de la campaña completa es `69245378470b83dbc5d6f8eb58113c7d2fa2e750bf87e994aca7a4f3aec21950`. `train_loop.py` tiene el mismo hash en los dos manifiestos. El bloque `config` es idéntico. El diff exacto queda desconocido. Si hubo pasos de Adam antes del fallo, queda desconocido. Si alguien leyó métricas en la salida estándar antes del relanzamiento, no quedó registro. Los hiperparámetros registrados no cambiaron. En el código que sobrevivió, el cambio visible es crear el directorio antes de `torch.save`.

Los seis modelos usados aquí coinciden con `training_verification.json`: época 40, contrato de 17 columnas, la misma normalización de train y los SHA256 ya publicados. El ranking de etiquetas no eligió semilla ni configuración.

## Casos

12 GreedyBestFit, 36 classification y 36 preferences. Cada caso tiene `input.json`, `worker.json`, `capture.json`, `audit.json` y `result.json`. Un intento, timeout 300 s. Cero fallos de método y cero errores del evaluador. `U_geom` se recalcula desde la captura auditada. En estos episodios el actor vio entre 16 y 142 candidatas legales en algún paso: no hay tope de cuatro.

## Resultados

La media es primero entre los doce pedidos de cada semilla y después entre las tres semillas. Cada target aporta seis pedidos. La tolerancia de victoria, empate y derrota es `1e-9`. Greedy se ejecutó una vez por pedido y se reutiliza en las tres semillas.

| Semilla | Pref.−clas. | Euro | Roll | V/E/D | Pref.−Greedy | Euro | Roll | V/E/D | Clas.−Greedy | V/E/D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 0.03409619760664681 | 0.00941382378472221 | 0.05877857142857142 | 5/2/5 | −0.006105282738095241 | −0.039376041666666674 | 0.027165476190476195 | 3/2/7 | −0.04020148034474206 | 3/2/7 |
| 23 | 0.02844305555555555 | −0.007702430555555566 | 0.06458854166666667 | 5/4/3 | −0.026514601934523808 | −0.027361197916666673 | −0.025668005952380946 | 2/4/6 | −0.05495765749007936 | 1/2/9 |
| 37 | 0.030306640625000002 | 0.0022289062499999956 | 0.05838437500000001 | 5/3/4 | −0.02673100198412698 | −0.024267361111111108 | −0.02919464285714285 | 2/3/7 | −0.05703764260912698 | 2/1/9 |

Agregado con igual peso por semilla:

| Contraste | Media | Euro-pallet | Rollcontainer |
| --- | ---: | ---: | ---: |
| preferencias − clasificación | 0.03094863126240079 | 0.0013134331597222137 | 0.06058382936507937 |
| preferencias − Greedy | −0.019783628885582008 | −0.03033486689814815 | −0.009232390873015866 |
| clasificación − Greedy | −0.050732260147982794 | −0.031648300057870365 | −0.06981622023809524 |

Los fallos de Greedy, classification y preferences son 0 en las tres semillas. Estas cifras describen los doce pedidos. No son 36 pedidos independientes por brazo.

El ranking guardado con las etiquetas ordena candidatas ya examinadas. En development, el regret de ese ranking y el `U_geom` de estos episodios no se mueven juntos de la misma forma: las preferencias quedan por encima de la clasificación en la media de episodios, mientras el regret de ranking no mostraba esa ventaja en todas las semillas. Son dos descripciones. La diferencia no demuestra una causa.

## Puerta

El texto del protocolo coincide con el resumen de las cinco condiciones. Se aplicó así:

1. Media preferencias−clasificación 0.03094863126240079 ≥ 0.005. Cumple.
2. La diferencia es positiva en las tres semillas. Cumple.
3. Media preferencias−Greedy −0.019783628885582008 ≥ 0.01. No cumple.
4. Esa media es negativa en euro-pallet y en rollcontainer. No cumple.
5. Los 84 episodios están auditados, sin fallo geométrico tratado como 0 y con estabilidad física `null`. Cumple.

Corrida íntegra y puerta incumplida: no avanzar con esta configuración. Que la clasificación quede por debajo de las preferencias y también por debajo de Greedy no autoriza cambiar el objetivo ni continuar con ese brazo.

## Tiempos

Medias por caso, en segundos. `decision_seconds` está incluido en `packing_loop_seconds`. La generación de candidatas no se separó: vive dentro del bucle congelado.

| Arranque | Decisión | Bucle | Captura | Auditoría y escritura | Pared del proceso |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.010442502404766666 | 0.03481191690477271 | 1.4733888543571472 | 0.03286235220237188 | 3.0680189858452436 | 6.379310612178577 |

La pared del proceso no es la latencia de la política. La campaña usó cuatro procesos a la vez; esos 244 s no comparan eficiencia.

## Archivos y pruebas

`paper/tests`: 122 pruebas, OK. `paper/studies/counterfactual_ranking/tests`: 55 pruebas, OK, con el aviso ya conocido en `test_learning_pilot.py`. Manifiesto, agregado y verificación son JSON válidos. Los hashes de código y de checkpoints están en `learning_packing/manifest.json`.
