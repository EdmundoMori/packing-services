# Paso 00 — Inventario y trazabilidad

**Ejecución:** `inv-00-20261002T122453Z`
**UTC:** 2026-10-02T12:24:53Z
**Estado:** completed

Solo inspección. No se entrenó, no se instaló nada, no se descargaron datos, no se ejecutaron notebooks ni tests, no hubo commit, push ni pull.

No hay `AGENTS.md` en el árbol del repositorio (búsqueda por nombre; observado).

## Resumen

El HEAD local es el commit de referencia. La rama es `main`. Antes de este paso el árbol ya estaba sucio solo por 17 `.pkl` sin seguimiento. Los 15 archivos pedidos existen. `05_rl_ppo.json` declara `best_epoch=0`. La comparación `vs_heuristic` de ese JSON tiene 20 pedidos y coincide con `scale.val` de `01_splits.json`, no con `working.val` (8).

## Comandos ejecutados

Desde `/home/edmundo/packing-services`, salvo el primero de sistema.

| Comando | Resultado relevante |
|---|---|
| `uname -a` | Linux, kernel `6.6.87.2-microsoft-standard-WSL2`, `x86_64`. El nombre de host no se copia. |
| `git rev-parse --show-toplevel` | `/home/edmundo/packing-services` |
| `git rev-parse HEAD` | `7de7c1037248fa0c207fa7de7908149d72c3a34c` |
| `git branch --show-current` | `main` |
| `git status --short` (antes) | 17 rutas `??` de `transitions_*.pkl` bajo `online_policy_ml/versions/v1/data/` |
| `git log -1 --format="%H%n%cs%n%s"` | mismo hash; fecha `2026-09-15`; asunto `feat: cierra el ciclo RL online, el .pt de API y la comparación con PCT` |
| `git remote -v` | fetch y push: `git@github.com:EdmundoMori/packing-services.git`. Sin credenciales en la URL. |
| `date -u` | `2026-10-02T12:24:53Z` al cerrar el registro |
| `.venv/bin/python` + `importlib.metadata` | Python 3.10.12; 16 CPU lógicas; torch `2.14.0+cpu`; numpy `2.2.6`; pytest `9.1.1`; pydantic `2.13.4`. Torch no se importó. |
| `command -v git-lfs` | no está en PATH |
| `git lfs version` | error real: `fatal: 'lfs' appears to be a git command, but we were not able to execute it` |
| `nvidia-smi` | GPU 0: NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB. UUID no copiado. |

`pyproject.toml` exige `requires-python >= 3.10`. El intérprete del proyecto es `.venv/bin/python` (enlace a `python3`). También existe `/usr/bin/python3`; no se usó para las versiones de paquetes.

La primera llamada a `nvidia-smi` dentro del sandbox devolvió `Failed to initialize NVML: GPU access blocked by the operating system`. La repetición fuera del sandbox sí obtuvo nombre y memoria. Se registra la segunda.

## Diferencia respecto al commit de referencia

**Observado:** HEAD es idéntico a `7de7c1037248fa0c207fa7de7908149d72c3a34c`. No se cambió.

**Observado:** no hay archivos rastreados modificados. Hay 17 `.pkl` sin seguimiento que ya estaban antes de escribir `paper/`. No se han añadido, borrado ni restaurado.

## Archivos pedidos

| Ruta | Existe | Bytes |
|---|---|---|
| `src/packing_services/online/loop.py` | sí | 3069 |
| `src/packing_services/online/session.py` | sí | 4166 |
| `src/packing_services/online/features.py` | sí | 3754 |
| `src/packing_services/online/policies.py` | sí | 6645 |
| `src/packing_services/algorithms/_extreme_points.py` | sí | 9255 |
| `online_policy_ml/src_ml/bedbpp_eval.py` | sí | 12656 |
| `online_policy_ml/src_ml/train_ppo.py` | sí | 20293 |
| `online_policy_ml/src_ml/teacher.py` | sí | 3976 |
| `online_policy_ml/src_ml/config.py` | sí | 1894 |
| `online_policy_ml/artifacts/reports/01_splits.json` | sí | 3779 |
| `online_policy_ml/artifacts/reports/05_rl_ppo.json` | sí | 18087 |
| `online_policy_ml/artifacts/reports/09_homologar_pct.json` | sí | 11112 |
| `online_policy_ml/artifacts/reports/10_comparar_pct.json` | sí | 3048 |
| `online_policy_ml/artifacts/models/mlp_v1_p1s1.pt` | sí | 12037 |
| `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt` | sí | 12077 |

No existía `paper/` antes de este paso.

## Checkpoints (sin deserializar)

