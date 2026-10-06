# BED-BPP-RL

**Estado R02A:** integridad del entorno y corpus verificada (solo sintético).
Decisión: `integridad_del_recurso_verificada_para_disenar_preflight_real`.

## Artefactos

| Documento | Rol |
|-----------|-----|
| [`tools/`](tools/) | Env, validación, corpus portable, verifier, pruebas R02/R02A |
| [`claims_evidence.md`](claims_evidence.md) | Afirmaciones ↔ evidencia |
| [`environment_contract_draft.json`](environment_contract_draft.json) | Contrato (frozen R02A) |
| [`corpus_schema_v1.json`](corpus_schema_v1.json) | Esquema + manifiesto portable |
| [`../../reviews/R02_synthetic_env_and_corpus.md`](../../reviews/R02_synthetic_env_and_corpus.md) | R02 |
| [`../../reviews/R02A_resource_integrity.md`](../../reviews/R02A_resource_integrity.md) | R02A |
| [`../../manuscript/bed_bpp_rl/`](../../manuscript/bed_bpp_rl/) | LaTeX |

## Pruebas

```bash
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py \
  paper/studies/bed_bpp_rl/tools/test_r02a_integrity.py -v
```

## No autorizado

Pedidos reales, entrenamiento, corpus industrial, preflight real.
