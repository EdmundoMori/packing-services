# Paso 02 — protocolo efectivo y separación de datos

Origen: `research/paper-online-packing` en `f4525b8cd05ab52570cc58abfb54cac9c41dcae2`.

Este informe describe el comportamiento del código de packing-services. No es una reproducción de un método externo. Donde el código no alcanza, la conclusión es **no comprobado**. No se entrenó, no se infirió y no se deserializó ningún checkpoint ni ningún `.pkl`.

## Qué problema resuelve la implementación

Coloca ítems de un pedido, en el orden de llegada, dentro de los contenedores que el problema ya trae. En cada paso genera colocaciones sobre los puntos extremos actuales, descarta las que no pasan la máscara y pide a una política que elija una colocación ya legal. La colocación es irrevocable. Si ninguna opción del buffer es legal, descarta el ítem más antiguo y sigue con el resto.

Alcance: lectura de `run_online_loop`, `ExtremePointOnlineSession.candidates`, `ValidatorMask.allows` y `LearnedPlacementPolicy.decide`. No se ejecutó un pedido en este paso.

## Matriz

### Contenedores

El bucle crea un estado por cada contenedor presente en `problem.containers`. No añade contenedores durante el pedido.

- Comportamiento: `ExtremePointOnlineSession.__init__` construye `self.states` a partir de esa lista (`session.py`, líneas 37–39) y `candidates` recorre `self.states` (líneas 61–77).
- La conversión de un pedido crea exactamente un contenedor, el del `target` (`convert_order_to_pack_input`, líneas 251–265; `_resolve_target_container`, líneas 72–95).
- Si hay más de un contenedor y `consolidate` no es false, `wants_consolidate` activa una envolvente que no abre un bin nuevo: retira candidatas de bins posteriores mientras el actual admita alguna (`params.py`, `wants_consolidate`, líneas 28–38; `policies.py`, `ConsolidatingPolicy.decide`, líneas 157–176).
- Limitación: el número de contenedores del pedido 00100408 no se releyó del dataset en este paso. El código de conversión produce uno salvo que el problema se construya por otra vía.

### Dimensiones y unidades

Euro-pallet: 1200 × 800 × 2000. Rollcontainer: 800 × 700 × 2000. Peso máximo por defecto: 1500. El payload declara unidades `mm_kg` (`bed_bpp.py`, líneas 21–26 y 277).

### Orden de llegada

`order_to_problem` pide `packing_mode="online"` (`problems.py`, líneas 30–57). En ese modo `_merge_parameters` fuerza `sort_strategy="input_order"` (`bed_bpp.py`, líneas 152–171). El bucle ordena con `SortStrategy.INPUT_ORDER` y el comentario de la función dice que no reordena fuera de `s` (`loop.py`, líneas 33 y 43–48).

Dentro del buffer de tamaño `s` la política puede elegir un ítem que no sea el primero. El maestro de etiquetas, en un snapshot que luego restaura, sí reordena una copia de toda la cola por volumen descendente (`teacher.py`, `receding_horizon_ep_index`, líneas 45–74). Esa reordenación no es la del actor en inferencia.

Los ítems salen de `item_sequence` ordenados por `sequence`, con `allowed_orientations="all"` (`bed_bpp.py`, `_items_from_sequence`, líneas 98–123).

### Significado operativo de p y s

`InformationBudget.observe_p` es cuántos ítems próximos entran en la ventana, incluido el actual. `select_s` es cuántos del frente pueden elegirse ahora. `window` recorta ambos a los que quedan y garantiza observar al menos los `s` seleccionables (`budget.py`, líneas 25–50).

En el bucle, `selectable = remaining[:select_s]` y `preview = remaining[:observe_p]` (`loop.py`, líneas 47–49). La receta de los notebooks 03 y 05 fija `LOOKAHEAD_P, SELECT_S = 1, 1` para el checkpoint de producción p1s1. Con p=s=1 la ventana es el ítem actual.

### Qué futuro ven el motor y el actor

El motor, al generar candidatas, solo usa el layout ya colocado y el ítem que está evaluando (`session.py`, `candidates`, líneas 53–79). No lee la cola.

