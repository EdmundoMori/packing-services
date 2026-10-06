# Claims ↔ evidence (BED-BPP-RL)

## R01–R02A (resumen)

Diseño, entorno sintético e integridad portable: ver revisiones R01/R02/R02A.

## R03-preparación

| Afirmación | Evidencia | Estado |
|------------|-----------|--------|
| Contraste de identidades y orientaciones sin `orientation_ok` prefijado | `artifact_contrast.py` | Pass |
| Prefijo de secuencia / rechazo de swaps y extras | adversarial tests | Pass |
| Correspondencia transición↔placement (ítem, pos, dims) | contrast + tests | Pass |
| Reward por paso = V_nominal/V_bin; suma = U_geom | contrast | Pass |
| Cierre vs unpacked tipificado | contrast | Pass |
| Snapshot insuficiente → no auditoría completa | test | Pass |
| Propiedad sin datos → `no_comprobada` (no aceptación) | `missing_allow_rotation` test | Pass |
| Preflight real diseñado, no ejecutado | `preflight_real_protocol.json` | Diseño |
| Static-only valida protocolo/selección sin packing | `run_preflight_real.py --static-only` | Pass |
| Presupuestos propuestos con fundamento histórico orientativo | protocolo `budgets_proposed_before_execution` | Documentado |

### No afirmado

- Preflight real ejecutado; corpus industrial; entrenamiento RL
- Cola de tiempos desde 4 pedidos; tamaño definitivo de corpus
- Estabilidad física; independencia absoluta de la muestra