| Archivo | Bytes | SHA256 |
|---|---|---|
| `mlp_v1_p1s1.pt` | 12037 | `0c17dc62e9a9fcb10ae1bfe2b1e02113977f9730c348c8d84daa214f11870aa6` |
| `mlp_v1_p1s1_ppo.pt` | 12077 | `6139beb5c13c6a3f9c701626a1765cf690234f253c2a9b9e4c03185b0228ec24` |

**No comprobado:** que los pesos sean distintos. El tamaño y el hash difieren; la serialización puede diferir con los mismos pesos. No se cargaron los `.pt`.

## Campos JSON leídos

`01_splits.json` (observado):

- `fase` 1, `seed` 42, `n_orders_source` 10003.
- `full_split_counts`: train 6999, val 1500, test 1499.
- `working_counts`: train 24, val 8, test 8.
- `scale_counts`: train 80, val 20, test 20.
- `blocked_demo_ids`: cinco ids (`00100001`–`00100004`, `00100408`).
- El campo `source` existe. No se copia la ruta local.

`05_rl_ppo.json` (observado):

- `fit.best_epoch` = 0.
- `fit.best_val_util` = 0.6874582.
- `fit.history`: 6 filas, epochs 1 a 6. El epoch 0 no está en `history`.
- `fit.init_path` termina en `mlp_v1_p1s1.pt`.
- `fit.lookahead_p` = 1, `fit.select_s` = 1.
- `vs_heuristic.n_paired` = 20; `order_ids` tiene longitud 20.
- `vs_heuristic.mean_a` = 0.6874582 (igual numéricamente a `best_val_util`).
- `mean_delta` = 0.01302855; `significant` = false.

Comparación de conjuntos, sin listar ids (observado): los 20 ids de `vs_heuristic` son exactamente `scale_ids.val`. Intersección con `working_ids.val` = 0.

`config.py` (observado, no ejecutado): `WORKING_COUNTS` val 8 y `SCALE_COUNTS` val 20.

`05_rl_ppo.ipynb` (observado en fuente, no ejecutado): el texto dice que la val de `data/scale` elige el actor, y el código carga `scale_split_dir("val")`.

`generar_informe_word.py` (observado): afirma que el working set (24/8/8) se usa para 01–05 y que scale queda como reserva no promocionada. Eso no coincide con el notebook 05 ni con los 20 ids del JSON.

`09_homologar_pct.json`: claves de primer nivel presentes (`marco_zhao`, `nuestro`, `pct`, `order_ids`, entre otras). No se reabren cifras.

`10_comparar_pct.json` (observado, no reinterpretado): `shared` = [`00100408`]; `columna_decisoria` = `feasible`; `uti_head_to_head` = false; `lado` = `supera`. Es el veredicto histórico, no una conclusión de este paso.

## Procedencia aparente de `best_epoch`

**Observado:** el JSON guarda 0 y la historia empieza en 1.

**Inferido, leyendo `train_ppo.py` sin ejecutarlo:** `best_epoch` se inicializa a 0, se mide la utilización del actor inicial sobre `val_ids`, y solo pasa a un epoch ≥ 1 si un epoch posterior la supera. El 0 del JSON es compatible con “ningún epoch PPO superó esa medición”. No se ha vuelto a correr el entrenamiento.

**No comprobado:** que el `.pt` de API sea byte a byte el actor BC.

## Cuestiones de la revisión previa

| Cuestión | En este paso |
|---|---|
| `session.py` usa `ExtremePointPacker` y no hay que asumir EMS | No comprobado. El archivo existe; no se leyó el cuerpo. |
| `loop.py` descarta un ítem que no cabe y sigue | No comprobado. El archivo existe; no se leyó el cuerpo. |
| `bedbpp_eval.py` exporta orientaciones 0/1 | No comprobado. El archivo existe; no se releyó la exportación. |
| `best_epoch=0` | Observado en `05_rl_ppo.json`. |
| working.val 8 frente a scale.val 20 | Observado. Ambos constan en `01_splits.json`. El conjunto de validación emparejado en `05` es `scale.val`. |

## Incertidumbres para un paso posterior

- Si la GPU de `nvidia-smi` es usable: el metadato de torch dice `+cpu` y no se importó torch.
- Git LFS no ejecuta. Cualquier puntero LFS sigue sin materializar.
- Hashes distintos de los `.pt` no prueban pesos distintos.
- Los cinco puntos de comportamiento de `loop.py`, `session.py` y orientaciones siguen sin leer en este paso.
- No se atribuyen definiciones de Uti., ηutil o factibilidad a Zhao ni a Kagerer: esos PDF no se han abierto en esta ejecución.