El actor recibe `preview` y `remaining_count` (`learned/policy.py`, `decide`, líneas 24–44). `preview` es la ventana `p`. `encode_option` copia hasta tres ítems de esa ventana distintos del ítem puntuado (`features.py`, líneas 18 y 93–107). Con p=1 esa copia queda en ceros.

`remaining_count` es `len(remaining)` en el momento del paso (`loop.py`, línea 66): el tamaño de la cola que falta, no un identificador. Se comprime como `min(max(remaining_count, 0) / 50.0, 1.0)` (`features.py`, línea 132). El actor conoce ese conteo, incluido lo que queda fuera de la ventana. No recibe las dimensiones de esos ítems fuera de la ventana. No hay una característica separada con el total original del pedido; el conteo empieza siendo el tamaño de la cola y disminuye.

### Las 35 características

`FEATURE_NAMES` tiene 35 nombres y `FEATURE_DIM = len(FEATURE_NAMES)` (`features.py`, líneas 20–59). `encode_option` (líneas 68–140) las calcula así. Ninguna usa el resultado de una colocación futura. Las de preview y `remaining_n` usan la cola de llegada, que todavía no se ha colocado.

| Nombre | Cálculo | Fuente |
| --- | --- | --- |
| `item_l_n`, `item_w_n`, `item_h_n` | largo, ancho y alto del ítem partido por los del contenedor de la candidata | ítem actual, dimensiones originales |
| `item_vol_n` | volumen del ítem / volumen del contenedor | ítem y contenedor actuales |
| `item_weight_n` | peso del ítem / `max_weight` del contenedor, o / 1 si el máximo es nulo o cero | ítem y contenedor actuales |
| `item_can_rotate` | 1 si `item.allow_rotation`, si no 0 | `allowed_orientations == "all"` (`models.py`, líneas 57–58) |
| `pos_x_n`, `pos_y_n`, `pos_z_n` | posición de la candidata / dimensiones del contenedor | candidata ya generada |
| `ori_l_n`, `ori_w_n`, `ori_h_n` | dimensiones orientadas de la candidata / contenedor | candidata ya generada |
| `support_ratio` | valor ya calculado en la candidata | apoyo geométrico sobre cajas ya colocadas |
| `bin_index_n` | índice del contenedor / número de contenedores de la sesión | candidata y sesión |
| `rank_0` … `rank_3` | primeros cuatro componentes de `rank_key`, con ceros si faltan | puntuación del generador sobre el layout actual |
| `n_packed_n` | `min(len(session.packed) / 50, 1)` | colocaciones ya hechas |
| `loaded_weight_n` | peso cargado en ese contenedor / su máximo | estado actual del contenedor |
| `used_height_n` | máximo `max_corner[2]` de las cajas ya puestas / alto del contenedor | layout actual |
| `remaining_n` | conteo de la cola / 50, recortado a 1 | argumento `remaining_count` |
| `buffer_index_n` | índice dentro del buffer / 5, recortado a 1 | opción legal |
| `preview_0_*` … `preview_2_*` | largo, ancho, alto y volumen normalizados de hasta tres ítems distintos del actual en `preview`; huecos en cero | ventana `p`, no el resto de la cola |

`_safe_div` devuelve 0 si el denominador es casi cero (líneas 62–65).

### Generador de candidatas

La clase que genera las posiciones es `ExtremePointOnlineSession`. Delega la factibilidad y la clave de orden en `ExtremePointPacker._feasible` y `_score` (`session.py`, líneas 53–79). El módulo `_extreme_points.py` describe una lista persistente de puntos extremos con proyección vertical y contacto de caras (líneas 1–19 y 76–84). `_score` con `selection="best_fit"` ordena por mayor contacto y después por menor z, y, x (líneas 186–195). `config.SELECTION` es `"best_fit"` (`config.py`, línea 22) y `online_params` lo copia al problema (`problems.py`, líneas 13–24).

No se usó otro nombre para este generador. No es un generador de espacios máximos.

Filtro dentro del generador, antes de la máscara (`_feasible`, líneas 170–184):

- contención, si `constraints.containment`;
- peso acumulado, si `constraints.max_weight` y el contenedor tiene máximo;
- no solape, si `constraints.non_overlap`.

No filtra soporte, carga ni fragilidad.

### Máscara

