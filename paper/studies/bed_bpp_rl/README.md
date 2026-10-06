# BED-BPP-RL

**Título provisional:** BED-BPP-RL: A Reusable Environment and Experience Corpus for
Resource-Constrained Online Packing Research

**Pregunta:** ¿Cómo transformar pedidos industriales BED-BPP en un recurso
reproducible de interacción y experiencias para estudiar políticas de RL,
manteniendo explícitos la observabilidad, las acciones, los retornos y el
presupuesto computacional?

**Estado R02:** entorno + corpus export verificable con pruebas sintéticas.
Sin pedidos reales, sin entrenamiento, sin corpus industrial.

## Artefactos

| Documento | Rol |
|-----------|-----|
| [`tools/`](tools/) | `BedBppRlEnv`, corpus, verifier, pruebas sintéticas |
| [`claims_evidence.md`](claims_evidence.md) | Afirmaciones ↔ evidencia |
| [`reuse_matrix.md`](reuse_matrix.md) | Reutilizar / adaptar / excluir |
| [`environment_contract_draft.json`](environment_contract_draft.json) | Contrato del entorno (frozen R02) |
| [`corpus_schema_v1.json`](corpus_schema_v1.json) | Esquema versionado del corpus |
| [`validation_plan.md`](validation_plan.md) | Plan + estado de verificaciones |
| [`provenance_and_licensing.md`](provenance_and_licensing.md) | Procedencia y licencias |
| [`design_draft.md`](design_draft.md) | Diseño resumido |
| [`../../reviews/R01_scope_and_reuse.md`](../../reviews/R01_scope_and_reuse.md) | Revisión R01 |
| [`../../reviews/R02_synthetic_env_and_corpus.md`](../../reviews/R02_synthetic_env_and_corpus.md) | Revisión R02 |
| [`../../manuscript/bed_bpp_rl/`](../../manuscript/bed_bpp_rl/) | Borrador LaTeX |

## Pruebas sintéticas

```bash
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py -v
```

## No autorizado por R02

No ejecutar pedidos BED-BPP reales, no entrenar, no generar corpus industrial,
no abrir el test cerrado, no iniciar el preflight real todavía.
