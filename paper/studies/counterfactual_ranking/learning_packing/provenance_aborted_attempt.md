# Procedencia del intento abortado

Hay dos registros distintos. `learning_training_aborted_missing_checkpoint_dir/` es un intento incompleto. `learning_training/` es una campaña posterior que volvió a construir los modelos.

El intento abortado terminó en 4.102623733000655 s con estado `incomplete`. Las tres semillas 11, 23 y 37 registran el mismo error: `RuntimeError: Parent directory /home/edmundo/packing-services/paper/studies/counterfactual_ranking/learning_training/checkpoints does not exist.`. Esa frase es la de `torch.save` cuando el directorio padre no existe. No hay historiales, ranking ni checkpoints: `checkpoints` de su verificación está vacío.

Los hashes de inicialización y de permutaciones de las tres semillas coinciden con los de la campaña completa. Esos hashes se calculan antes del bucle de cada brazo. El intento abortado no guardó pesos ni estado de Adam.

El hash de `train_loop.py` es el mismo en los dos manifiestos (`60b782aa6fa6505a5de3cd4f3f128ed4d0bedfa6dc9d8a64d92d00f50b10b31b`). El de `run_learning_training.py` no: el abortado tiene `820ab396a9061bd1b7b8a010c54b8cb2d742ecc6746a8fc440a4e5820d8a292a` y la campaña completa `69245378470b83dbc5d6f8eb58113c7d2fa2e750bf87e994aca7a4f3aec21950`. El bloque `config` de los dos manifiestos es idéntico. El fuente abortado no está en git, así que el diff exacto queda desconocido. El ejecutor que sobrevivió crea el directorio de checkpoints inmediatamente antes de `torch.save`, y esa llamada está después de `train_arm`.

Si en el fuente abortado el orden era el mismo, cada semilla habría dado 40 pasos de Adam en classification y habría fallado al guardar, sin llegar a preferences. Las marcas de tiempo entre semillas son de unos 0,7–0,9 s. La campaña completa tardó varios segundos por semilla. Con esa evidencia no se puede afirmar que los pasos de Adam ocurrieran. Tampoco se puede afirmar que no ocurrieran. Queda desconocido.

No hay ranking ni historial en el intento abortado. Si alguien inspeccionó métricas en la salida estándar antes del relanzamiento, no quedó registro. La campaña completa no parte de pesos guardados: no existían. Su proceso nuevo llama a la inicialización documentada, crea un Adam nuevo dentro de `train_arm` y escribe los seis checkpoints de la época 40. Es un reinicio limpio de los artefactos, no una continuación del intento abortado, y tampoco es una campaña que no se hubiera vuelto a lanzar.

Los hiperparámetros registrados no cambiaron. Lo que sí cambió, en el código que quedó, es la creación del directorio antes de guardar.
