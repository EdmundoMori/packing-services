# learning_objectives

Etiquetas verificadas (re-verificación posterior). Entrenamiento emparejado de 9 modelos completado. Sin episodios ni test.

## Cobertura

| Split | pedidos | estados | filas |
| --- | ---: | ---: | ---: |
| train | 48 | 192 | 743 |
| development | 24 | 96 | 372 |
| test | 0 | — | — |

## Intento 03

- Exit proceso original: **1** (conservado)
- Re-verificación: `forensics/label_verification_closure.json`

## Entrenamiento

- HEAD: `468ff517bbc1cfae2831abbfbb454cc82af1cf41`
- Salida: [`learning_models/`](learning_models/) — 9 × `checkpoint_epoch_40.pt`
- Pared ≈ 38.3 s / presupuesto 1800 s
- Decisión operativa: `entrenamiento_integro_para_revision_de_desarrollo`

## Modelos y evaluación development

- Modelos: [`learning_models/`](learning_models/)
- Evaluador: [`tools/run_development_eval.py`](tools/run_development_eval.py)
- Procedencia aborto: [`forensics/training_abort_provenance.json`](forensics/training_abort_provenance.json)