`ValidatorMask.allows` (`mask.py`, líneas 33–48) rechaza la candidata si `min_support_ratio > 0` y `support_ratio` queda por debajo. Después arma un layout de prueba y llama a `PackingValidator.rejects_trial`. Ese método valida sin exigir la lista de no colocados y solo rechaza severidad error (`validator.py`, líneas 92–111). Las comprobaciones activas dependen de las banderas (`validate`, líneas 72–87): contención, orientación, no solape, peso, estabilidad básica y load-bearing.

`support_threshold` devuelve 0 cuando `basic_stability` es false (`params.py`, líneas 18–25). Con la conversión por defecto, el filtro duro de soporte no se activa.

### Orientaciones

Globales: `unique_orientations` devuelve la dimensión original si `allow_rotation` es false, y hasta seis permutaciones distintas de `(l, w, h)` si es true (`geometry.py`, líneas 76–93).

Por ítem: `orientations_for` exige las dos cosas, la bandera del problema y `item.allow_rotation` (`session.py`, líneas 49–51). En la conversión, cada ítem nace con `allowed_orientations="all"`, así que `allow_rotation` del ítem es true.

### Estabilidad, soporte, peso y carga

El peso se filtra en `_feasible` y, si la bandera está activa, otra vez en el validador. El soporte se calcula y se guarda en la candidata; solo elimina candidatas si el umbral es positivo. `basic_stability` y `load_bearing` existen en `ConstraintFlags` con default false (`models.py`, líneas 81–97) y el validador las ejecuta solo si la bandera está true. No hay centro de masas en el generador ni en la máscara. La estabilidad física de una solución terminada queda **no comprobada** por este código. El paso 01E ya dejó `physical_stability_verified` en null; este paso no repite esa auditoría.

### Acción del actor

`LearnedPlacementPolicy.decide` codifica las opciones que el bucle ya marcó como legales, obtiene un escalar por opción con `backend.score` y se queda con la mayor puntuación. A igualdad de puntuación gana el menor `buffer_index` (`learned/policy.py`, líneas 34–53). No crea posiciones. No reordena la cola fuera del buffer. El comentario de la clase lo dice en las líneas 14–15.

La carga del checkpoint está en `LearnedPlacementPolicy.from_path` → `load_backend` (`policy.py`, líneas 20–22) y `checkpoint.py` (`torch.load` con `map_location="cpu"`, líneas 123–125). Este paso no abrió el archivo `.pt`.

### Ítem que no cabe

Si `decide` devuelve `None`, el bucle saca `remaining[0]`, lo anota como no colocado con la razón «No hay colocación legal con el presupuesto de información actual» y continúa (`loop.py`, líneas 72–80). No termina el pedido. No abre otro contenedor. El mismo descarte ocurre al etiquetar si no hay opciones o el maestro no devuelve índice (`collect.py`, líneas 69–71 y 98–101).

### Determinismo

Inferencia del actor: la elección es el máximo de las puntuaciones. El bucle de inferencia no llama a un muestreador. `Online3DBPPHeuristic.metadata.deterministic` es true (`online_3d_bpp_heuristic.py`, línea 46). El reparto de splits usa `random.Random(seed)` con `SEED = 42` (`splits.py`, líneas 94–111 y 136–146; `config.py`, línea 3).

Entrenamiento PPO: cada rollout llama a `Categorical.sample()` porque `fit_ppo` pasa `deterministic=False` (`train_ppo.py`, líneas 263–269 y 496–503). El actor de imitación baraja con `torch.randperm` (`train_mlp.py`, líneas 100–102). Que una repetición concreta del pedido 00100408 haya coincidido con un plan histórico no se usa aquí como prueba de determinismo general.

### Restricciones implementadas y las de la receta 00100408

Implementadas en el validador, cada una detrás de su bandera: no solape, contención, orientación, peso, estabilidad básica, load-bearing (`validator.py`, líneas 72–87). Fragilidad y secuencia de descarga existen en el modelo con default false (`models.py`, líneas 96–97); este paso no encontró un filtro de candidatas que las aplique. **no comprobado** más allá de ese default.

`order_to_problem` no pasa un diccionario de restricciones (`problems.py`, líneas 42–48). `convert_order_to_pack_input` usa entonces `_default_constraints` (`bed_bpp.py`, líneas 254–259). Para un tipo distinto de `STACKING_AWARE` ese default enciende no solape, contención, rotación y peso, y deja estabilidad básica y load-bearing en el default false del modelo (`bed_bpp.py`, líneas 134–149). `PROBLEM_TYPE` es `"3D_BPP"` (`config.py`, línea 23). Con esas banderas, `support_threshold` devuelve 0.

