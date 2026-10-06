# Claims ↔ evidence (BED-BPP-RL)

## R01 (diseño)

| Afirmación | Evidencia |
|------------|-----------|
| Recurso definible reutilizando el repo | `reuse_matrix.md`, `reviews/R01_scope_and_reuse.md` |

## R02 (implementación sintética)

| Afirmación | Evidencia | Estado |
|------------|-----------|--------|
| Interfaz `reset`/`step`/`close` | `tools/environment.py` | Pass (R02) |
| 36 features documentadas | `tools/observation_spec.py` | Pass |
| Truncación / terminación contractual | pruebas R02 | Pass |
| Motor post-C04 | `engine_check` | Pass |

## R02A (integridad)

| Afirmación | Evidencia | Estado |
|------------|-----------|--------|
| Validación estructural común (writer/loader/verifier) | `episode_validation.py` | Pass |
| Rechazo de conteos/IDs/índices/cierres contradictorios | `test_r02a_integrity` | Pass |
| Rechazo de propuestas ausentes/incompatibles | idem | Pass |
| Distinción estructural vs auditoría completa | `resource_verifier` niveles | Pass |
| Sin artifacts → `auditoria_no_realizada` (no completa) | `verify_complete_from_artifacts` | Pass |
| Manifiesto relativo + size + SHA256 | `CorpusStore` | Pass |
| Detección de modificación posterior | `test_detect_post_confirmation_modification` | Pass |
| Carga tras mover el directorio del corpus | `test_load_corpus_after_directory_move` | Pass |
| Single-writer + lock; sin pérdida silenciosa concurrente | `corpus_writer` docstring + lock | Documentado |
| Truncación sin acciones conserva obs/máscara abiertas | `truncate_budget` + test | Pass |
| Callback de política sin auditoría | `policy_public_view` + test | Pass |
| Tipos estrictos action/budget | environment + tests | Pass |
| Verificación geométrica/retorno desde archivos sin env | `verify_published_episode` | Pass |
| `physical_stability_verified=null` | verifier | Pass |

### No afirmado

- Corpus industrial, entrenamiento RL, off-policy por importancia
- Durabilidad absoluta ante caída de host
- Suficiencia Markov / novedad / superioridad
