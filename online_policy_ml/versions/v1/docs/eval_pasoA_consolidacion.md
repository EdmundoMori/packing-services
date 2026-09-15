# Paso A: Disciplina de Consolidación en Multi-Pallet

> Independiente del pipeline `01`–`03` y del PPO. No reentrena. Si la disciplina cierra el
> defecto de la Fase 1, el producto con dos pallets no espera a un maestro consolidador
> ni a RL. El plan de modelado (PPO sobre un contenedor) está en [`../README.md`](../README.md) §7.

Pertenece a la pista de **evaluación de producto**. Índice: [`README.md`](README.md).

| | |
|---|---|
| **Flujo** | `eval_pasoA_consolidacion` |
| **Notebook** | `notebooks/10_consolidacion_multipallet.ipynb` |
| **Módulos** | `src_ml/consolidation.py`, `src/packing_services/online/policies.py` |
| **Estado** | Pendiente de ejecución |

---

## Objetivo

Cuantificar qué proporción del defecto descrito en la [Fase 1](eval_fase1_multipallet.md) se cierra
**sin reentrenar y sin modificar el modelo**.

La pregunta no es "cómo arreglamos el multi-pallet", sino una anterior y más útil: **¿el problema
está en el espacio de acciones o en la política?** La respuesta determina si hace falta aprender
una política de dos contenedores (fuera de este notebook) o basta la envolvente first-fit. El
plan de modelado vigente no es “B luego C”; es el PPO de un contenedor descrito en el README.

---

## Mecanismo

La clase `ConsolidatingPolicy` envuelve cualquier política del bucle online e impone disciplina
*first-fit*: mientras el contenedor abierto de índice más bajo admita alguna colocación legal, las
candidatas de los contenedores siguientes no se ponen sobre la mesa. Si ninguno de los contenedores
abiertos admite nada, se habilita el disponible de índice más bajo, que es el que corresponde abrir.

La política interna, sea el greedy o el MLP entrenado, **sigue eligiendo la pose exactamente como
antes**. La envolvente solo recorta el menú de opciones.

### Lo Que No Se Modifica

| Elemento | Estado |
|----------|--------|
| Encoder v1 (`FEATURE_VERSION=1`, `FEATURE_DIM=35`) | Intacto |
| Checkpoints `mlp_v1_p1s1.pt`, `mlp_v1_p3s2.pt` | Intactos, verificado por fecha de modificación |
| `run_online_loop` | Intacto; ya aceptaba el parámetro `policy` |
| `ExtremePointOnlineSession` | Intacta |
| Contrato de checkpoint `packing-services-online-policy` v1 | Intacto |
| Defaults del execute y de la API | Intactos |
| Algoritmos offline | Intactos |

La aportación al código de producción se limita a una clase nueva en `policies.py`, sin ningún punto
de llamada existente modificado.

---

## Diseño Experimental

Diseño **emparejado**: seis brazos sobre los cinco pedidos del holdout con dos contenedores
disponibles, es decir treinta corridas. Cada motor aparece dos veces, `libre` y `consolida`, con el
mismo checkpoint, el mismo presupuesto, el mismo bucle, el mismo validador y las mismas métricas. La
única diferencia entre los dos miembros de un par es la disciplina de contenedor.

| Motor | Presupuesto | Checkpoint |
|-------|-------------|------------|
| greedy | p=1, s=1 | ninguno |
| MLP por defecto | p=1, s=1 | `mlp_v1_p1s1.pt` |
| MLP de cinta | p=3, s=2 | `mlp_v1_p3s2.pt` |

El heurístico con lookahead `p=3` queda excluido deliberadamente: la Fase 0 midió 95 s en un pedido
de 26 ítems y más de 22 minutos en uno de 44, de modo que no es operable.

### Validación del Baseline

El brazo `libre` debe reproducir exactamente las cifras de la Fase 1, porque es el mismo código por
el mismo camino. El notebook lo comprueba contra la versión sellada de `eval_fase1_multipallet` y
advierte si no coincide. Una discrepancia invalidaría el resto de la tabla.

---

## Criterios de Parada

El paso se considera exitoso si se cumplen las cuatro condiciones:

1. **Ahorra pallets.** El total de contenedores abiertos disminuye.
2. **No deja más carga fuera.** Ningún pedido empaca menos ítems que con el brazo libre.
3. **Todo sigue válido.** Cero violaciones geométricas o de peso.
4. **No empeora el cubo** en ningún pedido.

La tercera y la cuarta condición son las que protegen contra un falso positivo: restringir el espacio
de acciones siempre reduce el número de pallets, pero podría hacerlo dejando carga fuera.

### Interpretación

| Resultado | Lectura | Consecuencia |
|-----------|---------|--------------|
| Exitoso | La brecha estaba en el espacio de acciones | El producto con dos pallets puede usar la envolvente; no hace falta un maestro consolidador |
| No concluyente | La disciplina no basta; hay una política que aprender | Queda como pista de producto aparte. No se mezcla con el primer PPO (un contenedor) |

El notebook calcula explícitamente la brecha restante contra el techo de un solo pallet medido en la
Fase 0 (70.9 % offline, 66.8 % online), que es la cifra que un paso posterior tendría que superar.

---

## Ejecución

```bash
cd packing-services
source .venv/bin/activate
cd online_policy_ml/notebooks
jupyter notebook 10_consolidacion_multipallet.ipynb
```

La celda de ejecución tarda unos minutos e imprime el progreso pedido a pedido. La última celda sella
el resultado en el registro de versiones, marcándolo `validado` únicamente si los cuatro criterios
pasaron.

El notebook del Paso A es `notebooks/10_consolidacion_multipallet.ipynb`. No forma parte del pipeline 01–03. Se abre y se ejecuta con Jupyter.

### Verificación Previa del Mecanismo

La disciplina tiene pruebas unitarias independientes del experimento, que reproducen el defecto en un
caso mínimo y comprueban que la envolvente consolida sin bloquear:

```bash
PYTHONPATH=src python -m pytest tests/test_consolidating_policy.py -q
```