La receta efectiva de un pedido convertido por ese camino, incluido el que usarían los notebooks con `order_to_problem`, activa no solape, contención, rotación y peso máximo. No activa estabilidad básica, load-bearing, fragilidad ni secuencia de descarga. No se volvió a abrir el JSON del pedido para confirmar su `target`; si el target es euro-pallet, el contenedor es el de 1200 × 800 × 2000 mm y 1500 kg.

## Información del maestro, del actor y de la selección

### Maestro al crear ejemplos

`TEACHER_NAME` es `receding_horizon_ep` (`config.py`, líneas 11–16). `collect_order_transitions` le pasa la cola completa `remaining`, no solo la ventana `p` (`collect.py`, líneas 86–94). `receding_horizon_ep_index` ordena esa cola por volumen descendente, simula colocaciones legales hasta cubrir los ítems del buffer y restaura el snapshot (`teacher.py`, líneas 32–74). Si no proyecta una pose, cae en `privileged_volume_ep_index`, que elige el mayor volumen del buffer y la menor `rank_key` (líneas 17–29 y 95). El comentario de configuración dice que `privileged_volume_ep` es tautológico respecto al encoder y no está en `TRAINABLE_TEACHERS` (`config.py`, líneas 11–16). El notebook `02_etiquetas_maestro.ipynb` llama a `collect_dataset` sobre `data/train`, `data/val` y `data/test`.

Ese maestro ve identidades y dimensiones de ítems que el actor, con p=1, no ve, y además simula colocaciones que todavía no ocurrieron. Eso no le otorga al actor la misma información.

### Actor en inferencia

`DRLPolicy3DBPP.run` carga el checkpoint y llama a `run_online_loop` (`drl_policy_3d_bpp.py`, líneas 99–134). En ese bucle nadie llama a `label_index`. La observación es la descrita en las 35 características.

### Evaluación y selección

`fit_ppo` declara que la validación elige el actor y que test y holdout no entran (docstring, línea 418). Antes del bucle mide `volume_utilization` media del actor inicial sobre `val_ids` (`evaluate.py` devuelve esa métrica en la línea 191; `fit_ppo` la promedia en las líneas 480–482). Después de cada epoch 1…N vuelve a medirla y sustituye `best_state` solo si la media nueva supera a la guardada en más de `1e-12` (líneas 484–543). La métrica de selección es el resultado del empaquetado completo en validación, no una característica de entrada.

`assert_holdout_excluded` se aplica a train y val dentro de `fit_ppo` (líneas 425–426). El notebook `05_rl_ppo.ipynb` construye `ids_train` e `ids_val` desde `data/scale/train` y `data/scale/val`, y pasa esos ids a `fit_ppo`. Al terminar exporta `fit["state_dict"]` al path de producción. El notebook `03_imitacion.ipynb` entrena el inicial con `fit_mlp` sobre las transiciones de `data/train` y `data/val`, y elige por `val_acc` si `select_best` es `"val_acc"` (`train_mlp.py`, líneas 109–125). Esos directorios son el subconjunto working (`paths.py`, líneas 13–14).

## Selección del checkpoint y `best_epoch = 0`

En `fit_ppo`:

- `best_epoch` nace en 0 y `best_state` es una copia del actor cargado desde `init_path`, antes de cualquier actualización (líneas 471–473).
- El bucle de entrenamiento empieza en 1 (`for epoch in range(1, outer_epochs + 1)`, línea 484). El epoch 0 no es una pasada de PPO.
- El checkpoint de producción no lo escribe `fit_ppo`. Esa función exporta un scratch, lo usa para evaluar y lo borra (líneas 478–480 y 547–548). Quien persiste el actor elegido es el notebook 05, con el `state_dict` devuelto.
- `best_epoch = 0` significa que ningún epoch posterior superó la utilización media del actor inicial en `val_ids`. El `state_dict` devuelto es esa copia inicial.

No se deserializaron pesos. Tamaños o hashes de archivos no se usan como prueba de igualdad. La igualdad entre `mlp_v1_p1s1_ppo.pt` y el actor de imitación queda **no comprobada**.

