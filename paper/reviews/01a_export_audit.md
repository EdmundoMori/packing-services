# Paso 01A — Auditoría de la geometría del plan exportado

**Ejecución:** `01a-20261002T123642Z`
**UTC:** 2026-10-02T12:36:42Z
**Estado:** completed
**Rama:** `research/paper-online-packing`
**HEAD:** `7de7c1037248fa0c207fa7de7908149d72c3a34c`

No se ha corregido el exportador, no se ha regenerado el reporte 09 y no se han cargado checkpoints.

## Cambios preexistentes

Antes de crear la rama, `git status --short` en `main` mostraba 17 `.pkl` sin seguimiento y `paper/` sin seguimiento. Ningún archivo rastreado estaba modificado. HEAD era el commit esperado.

`research/paper-online-packing` no existía. `git checkout -b research/paper-online-packing` la creó en ese mismo HEAD. Los `.pkl` y `paper/` siguieron sin seguimiento. No hubo reset, clean ni stash.

## Qué genera y qué exporta las orientaciones

**Observado en código, no ejecutado en esta pasada:**

- `unique_orientations` (`src/packing_services/domain/geometry.py`, líneas 76–93) genera hasta seis permutaciones de `(l, w, h)` si `allow_rotation` es verdadero.
- `ExtremePointOnlineSession.orientations_for` (`src/packing_services/online/session.py`, líneas 49–51) llama a esa función.
- `candidates` (líneas 53–79) prueba cada permutación en los puntos extremos.
- `as_packed_item` (líneas 81–96) guarda en `PackedItem.orientation` las tres dimensiones de la candidata, no un flag 0/1.
- `packing_plan_actions` (`online_policy_ml/src_ml/bedbpp_eval.py`, líneas 43–67) escribe siempre `item.length/width/height` originales. Pone `orientation=1` si la longitud o la anchura colocadas difieren de las originales (líneas 52–63). No escribe la altura colocada.
- `kpis_zhao` (líneas 82–119) mide el bin con las dimensiones de `packed.orientation`, no con el flag 0/1.
- `kpis_zhao_from_plan` (líneas 122–163) sí interpreta 0 como dimensiones originales y 1 como intercambio de length/width, conservando height (líneas 139–142).
- En el notebook `09_homologar_pct.ipynb` (fuente, no reejecutado), la fila `nuestro` sale de `kpis_zhao(problem, solution)` y el plan sale aparte de `packing_plan_actions`.

**Inferido:** un giro que cambie la altura cabe en las seis permutaciones internas, pero el exportador lo aplasta a yaw 0/1 y conserva la altura original. Esta pasada no ha vuelto a colocar el pedido, así que no demuestra cuál permutación usó cada caja.

**No leído:** los PDF de Zhao y de Kagerer. No se les atribuye la definición de Uti. ni de ηutil.

## Estructura observada del JSON 09

`packing_plan_nuestro` es un diccionario. La clave `00100408` es una lista de 26 acciones. Cada acción tiene `item` (`id`, `length`, `width`, `height`, `weight`), `orientation` y `flb_coordinates`. Las orientaciones presentes son solo 0 y 1.

`nuestro` es una lista de un objeto. Se contrastó el objeto con `order_id=00100408`. No se inventaron claves.

## Comandos

```text
git status --short
git checkout -b research/paper-online-packing
.venv/bin/python -m unittest discover -s paper/tests -p 'test_audit_exported_plan.py'
.venv/bin/python paper/tools/audit_exported_plan.py \
  --report online_policy_ml/artifacts/reports/09_homologar_pct.json \
  --order-id 00100408 \
  --bin-mm 1200 800 2000 \
  --output paper/results/01a_export_audit_00100408.json
```

## Pruebas

`Ran 6 tests in 0.001s` — `OK`.

Cubren contacto de caras, solape estricto, caja dentro y caja fuera, yaw que cambia length/width, id duplicado y orientación distinta de 0/1. No usan cifras del pedido real. El auditor no importa `bedbpp_eval.py`. Tolerancia registrada: `1e-6` mm. El contacto de caras no cuenta como solape.

## Resultado en 00100408

Interpretando el plan exportado como yaw 0/1, bin 1200×800×2000 mm:

| Magnitud | Valor |
|---|---|
| Cajas parseadas | 26 |
| Errores de esquema | 0 |
| IDs duplicados | 0 |
| Altura máxima reconstruida | 1865 mm |
| Volumen total reconstruido | 1241041750 mm³ |
| Cajas fuera del bin | 10 (9 exceso en Y, 1 exceso en X; ninguno en Z ni por debajo de 0) |
| Pares con solape | 19 de 325 |
| `exported_plan_geometry_valid` | false |
| `internal_solution_valid` | null |

Estas cifras coinciden con la comprobación previa (1865 mm, 10 fuera, 19 solapes). No se forzaron: salieron del script.

## Contraste con lo que el reporte 09 dice de la solución interna

| Campo interno | Reportado | Reconstrucción 0/1 |
|---|---|---|
| `hn_m` | 1.97 m (1970 mm) | 1865 mm (diferencia −105 mm) |
| `n_fuera_bin` | 0 | 10 |
| `feasible` | true | el plan exportado no es válido |
| `packed_volume_in` | 1241041750 | el volumen reconstruido es el mismo |
| `num` / `items_packed` | 26 | 26 cajas parseadas |

El volumen coincide porque intercambiar length y width no cambia el producto. Eso no demuestra que la altura colocada sea la original.

## Qué demuestra y qué no

**Demuestra:** bajo el esquema 0/1 del propio exportador, `packing_plan_nuestro` de `00100408` no es una geometría válida: hay cajas fuera de la huella y pares con intersección positiva en los tres ejes. La altura de esa reconstrucción no es la `hn_m` guardada en `nuestro`.

**No demuestra:** que la solución interna sea inválida. `kpis_zhao` usa las tres dimensiones colocadas; este auditor no las tiene. `internal_solution_valid` queda null. Tampoco demuestra que el selector gane o pierda frente al heurístico o frente a PCT, ni corrige el exportador.
