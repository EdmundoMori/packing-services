# Claims ↔ evidence (BED-BPP-RL)

## Ejes del estudio (explícitos)

1. **BED-BPP** — dominio de pedidos/targets industriales.
2. **Aprendizaje por refuerzo** — interfaz de interacción y, más adelante,
   demostración PPO mínima en CPU con experiencias **nuevas** y separación
   train/evaluación.

El preflight con políticas fijas/aleatorias es **validación operativa previa**,
no el resultado final del artículo. No sustituye la demostración RL. No se abre
entrenamiento hasta ejecutar y revisar el preflight real publicado.

## R01–R02A (resumen)

Diseño, entorno sintético e integridad portable: revisiones R01/R02/R02A.

## R03-preparación

| Afirmación | Evidencia | Estado |
|------------|-----------|--------|
| Contraste de artefactos offline | `artifact_contrast.py` + tests | Pass |
| Preflight real diseñado; static-only sin packing | protocolo + `run_preflight_real.py --static-only` | Pass |
| Recurso apto en diseño para PPO CPU posterior | contrato env + corpus + loader agente | Diseño (no ejecutado) |

### Verificado (no es rendimiento RL)

Corrección contractual sintética; contraste de artifacts; diseño de preflight.

### No afirmado / pendiente

- Preflight real ejecutado
- Corpus industrial de aprendizaje
- Demostración PPO (no exportador, no heurísticas como sustituto)
- Aprendizaje eficaz, superioridad, novedad demostrada, aceptación editorial
