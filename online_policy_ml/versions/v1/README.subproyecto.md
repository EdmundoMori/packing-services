# Política online aprendida

Documento canónico del subproyecto. Si otro texto de esta carpeta o un `.docx` local discrepa, vale **este archivo** y el código de `src_ml/`.

El repositorio **packing-services** compara metodologías de Cutting and Packing sobre la misma entrada, el mismo validador y las mismas métricas. Aquí se **entrenan y exportan** los checkpoints del modo `packing_mode=online`. El execute de producción solo los carga; no reentrena.

El default de producción sigue siendo **imitación P2O** (`mlp_v1_p1s1.pt`). El RL es fine-tuning PPO de ese mismo actor (notebook `05`). En la plataforma se elige con `parameters.policy=rl` o `POST /api/v1/online/rl/execute`; no hay un algoritmo nuevo en el catálogo.

---

## 1. Estado (12 de septiembre de 2026)

| Pieza | Estado |
|-------|--------|
| Pipeline de entrenamiento | `01` → `02` → `03` ejecutado con metodología corregida |
| Compuerta del maestro | `04` ejecutado: maestro 0.6784 vs heurístico 0.6826 vs MLP 0.6865. Empate. **Decisión: PPO** |
| Maestro | `receding_horizon_ep` (informativo; no tautológico) |
| Checkpoints | `mlp_v1_p1s1.pt` (imitación), `mlp_v1_p3s2.pt`, `linear_v1.json`, `mlp_v1_p1s1_ppo.pt` (tras `05`) |
| Calidad vs heurístico | Empate estadístico en holdout (imitación). PPO no promociona el default hasta IC |
| Evaluación multi-pallet (notebook `10`) | Código listo; no forma parte del reentreno |
| RL (PPO) | `05` denso+scale (val n=20): PPO 0.6802 · imitación 0.6733 · heurístico 0.6695. IC cruza cero. **No promocionar. No repetir el mismo PPO.** |

**Lectura honesta:** el proceso es válido. El modelo es un baseline comparable al heurístico, no un packer mejor. No se reejecuta `01`–`03` para “ganar décimas” sobre los mismos 8 pedidos de validación.

---

## 2. Cómo se ejecuta el pipeline

Desde `online_policy_ml/notebooks/`, un notebook cada vez, **Restart Kernel and Run All**, en este orden:

```bash
cd packing-services
source .venv/bin/activate
cd online_policy_ml/notebooks
jupyter notebook 01_datos_y_splits.ipynb
# al terminar OK → 02_etiquetas_p2o.ipynb (largo: el maestro receding es caro)
# al terminar OK → 03_entrenar_validar_exportar.ipynb
# al terminar OK → 04_compuerta_maestro.ipynb (solo val; el maestro es lento)
# al terminar OK → 05_ppo_finetune.ipynb (PPO; minutos)
```

Alternativa: `python _execute.py 01` (luego `02`, `03`, `04`, `05`).

| Notebook | Qué hace | Artefacto |
|----------|----------|-----------|
| `01_datos_y_splits.ipynb` | Inventario BED-BPP, holdout bloqueado, split 70/15/15 estratificado por target, muestra aleatoria 24/8/8 | `data/train\|val\|test/`, `data/holdout_producto/`, `artifacts/reports/01_splits.json` |
| `02_etiquetas_p2o.ipynb` | Transiciones P2O con el bucle real del repo; maestro `receding_horizon_ep` | `data/*/transitions_pXsY.pkl`, `artifacts/reports/02_transitions.json` |
| `03_entrenar_validar_exportar.ipynb` | Lineal y MLP; val para early stopping; test y holdout no tunan | `artifacts/models/`, `artifacts/reports/03_validacion.json` |
| `04_compuerta_maestro.ipynb` | Maestro RH vs MLP vs heurístico en val. Decide destilar o PPO | `artifacts/reports/04_compuerta_maestro.json` |
| `05_ppo_finetune.ipynb` | Fine-tuning PPO del MLP p=1,s=1. Exporta el checkpoint RL | `mlp_v1_p1s1_ppo.pt`, `artifacts/reports/05_ppo.json` |

El notebook `10_consolidacion_multipallet.ipynb` es **evaluación de producto** (disciplina first-fit con dos pallets). No se mete entre 01 y 05.

---

## 3. Módulos (`src_ml/`)

Solo estos archivos sirven al pipeline 01–05:

| Módulo | Rol |
|--------|-----|
| `bootstrap.py` | `sys.path` y carpetas |
| `config.py` | Semilla 42, maestro, tamaños, hiperparámetros |
| `paths.py` | Rutas bajo `online_policy_ml/` |
| `splits.py` | Carga BED-BPP, split, materialización |
| `problems.py` | Pedido → `PackingProblem` |
| `teacher.py` | Etiqueta del maestro |
| `collect.py` | Colecta transiciones (mismo bucle que producción) |
| `methodology.py` | Compuertas: holdout, fuga de objetivo, colinealidad, sobreajuste, promoción |
| `train_linear.py` | Lineal, init en ceros, early stopping en val |
| `train_mlp.py` | `Linear(35, 64) → ReLU → Linear(64, 1)` |
| `train_ppo.py` | Fine-tuning PPO del actor `mlp_v1`; critic solo en entrenamiento |
| `train_mlp_numpy.py` | El mismo MLP si no hay torch |
| `export_ckpt.py` | Contrato `packing-services-online-policy` v1 |
| `evaluate.py` | Empaquetado online: modelo vs heurístico vs maestro |
| `select.py` | Epoch por utilización en val |

Fuera del entrenamiento (evaluación): `consolidation.py`, `registry.py`.

### Contrato que no se toca

- Encoder v1: `FEATURE_VERSION=1`, `FEATURE_DIM=35`, `encode_option`
- Loader: `mlp_v1` = Linear(35, 64) → ReLU → Linear(64, 1)
- Checkpoint: `packing-services-online-policy` v1
- Bucle `run_online_loop` y el validador de producción
- Offline (`volume_desc`) y catálogo de 31 motores
- Geometría europalé BED-BPP 1200×800×2000 mm
- Holdout de producto: `00100001`, `00100002`, `00100003`, `00100004`, `00100408`

---

## 4. Metodología (lo que se corrigió)

Una primera versión del pipeline (notebooks 01–05 históricos) usaba el maestro `privileged_volume_ep`. Esa etiqueta es una función cerrada de seis features (`item_vol_n`, `rank_0…3`, `buffer_index_n`): se recuperaba al **100 %** sin aprender a empaquetar. El 99 % de accuracy era un artefacto. Las fases 4 (escala con el mismo maestro) y 5 (receding solo en p=3,s=2) se absorbieron.

El pipeline actual impone, en código:

1. **Holdout fuera** de train, val, test, colecta y selección de epoch.
2. **Maestro entrenable** solo `receding_horizon_ep`. `collect_dataset` y `fit_*` rechazan etiquetas tautológicas (regla cerrada ≥ 98 %).
3. **Split estratificado** por target (`euro-pallet` / `rollcontainer`) y subconjunto de trabajo **aleatorio**, no los pedidos más cortos.
4. **Val obligatorio** para early stopping. Test y holdout no eligen epoch.
5. **Promoción** solo si un IC emparejado por pedido excluye el cero (`methodology.assert_can_promote`).
6. Colinealidad estructural `pos_*_n` ≈ `rank_1…3` y features constantes (`bin_index_n` con un contenedor, `preview_*` en p=1) se **diagnostican**; no se borran (el encoder v1 es contrato).

El target es **multiclase de tamaño variable**: el índice de la candidata legal que eligió el maestro. La red produce un escalar por opción y el softmax va sobre el conjunto del paso.

---

## 5. Resultados del run corregido

Cifras de `artifacts/reports/01_splits.json`, `02_transitions.json`, `03_validacion.json` y una pasada posterior al holdout con el mismo juez. n=8 (val/test) y n=5 (holdout): las diferencias de décimas **no son significativas**.

### Datos (01)

- Fuente: 10 003 pedidos BED-BPP v1 (mediana 43 ítems).
- Split completo: train 6 999 / val 1 500 / test 1 499. Holdout bloqueado.
- Trabajo: 24 / 8 / 8, media de ítems 44.2 / 47.9 / 56.9 (representativo; ya no ~13).

### Etiquetas (02)

- Maestro `receding_horizon_ep`, `label_rate` 1.0, `FEATURE_VERSION=1`.
- Train p=1,s=1: 1 006 transiciones, ~40 opciones/paso, 656 s.
- Train p=3,s=2: 1 011 transiciones, ~81 opciones/paso, 1 197 s.
- Regla cerrada sobre estas etiquetas: **33–37 %** (informativo).

### Imitación (03)

| Modelo | Régimen | Acc. train | Acc. val | Criterio |
|--------|---------|------------|----------|----------|
| Lineal | p=1,s=1 | 0.349 | 0.362 | early stop val |
| MLP | p=1,s=1 | — | 0.334 | `val_loss`, epoch 3 |
| MLP | p=3,s=2 | — | 0.322 | `val_loss`, epoch 4 |

Con 40–80 clases por paso, el azar es ~2–3 %. El modelo imita en parte al maestro; no lo copia.

