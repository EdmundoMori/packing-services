# R02A — Cierre de integridad del entorno y del corpus

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `9b3318231f613a737c61a6ca31bb25888c09fd92`
**Rama:** `research/paper-online-packing`
**Decisión:** `integridad_del_recurso_verificada_para_disenar_preflight_real`

Sin pedidos reales, entrenamiento, corpus industrial ni preflight real.

## Objetivo

Dar un significado preciso a “verificado”: validación estructural común,
auditoría geométrica/volumen solo con artefactos suficientes, manifiesto
portable comprobable tras traslado, y separación política/auditoría.

## Cambios principales

| Pieza | Rol |
|-------|-----|
| `tools/episode_validation.py` | Validación común (writer/loader/verifier) |
| `tools/corpus_writer.py` (`CorpusStore`) | Manifiesto relativo + size + SHA256; lock single-writer |
| `tools/corpus_loader.py` | Rechaza tamper, rutas fuera, tmp |
| `tools/resource_verifier.py` | Niveles: structural / geometry / volume / complete |
| `tools/episode_export.py` | Política solo con vista pública; artifacts persistidos |
| `tools/environment.py` | `truncate_budget` conserva bootstrap; tipos estrictos |

## Garantías comprobadas

- Episodio inconsistente rechazado (conteos, IDs, índices, cierres, propuestas).
- Truncación: máscara siguiente utilizable; terminación: máscara siguiente vacía.
- Verificación completa desde archivos sin env vivo (si hay `artifacts`).
- Sin `artifacts` suficientes → `auditoria_no_realizada` (no se finge completa).
- Manifiesto portable; modificación posterior detectada por SHA256/tamaño.
- Escritura: un escritor con `.writer.lock`; `fsync` + `replace` atómico.
  No se promete durabilidad absoluta si el host cae entre episodio y manifiesto
  (el huérfano no cuenta como confirmado).

## Pruebas

```text
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py \
  paper/studies/bed_bpp_rl/tools/test_r02a_integrity.py -v
# 29 passed
```

## Límites

Sintético únicamente; AABB ≠ estabilidad física; sin RL ni corpus BED-BPP real.

## Siguiente paso (no ejecutado)

Diseñar preflight real medido.

## Decisión

`integridad_del_recurso_verificada_para_disenar_preflight_real`
