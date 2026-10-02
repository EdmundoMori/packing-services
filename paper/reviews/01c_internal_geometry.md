# Paso 01C — Geometría interna de una inferencia nueva

**Ejecución:** `01c-20261002T124527Z`
**UTC de la captura:** 2026-10-02T12:45:27Z
**Duración:** 2.905 s
**Rama:** `research/paper-online-packing`
**HEAD:** `d84ad596d6d8a7857dfcecb4470375905da21f4a`

Una sola inferencia diagnóstica. No es evaluación confirmatoria ni comparación con PCT. No se ha corregido el exportador ni el motor.

Al empezar, `git status --short` solo tenía los 17 `.pkl` sin seguimiento. Esos archivos siguen sin seguimiento.

## Receta efectiva

El notebook `09_homologar_pct.ipynb` hace `load_orders(DEMO_BED_BPP)`, `order_to_problem(..., lookahead_p=1, select_s=1, algorithm_name="drl_policy_3d_bpp", model_path=ckpt)` y `DRLPolicy3DBPP().run`. `DEMO_BED_BPP` es `examples/5_bed-bpp.json`. Ese archivo local contiene `00100408`.

SHA256 del dataset: `73116525448e167c87a1e82854b896c2d0f36ad2c0fd27b507e7b0c5c5c24a1f`.
SHA256 del checkpoint `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt`: `6139beb5c13c6a3f9c701626a1765cf690234f253c2a9b9e4c03185b0228ec24`.

Parámetros efectivos: `packing_mode=online`, `problem_type=3D_BPP`, `sort_strategy=input_order`, `selection=best_fit`, `lookahead_p=1`, `select_s=1`. El loader existente carga el `.pt` con `map_location="cpu"`. No se pidió CUDA.

Restricciones que salen de `_default_constraints` para `3D_BPP`, sin override en el notebook:

| Restricción | Efectiva |
|---|---|
| non_overlap | true |
| containment | true |
| allow_rotation | true |
| max_weight | true |
| basic_stability | false |
| load_bearing | false |
| fragility | false |
| unloading_sequence | false |

Soporte mínimo efectivo: `0.0`, porque `basic_stability` es false (`support_threshold`). Consolidación efectiva: false, porque hay un contenedor y el notebook no envía `consolidate` (`wants_consolidate`). Contenedor: `EURO_PALLET`, 1200×800×2000 mm, `max_weight` 1500 kg. Unidades del conversor: mm y kg.

Si ningún ítem del buffer cabe, `run_online_loop` descarta el más antiguo y sigue. El motivo guardado es «No hay colocación legal con el presupuesto de información actual». En esta ejecución no se descartó nadie.

La estabilidad física no se evaluó.

## Comandos

```text
.venv/bin/python -m unittest discover -s paper/tests -p 'test_audit_*.py'
/home/edmundo/packing-services/.venv/bin/python \
  /home/edmundo/packing-services/paper/tools/capture_internal_solution.py \
  --orders /home/edmundo/packing-services/examples/5_bed-bpp.json \
  --order-id 00100408 \
  --checkpoint /home/edmundo/packing-services/online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt \
  --output /home/edmundo/packing-services/paper/results/01c_internal_solution_00100408.json \
  --legacy-export /home/edmundo/packing-services/paper/results/01c_legacy_export_00100408.json
```

La captura se lanzó con el directorio de trabajo `/tmp` y rutas absolutas. Después:

```text
.venv/bin/python paper/tools/audit_internal_solution.py \
  --solution paper/results/01c_internal_solution_00100408.json \
  --output paper/results/01c_internal_audit_00100408.json \
  --legacy-export paper/results/01c_legacy_export_00100408.json \
  --historical-report online_policy_ml/artifacts/reports/09_homologar_pct.json \
  --order-id 00100408
.venv/bin/python paper/tools/audit_exported_plan.py \
  --report paper/results/01c_legacy_export_00100408.json \
  --order-id 00100408 --bin-mm 1200 800 2000 \
  --output paper/results/01c_legacy_export_audit_00100408.json
```

## Pruebas

`Ran 16 tests in 0.004s` — `OK`. Incluyen el rechazo de bins no finitos en el auditor 01A, sin cambiar la lectura yaw 0/1. El plan histórico 09 no se ha reescrito.

## 1. Geometría interna de esta ejecución

Auditor independiente, tolerancia `1e-6` mm. No usa `feasible` del motor como prueba.

| Magnitud | Valor |
|---|---|
| Entrada | 26 |
| Colocados | 26 |
| No colocados | 0 |
| Altura máxima | 1970 mm |
| Volumen colocado | 1241041750 mm³ |
| Cajas fuera del bin | 0 |
| Solapes en el mismo contenedor | 0 |
| `internal_geometry_valid` | true |
| `all_items_packed` | true |
| `physical_stability_verified` | null |

El `validation_report` del motor también dice `is_valid=true` y 0 violaciones. Queda registrado. No es la prueba geométrica de este paso.

## 2. Pérdida al exportar esta misma ejecución

`packing_plan_actions` de esta solución, auditado como yaw 0/1:

| Magnitud | Valor |
|---|---|
| Altura reconstruida | 1865 mm |
| Cajas fuera | 10 |
| Pares con solape | 19 |
| `exported_plan_geometry_valid` | false |

Las posiciones FLB coinciden con las internas (`n_position_mismatches=0`) y el orden de ids es el mismo. 24 de 26 colocaciones no caben en yaw 0/1. Ejemplo: `00101843#1` entra como 600×400×220 mm y queda colocado como 600×220×400 mm. El exportador escribe 400×600×220 mm. La altura colocada, 400 mm, se pierde y se conserva 220 mm.

## 3. Registro histórico

La inferencia reproduce el plan de `09_homologar_pct.json`: mismos 26 ids, mismas dimensiones originales, mismos FLB y los mismos flags 0/1 (`orientation_flag_diffs=0`). El defecto de conversión de esta ejecución es el del plan histórico. No hace falta atribuirlo a una colocación distinta.

## 4. Estabilidad física

No evaluada.

## 5. PCT

Esta pasada no compara con PCT.
