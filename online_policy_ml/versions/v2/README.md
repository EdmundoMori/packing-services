# PPO — tanda v2 (archivo)

El fine-tuning PPO sobre el encoder v1 está **cerrado**. Este directorio guarda las
salidas de las recetas 3 (shaping) y 4 (STEP). No se relanza `05` para buscar un
ganador. No se copia nada de aquí al path de la API.

Informe canónico: [`docs/informe_experimentos_ppo.md`](docs/informe_experimentos_ppo.md).

| Destino | Quién escribió | Qué hay |
|---------|----------------|---------|
| `artifacts/models/` | notebook `05` | `mlp_v1_p3s2_step.pt` (no promocionado) |
| `artifacts/reports/` | notebook `05` | `05_ppo.json` (shaping), `05_step.json` |
| `data/` | vacío a propósito | el PPO reusó `online_policy_ml/data/scale/` |
| `notebooks/` | copia de arranque | **no ejecutar** desde aquí (`paths.py` resolvería mal `ML_ROOT`) |
| `docs/` | notas de la tanda | informe + este README |

## Qué no se toca

| Ruta viva | Motivo |
|-----------|--------|
| `artifacts/models/mlp_v1_p1s1_ppo.pt` | PPO de producción (API). Receta 2; empate con el heurístico |
| `artifacts/models/mlp_v1_p1s1.pt` | warm-start BC; archivo |
| `data/scale/` | mismos 80/20 del corte v1 |
| `versions/v1/` | archivo congelado |
