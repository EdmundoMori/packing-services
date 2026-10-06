# Plan de validación (R02 + R02A)

## R02 — contractual (pass)

V1–V6, motor post-C04, loader agente: `test_r02_synthetic.py`.

## R02A — integridad (pass)

| ID | Comprobación | Estado |
|----|--------------|--------|
| I1 | Conteos/IDs/índices/cierres contradictorios | Pass |
| I2 | Propuestas ausentes/incompatibles | Pass |
| I3 | Estructural ≠ auditoría completa | Pass |
| I4 | Tamper post-confirmación (SHA256) | Pass |
| I5 | Carga tras mover corpus | Pass |
| I6 | Truncación 0 acciones + máscara bootstrap | Pass |
| I7 | Callback sin auditoría | Pass |
| I8 | Tipos estrictos action/budget | Pass |
| I9 | Geometría/retorno desde archivos | Pass |

V8 (update PPO) y corpus real: no en R02A.
