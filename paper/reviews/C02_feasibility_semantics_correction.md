# C02 — Corrección de semántica de factibilidad (`bedbpp_eval`)

**Fecha:** 2026-10-06
**HEAD de trabajo:** `49c10846467d80607214e5f053a72c1851365369`
**Rama:** `research/paper-online-packing`
**Alcance:** `online_policy_ml/src_ml/bedbpp_eval.py` + pruebas + esta revisión.
**No altera:** JSON/informes históricos 09/10, capturas, protocolos, checkpoints, campañas cerradas, `packing_plan_actions`, motores de producción.

## Defectos reproducidos (pre-C02)

1. `kpis_zhao` / `kpis_zhao_from_plan`: `feasible = (n_fuera==0 ∧ hn≤H)` **sin** comprobar solapes → un plan con solapes y cajas «dentro» podía ser `feasible=true`.
2. `pct_zhao_publicado`: exigía `nu==0` para `feasible`, confundiendo completitud con validez geométrica.
3. Altura (`hn`) y `nu` no demuestran contención lateral ni ausencia de solapes; aun así se asignaba factibilidad.
4. `veredicto_zhao` emitía «supera»/«empata»/«inferior» usando solo `feasible` histórico, sin evidencia de protocolos homologados (p. ej. informe 09/10 sobre `00100408`).

## Semántica anterior vs nueva

| Concepto | Antes (v1 implícita) | Ahora (`schema_version=2`) |
|----------|----------------------|----------------------------|
| `feasible` | `n_fuera==0` y `hn≤H` (y `nu==0` en publicado) | Compatibilidad: `true` solo si `geometry_valid is True`; `false` si `geometry_valid is False`; `null` si falta evidencia. **No** exige `all_items_packed`. |
| Solapes | No comprobados | `non_overlap_valid`; contacto de caras permitido |
| Contención | Solo por caja vía `_inside` (sí), pero sin solape | `containment_valid` + solapes |
| Publicado sin plan | `feasible` por hn+nu; `n_fuera_bin=0` si «factible» | `geometry_valid=null`; `n_fuera_bin=null`; `nu` → completitud; `evaluator_height_limit_exceeded` si hn>H **sin** invalidar Kagerer |
| Veredicto | Superioridad por feasible | `comparison_valid` exige homologación explícita + contrato + geometría/uti validadas; default `no_compara` |

### `geometry_valid=true` (definición exacta)

Todas a la vez:

- sin errores de parseo (finitos, dims > 0, esquema FLB/orientación según entrada);
- `containment_valid is True` (todas las cajas colocadas dentro del AABB del bin);
- `non_overlap_valid is True` (sin intersección de volumen > ε; contacto de caras OK);
- `identity_valid is True` (sin IDs duplicados entre colocados);
- `orientation_valid is not False` (si se comprobó y falló → no válido; si no hay evidencia → `null` y no bloquea).

**No** es «factibilidad completa» Zhao/Kagerer: no incluye estabilidad física, peso, ni el protocolo ICLR íntegro. `physical_stability_verified` permanece `null`.

Packing parcial: puede tener `geometry_valid=true` y `all_items_packed=false`. Plan vacío con pedido no vacío: geometría vacua válida, completitud falsa.

Planes inválidos: `uti`/`packed_volume_in`/`num` validados → `null`; volúmenes en `diagnostic_*` con `metric_status=diagnostic_only_…`.

## Esquema de salida (v2)

Campos de validez: `containment_valid`, `non_overlap_valid`, `orientation_valid`, `identity_valid`, `geometry_valid`, `all_items_packed`, `physical_stability_verified`, `comparison_valid`, más `feasible` (compatibilidad) y `feasible_meaning`.

Metadatos: `schema_version=2`, `evaluator_contract`, `migration_note`, `yaw01_is_not_six_permutations`.

Comparación: `comparison_evidence_requirements()` documenta lo exigido; **no** hay bandera por defecto que autorice el veredicto histórico.

## Justificación de validación local

Se **reutiliza la lógica** del auditor de planes exportados (ε, contacto de caras, yaw 0/1) **sin** importar `paper/tools/audit_*.py`: el auditor congelado no se modifica y se evita dependencia de producción/ML hacia scripts de `paper/`. Duplicación deliberada y documentada.

`packing_plan_actions` no se toca (C03: exportación yaw).

## Consumidores afectados

| Consumidor | Efecto si se reejecuta |
|------------|-------------------------|
| `notebooks/09_homologar_pct.ipynb` | Filas KPI con nuevos campos; `feasible`/`uti` pueden diferir; veredictos → `no_compara` sin homologación explícita |
| `notebooks/10_comparar_pct.ipynb` | Idem vía `tabla_comparacion` / `veredicto_zhao` |
| `artifacts/reports/09_*.json`, `10_*` | **Preservados**; no regenerados |
| `paper/tools/capture_internal_solution.py` | Solo usa `packing_plan_actions` (sin cambio) |
| `docs/generar_informe_word.py` | Texto histórico; no regenerado |
| Auditores `paper/tools/audit_*` | Independientes; pruebas siguen OK |

## Pruebas

`online_policy_ml/tests/test_bedbpp_eval_feasibility.py` — 23 casos (solape, contacto, dentro/fuera, parcial, vacío, ID duplicado/desconocido, NaN/Inf/negativo, orientación/yaw, rotación prohibida, publicado hn≤H/hn>H, nu>0, comparación con/sin flags, diagnósticos, coherencia null, bin inválido, solución interna).

Auditores existentes: `paper.tests.test_audit_exported_plan` + `test_audit_internal_solution` — OK.

## Limitaciones

- No corrige el exportador yaw ni regenera 09/10.
- Validación AABB axis-aligned; no estabilidad.
- Publicado sin plan nunca alcanza `geometry_valid=true`.
- Este módulo **no** establece `comparison_valid=true`: secuencia/terminación/ICLR no verificables desde KPI.

## Evidencia histórica preservada

Informes/JSON 09–10, capturas, protocolos, checkpoints y cierres de campaña intactos.
## Cierre de revisión (mismo HEAD base)

Comprobado en la pasada de cierre:

1. **Null:** `feasible`/`orientation_valid` usan comparación `is True`/`is False`/`None`; no `bool(null)`.
2. **Contenedor:** `kpis_zhao` toma `problem.containers[0]` si `bin_lwh` es None; plan/publicado documentan `default_EURO_PALLET_MM` vs `caller_explicit`; bins no positivos/no finitos se rechazan.
3. **Orientación:** yaw 0/1 ≠ seis permutaciones; con `allow_rotation=False` se exige coincidencia exacta con el original.
4. **IDs:** desconocidos → `unknown_ids` + `identity_valid=false`; no se inventan originales.
5. **Comparación:** `protocols_homologated` / contrato / evidencia aportada **no** autorizan `comparison_valid`; el módulo no puede verificar secuencia/terminación/ICLR desde KPI → siempre `lado=no_compara`. Publicado sin plan + flags tampoco autoriza «supera».
6. **`packing_plan_actions`:** cuerpo idéntico a HEAD (SHA256 de la función sin cambio).
7. **Auditores `paper/tools`:** no modificados; pruebas independientes OK.

`feasible` representa **solo** validez geométrica AABB bajo `evaluator_contract` cuando `geometry_valid is True`. Fuera: estabilidad, peso, fragilidad, homologación Zhao/ICLR.