### Empaquetado (mismo validador)

Validación p=1,s=1 (8 pedidos): placeholder 0.6873 · MLP 0.6865 · heurístico 0.6826 · lineal 0.6671. Todas las soluciones válidas.

Test p=1,s=1 (8 pedidos): heurístico **0.6714** · MLP 0.6679.

Holdout de producto p=1,s=1 (5 pedidos, no se usó para tunear):

| Motor | Utilización | Ítems |
|-------|-------------|-------|
| Heurístico | **0.6682** | **187** |
| MLP `p1s1` | 0.6668 | 186 |
| Placeholder | 0.6629 | 186 |
| Lineal | 0.6545 | 183 |

MLP vs heurístico: Δ −0.0014 (IC95 −0.025 a +0.019). Empate. Smoke `00100408`: 26/26, válido, 64.6 % (el pedido cabe entero; esa utilización no discrimina).

Cinta p=3,s=2 en el 03 solo se midió en **3** pedidos de val: no se afirma superioridad. El heurístico tardó ~218 s; el MLP ~2 s.

---

## 6. Evaluación de producto (pista aparte)

Documentos en [`docs/`](docs/README.md). Las fases 0 y 1 de evaluación se midieron sobre **checkpoints anteriores** a la corrección del maestro (septiembre 2026, primer ciclo). El hallazgo de método sigue vigente:

- `volume_utilization` no separa cargas cuando el pedido cabe en un pallet.
- Con dos contenedores, los motores por puntos extremos **reparten** la carga (el suelo vacío del segundo pallet gana por área de contacto). No es un hueco de tuneo; es ausencia de disciplina de consolidación más una distribución de entrenamiento de un solo contenedor.

El notebook `10` prueba la envolvente `ConsolidatingPolicy` sin reentrenar. Pendiente de que se ejecute.

---

## 7. RL: qué se hizo y qué falta

El default de producción sigue siendo imitación. `policy=rl` carga `mlp_v1_p1s1_ppo.pt` si existe. No se promociona.

### Compuerta 04 y run 05

Val p=1,s=1, n=8: heurístico 0.6826 · imitación 0.6865 · maestro RH 0.6784 · PPO 0.6965.
PPO vs heurístico: Δ +0.0139, IC95 [−0.0008, +0.0286]. No significativo.

### Entrenamiento vigente (mismo notebook `05`)

Ya está en `train_ppo.py` / `05_ppo_finetune.ipynb` (sin archivos nuevos):

1. Recompensa **densa** (volumen del ítem / volumen del contenedor) y penalización solo al descartar.
2. Train scale **80** pedidos, **2** rollouts, `lr=1e-4`, `γ=0.99`.
3. Val scale **20** para el IC. Test y holdout sellados.

Hay que volver a ejecutar `05`. Si el IC sigue cruzando cero, el techo está en el scorer de 35 features, no en “falta PPO”.

### Qué no entra

- RL desde cero o pesos de PCT/GOPT (otra geometría, otro estado).
- Recompensa “copia al maestro” (es BC).
- Multi-pallet como recompensa de este PPO (notebook `10`).

---

## 8. Checkpoints y API

Rutas relativas a la raíz del repo:

| Uso | Ruta | Régimen |
|-----|------|---------|
| Online por defecto (imitación) | `online_policy_ml/artifacts/models/mlp_v1_p1s1.pt` | p=1, s=1 |
| RL (PPO, opción) | `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` | p=1, s=1 |
| Cinta | `online_policy_ml/artifacts/models/mlp_v1_p3s2.pt` | p=3, s=2 |
| Sin PyTorch | `online_policy_ml/artifacts/models/linear_v1.json` | p=1, s=1 |
| Humo (no es producción) | `examples/online_policy_linear_v1.json` | — |

```text
POST /api/v1/algorithms/drl_policy_3d_bpp/execute   # parameters.policy=imitation|rl
POST /api/v1/online/learned/execute                 # imitación P2O
POST /api/v1/online/rl/execute                      # RL (PPO)
```

En la web-demo (Ejecutar, modo online, `drl_policy_3d_bpp`) hay un selector **Imitación (P2O)** / **RL (PPO)**.

MLP: `pip install torch` o `packing-services[torch]`.

---

## 9. Qué se eliminó de la documentación

Los archivos `docs/fase1.md`–`fase5.md` describían el pipeline tautológico (pedidos más cortos, maestro de volumen, fase 4/5 como mejoras) y se eliminaron. Los informes `.docx` locales del primer ciclo también: el markdown de esta carpeta es la única fuente.

El índice corto de evaluación está en [`docs/README.md`](docs/README.md).
