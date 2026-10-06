# C03 — Corrección del contrato de exportación yaw

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `c30e06fafd018c7fe898682de614b9452701fbaf`
**Rama:** `research/paper-online-packing`
**Alcance:** `packing_plan_actions` estricto; captura; pruebas; esta revisión.
**No altera:** JSON/planes 09/10, resultados 01A/01C/01E, auditores congelados, motor EP, checkpoints, cierres de campaña.

## Contrato interno `yaw_0_1_v1`

Respecto a los ejes **originales almacenados** `(L, W, H)`:

| Flag | Decode |
|------|--------|
| 0 | `(L, W, H)` |
| 1 | `(W, L, H)` (misma altura) |

- Sin canonicalización por lado mayor.
- Tolerancia `1e-6` mm; dims finitas y >0; IDs desconocidos → rechazo; rotación prohibida + flag≠0 → rechazo.
- Empate simétrico → flag **0**.
- Una incompatibilidad rechaza el **plan entero**; el error lista **todas** las incompatibilidades detectadas.
- El rechazo no muta la solución de entrada ni altera FLB/dims/ids.
- «No exportable a yaw» ≠ geometría interna inválida.

Decode alineado con `kpis_zhao_from_plan` / `decode_yaw01_oriented_lwh` / adaptador estricto del repo.

### Alcance externo no verificado

Este contrato es **interno** del evaluador packing-services. **No** se afirma compatibilidad verificada con el esquema publicado BED-BPP/Kagerer ni con PCT. Una coincidencia de forma 0/1 con herramientas del repo no homologa protocolos externos.

## Comportamiento anterior vs corregido

| Antes (pre-C03) | Ahora |
|-----------------|-------|
| `orientation=1` si L o W colocados ≠ originales; altura colocada se perdía | Solo exporta si oriented es exactamente (L,W,H) o (W,L,H) |
| Plan completo aunque hubiera giros de altura | `YawExportError`; no lista parcial ni vacía fingiendo éxito |
| Capture `--legacy-export` usaba ese aplastamiento | `--yaw-export` estricto; legacy **inseguro** solo con flag explícito |

## Consumidores y CLI

| Consumidor | Compatibilidad |
|------------|----------------|
| `packing_plan_actions` | Vigente estricto |
| `packing_plan_actions_legacy_unsafe_yaw` | Forense etiquetado; nunca fallback |
| `capture_internal_solution` | `--yaw-export`; `--legacy-unsafe-yaw-export`; `--legacy-export` = alias deprecado del unsafe |
| `09_homologar_pct.ipynb` | Si se reejecuta, fallará en no-yaw; JSON 09 no regenerado |
| Auditores `export_yaw_strict` / `audit_*` | Sin cambio de código |

Migración CLI: quien usaba `--legacy-export` para forense debe usar `--legacy-unsafe-yaw-export` (mismo comportamiento inseguro) o pasar a `--yaw-export` (estricto).

## Captura y rechazo

- La captura interna se construye y puede persistirse aunque falle el yaw.
- Rechazo yaw: no crea/trunca plan; no plan parcial; `wrote_plan=false`; comunica `incompatible`.
- Rutas `output` / `--yaw-export` / legacy que resuelven al mismo archivo → error **antes** de escribir; archivos existentes se conservan.
- Legacy no se activa automáticamente tras rechazo.

## Evidencia histórica preservada

Planes 09/10, capturas y reviews 01A/01C/01E intactos.

## Pruebas ejecutadas

- `test_yaw_export_contract` (C03)
- `test_bedbpp_eval_feasibility` (C02)
- `test_export_yaw_strict`, `test_audit_exported_plan`, `test_audit_internal_solution`

Sin inferencia ni packing real en el cierre.

## Limitaciones

- No exporta seis permutaciones bajo otro contrato.
- Interoperabilidad externa BED-BPP/Kagerer/PCT no verificada.
- No regenera artefactos históricos.
