# Versiones del proceso PPO

| Versión | Estado | Carpeta |
|---------|--------|---------|
| v1 | Congelada. No se reescribe. | [`v1/`](v1/MANIFEST.md) |
| v2 | Sumidero del siguiente ciclo | [`v2/`](v2/README.md) |

Se **ejecuta** siempre desde el árbol vivo:

- código: `online_policy_ml/src_ml/`
- notebooks: `online_policy_ml/notebooks/`
- datos de entrenamiento (reutilizados): `online_policy_ml/data/`
- checkpoint que carga la API: `online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt`

`versions/` solo guarda **cortes** (v1) y **salidas nuevas** (v2). No se corre un notebook desde `versions/v2/notebooks/`.

Informe de las cuatro pruebas de PPO: [`v2/docs/informe_experimentos_ppo.md`](v2/docs/informe_experimentos_ppo.md). Cierre del subproyecto: [`../docs/informe_cierre_rl_online.md`](../docs/informe_cierre_rl_online.md).
