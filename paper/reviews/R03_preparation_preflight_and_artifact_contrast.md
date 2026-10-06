# R03-preparación — Contraste de artefactos y diseño del preflight real

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `dea829836ec2cf30af2d4f09a96e98ec3fdca5dd`
**Rama:** `research/paper-online-packing`
**Decisión:** `preflight_real_disenado_y_contraste_de_artefactos_verificado`

Sin pedidos reales, sin corpus industrial, sin entrenamiento.

## Contraste de artefactos (implementado)

Módulo `tools/artifact_contrast.py`, integrado en `resource_verifier.py`.

Propiedades **comprobadas** cuando el snapshot es suficiente:
- IDs únicos y dims originales finitas/positivas
- placements = prefijo ordenado de la secuencia
- orientación permitida (sin `orientation_ok=True` prefijado)
- 1:1 transición↔placement (posición + dims orientadas)
- reward individual = V_item/V_bin; volumen acumulado = U_geom
- cierre tipificado vs `unpacked`
- contención AABB y no solape
- `physical_stability_verified=null` (AABB ≠ estabilidad)

Si falta un dato (p. ej. `allow_rotation`), la propiedad se marca
`no_comprobada`; no se acepta por omisión.

Pruebas adversariales: `tools/test_r03_artifact_contrast.py`.

## Preflight real (diseñado, no ejecutado)

- Protocolo: `preflight_real_protocol.json`
- Ejecutor: `tools/run_preflight_real.py`
- Static-only (sí ejecutado en R03-prep):

```bash
python3 paper/studies/bed_bpp_rl/tools/run_preflight_real.py --static-only \
  --protocol paper/studies/bed_bpp_rl/preflight_real_protocol.json
```

- Comando futuro (no autorizado aquí):

```bash
python3 paper/studies/bed_bpp_rl/tools/run_preflight_real.py \
  --protocol paper/studies/bed_bpp_rl/preflight_real_protocol.json \
  --orders <BED_BPP_JSON> --out <CORPUS_DIR>
```

Muestra: 4 pedidos (2/target), cuantiles de `n_items` q25/q75, exclusión de
tests reservados, 3 políticas fijas + uniforme (semilla 20261006), ≤16 episodios.

Presupuestos propuestos: timeout 60 s/episodio; pared global 600 s; RSS soft 4 GiB;
concurrencia 1; un intento/clave; parada si falla el contraste. Fundamento:
orientación histórica ~2–8 s/caso en rl_rule_selection; 16×8≈128 s → techo ~5×;
**no** garantiza cola ni fija tamaño de corpus/entrenamiento.

## Pruebas

```text
pytest …/test_r02_*.py …/test_r02a_*.py …/test_r03_*.py
# 40 passed
```

El preflight es **validación operativa** (coste/export/reload), no el resultado
final del artículo ni una demostración RL. Tras ejecutarlo y revisarlo, el
recurso debe permitir una PPO mínima en CPU con experiencias nuevas y
separación train/evaluación; eso **no** se abre en R03-prep y **no** se
sustituye por tests del exportador ni por heurísticas.

## Decisión

`preflight_real_disenado_y_contraste_de_artefactos_verificado`