En imitación, `best_epoch = 0` significa otra cosa: allí `best_state` empieza en `None` y solo se rellena si un epoch de validación mejora (`train_mlp.py`, líneas 71–74 y 121–125). Si ninguno mejora, el estado devuelto es el del último epoch, no el de la inicialización. No se aplica esa lectura al resultado de PPO.

## Auditoría de splits

Herramienta: `paper/tools/audit_split_exposure.py`. Salida: `paper/results/02_split_exposure.json`. Lee JSON. No lee `.pkl`.

Observado en los manifiestos presentes:

- Working 24/8/8, scale 80/20/20 y full 6999/1500/1499, como listas. Working y scale están contenidos en el full del mismo corte. Scale es el prefijo del full en train, val y test. Working y scale no comparten ids en train, ni en val, ni en test.
- No hay duplicados dentro de las listas de split. En `05_rl_ppo.json` cada id de `rows` aparece dos veces porque el informe guarda heurístico y actor; el auditor no lo cuenta como duplicado de split.
- Los ids de `rows` en 05 coinciden como conjunto con `scale` val y no coinciden con working val. `06` repite ese mismo `scale_val`.
- 00100408 está en `blocked_demo_ids`, en `holdout_producto/order_ids.json`, en el holdout de `06_evaluar_holdout.json`, en `order_ids` de `09_homologar_pct.json` y en `shared` de `10_comparar_pct.json`.
- No está en las listas train, val o test de working, scale o full que se leyeron.

Clases para 00100408:

- A. Pertenencia registrada a entrenamiento: no aparece en los manifiestos train leídos. Eso no demuestra que no se usara fuera de esos archivos.
- B. Uso registrado para validación o selección: no aparece en scale val, working val ni en las filas de 05.
- C. Evaluación posterior registrada: sí. Holdout de producto, informe 06, informes 09 y 10, y la captura 01C ya lo inspeccionó. No es un test confirmatorio sin mirar.
- D. Exposición desconocida: las transiciones `.pkl` no se abrieron y los checkpoints no se deserializaron. Puede haber exposición no escrita en estos JSON.

Los otros cuatro ids del holdout de producto están en el mismo informe 06. Tampoco sirven como confirmación no inspeccionada.

## Consecuencias para el experimento

Comparación homologable con el heurístico del mismo repositorio: los dos llaman a `run_online_loop`, al mismo generador y a la misma máscara (`online_3d_bpp_heuristic.py`, líneas 91–108, y `drl_policy_3d_bpp.py`, líneas 118–134). Hace falta el mismo pedido, el mismo `p` y `s`, y las mismas banderas. Con p=s=1 la heurística no tiene otros ítems en la ventana; elige por `rank_key` (`policies.py`, `GreedyBestFitPolicy`, líneas 33–61). El actor elige por la puntuación aprendida. Esa es la diferencia de política, no de generador.

Comparar contra un método externo exigiría, antes de producir resultados nuevos, fijar contenedor, orden de llegada, conjunto de orientaciones de seis permutaciones, comprobaciones activas y un plan que conserve las tres dimensiones colocadas. El adaptador yaw 0/1 de 01E rechaza la captura ya hecha de 00100408. No se elige aquí la métrica de esa comparación.

Reservar pedidos para una evaluación confirmatoria: los manifiestos full y scale tienen cortes test que no aparecen en 05, 06, 09 ni 10. No se revisó cada informe histórico ni los `.pkl`, así que su limpieza queda **no comprobada**. 00100408 y el holdout de producto ya tienen evaluación registrada. No se pueden presentar como no vistos.

Decisiones que faltan antes de fijar el protocolo: qué corte queda congelado como confirmatorio, si la comparación interna es solo p=s=1, si la estabilidad básica entra o sigue apagada, cómo se representa una orientación que no es yaw 0/1, y qué se hace con los ítems descartados al resumir un pedido. Este paso no cierra ninguna de esas decisiones y no afirma superioridad.

## Alcance de la comprobación

Se leyeron las funciones citadas en el árbol de `f4525b8`. No se ejecutó el bucle, no se generaron candidatas y no se compararon tensores. El JSON de exposición solo refleja los manifiestos que existen en disco.
