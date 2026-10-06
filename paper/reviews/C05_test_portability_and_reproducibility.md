# C05 — Portabilidad y reproducibilidad de pruebas

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `a5fb46879c7bfbe16400eec2ab985dd23bf30385`
**Rama:** `research/paper-online-packing`
**Alcance:** rutas ejecutables en pruebas activas; skips de verificación; documentación de entornos.
**No altera:** protocolos congelados ni sus hashes, resultados/capturas de campañas, código hasheado en protocolos; no entrena, no infiere, no packea pedidos reales.

**Decisión:** `correccion_reproducibilidad_lista_para_revision`

## Clasificación del inventario

### Defecto de portabilidad corregible

| Ubicación | Problema | Corrección |
|-----------|----------|------------|
| `paper/tests/test_ablation_runner.py` | rutas `/home/edmundo/packing-services/...` | `paper/` vía `Path(__file__).resolve().parents[1]` |
| `paper/tests/test_ablation_packing_contract.py` | idem | idem |
| `paper/tests/test_teacher_probe.py` | protocolo 14 absoluto | `_PAPER / "protocols" / "14_teacher_probe.json"` |

Aserciones de integridad sobre `paper/results/11_normalization_ablation/` **conservadas**; si falta el artefacto → `FileNotFoundError` claro (obligatorio, no skip). Salidas de prueba siguen en `tempfile` / `tmp_path`.

### Skips revisados en `tests/`

| Archivo | Prueba | Finalidad | Tratamiento C05 |
|---------|--------|-----------|-----------------|
| `tests/test_ppo_policy.py` | `test_rl_preset_without_checkpoint_explains_notebook_05` | Unitaria: error de `apply_policy_preset` si no hay checkpoint | Antes saltaba si existía el PPO de producción. Ahora usa `tmp_path` + `model_path` inexistente. Sin entrenamiento. |
| `tests/test_ppo_policy.py` | `test_rl_execute_without_checkpoint_is_400` | Integración HTTP del mismo error | Idem (`model_path` bajo `tmp_path`). |
| `tests/test_teacher_leakage.py` | (antes) `test_legacy_volume_teacher_dump_is_tautological_if_present` | Comprobar tautología del dump `transitions_p1s1_volume.pkl` | Renombrada a `test_legacy_volume_teacher_dump_shape_is_tautological`: fixture pickle sintético en `tmp_path`. El `.pkl` histórico **no** es requisito de la suite. |

No son scripts de experimentación: son pruebas de contrato de API / detector de tautología. No se borraron aserciones; no se ejecutó entrenamiento para cerrarlas.

### Dependencia opcional vs obligatoria

| Suite / prueba | Dependencia | Criterio |
|----------------|-------------|----------|
| `tests/test_viz_3d.py` | `plotly`, `numpy` | Opcional **de esa suite** (`importorskip`); el resto de `tests/` no la necesita |
| `tests/test_drl_policy_online.py`, holdout | `torch` | Obligatoria **para esas pruebas**; `importorskip` solo si se ejecuta el archivo sin torch instalado — no oculta fallos del motor base |
| Integridad ablación 11 | árbol `paper/results/11_...` | Obligatoria para esas pruebas → error, no skip |

### Integración / histórico intacto

- Dataset BED-BPP externo y comandos en protocolos congelados: **sin modificar** (hashes / evidencia).
- Registros con paths de máquina (`state.json` `repo_root`, manifests, `invoked_python`): procedencia histórica, no rutas ejecutables de tests.

## Separación: reproducción histórica vs verificación actual

| | Histórica | C05 (código actual) |
|--|-----------|---------------------|
| Qué | commit + entorno + datos + protocolos de la campaña | suites sintéticas / integridad de artefactos ya en el tree |
| Dataset externo | path del protocolo de esa corrida | no se abre |
| Conclusión científica | no se reabre | no se deriva |

C05 **no** declara reproducibilidad completa del repositorio: falta el dataset externo, entornos históricos distintos y posibles artefactos no versionados.

## Entornos

Archivo: [`C05_current_verification_environment.json`](C05_current_verification_environment.json)

- **Versiones observadas:** plataforma, Python, `pip freeze` seleccionado del `.venv` en el momento C05.
- **Dependencias requeridas (mínimas por suite):** ver JSON (`required_by_suite`) y tabla abajo.
- **Entorno histórico:** no reconstruido; ver protocolos/resultados de cada campaña.

| Suite | Requerido |
|-------|-----------|
| `tests/` motor/API | proyecto editable + `pytest` (+ `httpx`) |
| `online_policy_ml/tests/` | `src` + `src_ml` (vía `__file__`) |
| `paper/tests/` afectados | + `paper/tools`; artefactos 10/11/14 si la prueba los exige |

## Comandos y conteos (cierre)

```bash
REPO=/ruta/al/packing-services
PY=$REPO/.venv/bin/python

# Suites afectadas C05 (+ proyección / skips corregidos), desde /tmp
cd /tmp
$PY -m pytest \
  $REPO/tests/test_extreme_point_projection.py \
  $REPO/tests/test_ppo_policy.py \
  $REPO/tests/test_teacher_leakage.py \
  $REPO/online_policy_ml/tests \
  $REPO/paper/tests/test_ablation_runner.py \
  $REPO/paper/tests/test_ablation_packing_contract.py \
  $REPO/paper/tests/test_teacher_probe.py -q

# Suite tests/ completa
$PY -m pytest $REPO/tests -q --tb=no -ra
```

Resultados de cierre (esta máquina):

| Conjunto | passed | failed | skipped | no ejecutado |
|----------|--------|--------|---------|--------------|
| Suites afectadas desde `/tmp` | **109** | **0** | **0** | — |
| Suites afectadas desde el repo | **109** | **0** | **0** | — |
| `tests/` completa | **412** | **0** | **0** | 0 |

Suites afectadas = proyección C04 + `test_ppo_policy` + `test_teacher_leakage` + `online_policy_ml/tests` + tres `paper/tests` de ablación/teacher.

**No ejecutado:** campañas, entrenamiento, notebooks, inferencia, packing de pedidos reales, suite completa `paper/studies/*/tests/`.

## Límites

1. Dataset BED-BPP externo y tools/protocolos hasheados no se «portabilizan» aquí.
2. Integridad de `11_normalization_ablation` exige ese árbol en el clone.
3. No hay lock histórico fabricado; las versiones del JSON C05 son solo observación actual.
4. Ningún defecto algorítmico nuevo en esta revisión.

## Archivos de C05

- `paper/tests/test_ablation_runner.py`
- `paper/tests/test_ablation_packing_contract.py`
- `paper/tests/test_teacher_probe.py`
- `tests/test_ppo_policy.py`
- `tests/test_teacher_leakage.py`
- `paper/reviews/C05_test_portability_and_reproducibility.md`
- `paper/reviews/C05_current_verification_environment.json`
- `paper/README.md`, `paper/state.json`
