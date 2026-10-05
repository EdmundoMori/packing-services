# learning_objectives

Etiquetas train/development verificadas (re-verificación posterior). Entrenamiento emparejado preparado. Sin episodios ni test.

## Cobertura verificada

| Split | pedidos | estados | filas aprendizaje |
| --- | ---: | ---: | ---: |
| train | 48 | 192 | 743 |
| development | 24 | 96 | 372 |
| test | 0 | 0 | 0 |

Alternativas totales: 1115. Preflight reutilizado: 16 (una vez).

## Cierre intento 03

- Exit original del proceso: **1** (conservado)
- Summary: `completed`
- Re-verificación: `forensics/label_verification_closure.json` (verificador `manifest_keyed_v2`)

## Entrenamiento

- CLI: [`tools/run_learning_train.py`](tools/run_learning_train.py)
- 3 brazos × semillas 11/23/37; 40 épocas; presupuesto 1800 s
- Revisión: [`reviews/19_label_closure_and_training.md`](reviews/19_label_closure_and_training.md)
