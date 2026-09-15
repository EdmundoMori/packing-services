# Qué se descartó y qué se replica ahora

## Ya falló (no repetir)

| Run | Idea | Resultado |
|-----|------|-----------|
| PPO v1 p=1 s=1 | Reward = solo volumen (GOPT/Zhao) | `policy_loss≈0`, 14 empates con BC |
| PPO v2 p=1 s=1 | Volumen + soporte − altura + critic 5-D + KL | `value_loss` sano, actor igual: val 0.6755, IC cruza 0 |

En p=1 s=1 la acción es la **pose** de un solo ítem. El volumen no cambia entre acciones.

## Receta actual: STEP

Repo: https://github.com/nikitasarawgi/step-bpp (ICRA 2026, sobre GOPT).

Ellos superan el techo de “solo colocar” en **dos etapas**:

1. Módulo de colocación congelado (dónde va un ítem dado).
2. Módulo de selección entrenado con RL (qué ítem del buffer).

Aquí: colocación = `mlp_v1_p3s2.pt`; PPO escribe `mlp_v1_p3s2_step.pt`.
Datos = `data/scale/` 80/20. Informe = `artifacts/reports/05_step.json`.
La API sigue en el PPO p=1 s=1 hasta que haya IC.
