# Documentación del subproyecto

La fuente de verdad es [`../README.md`](../README.md): pipeline `01`–`03`, corrección metodológica, cifras del run de septiembre 2026 y el plan de RL (PPO).

Esta carpeta solo guarda la **pista de evaluación de producto**. No reentrena.

---

## Pistas

| Pista | Pregunta | Dónde | Estado |
|-------|----------|--------|--------|
| Entrenamiento | ¿Cómo se obtiene y exporta la política? | notebooks `01`–`03` | Ejecutado (maestro informativo) |
| Compuerta | ¿El maestro RH supera al heurístico en val? | notebook `04` | Ejecutado: decisión PPO |
| RL | Fine-tuning PPO del MLP p=1,s=1 | notebook `05` | Denso+scale ejecutado; sin promoción. No repetir el mismo PPO |
| Evaluación | ¿Sirve sobre pedidos reales no vistos? | abajo | Fases 0–1 medidas; notebook `10` pendiente |

Los documentos `fase1.md`–`fase5.md` del pipeline viejo (maestro tautológico) se eliminaron.

---

## Evaluación de producto

Holdout: `00100001`, `00100002`, `00100003`, `00100004`, `00100408`. Nunca train ni tune.

| Documento | Qué midió | Estado |
|-----------|-----------|--------|
| [`eval_fase0_holdout.md`](eval_fase0_holdout.md) | Offline vs online en los 5 pedidos | Terminado (checkpoints **anteriores** a la corrección del maestro) |
| [`eval_fase1_multipallet.md`](eval_fase1_multipallet.md) | Dos contenedores; los EP parten la carga | Terminado (mismo ciclo; el defecto de scoring sigue vigente) |
| [`eval_pasoA_consolidacion.md`](eval_pasoA_consolidacion.md) | Diseño del notebook `10` (first-fit) | Pendiente de ejecución |

Las cifras de holdout **actuales** (MLP vs heurístico, empate) están en el README del subproyecto, sección 5. Las de eval_fase0/fase1 se conservan como historial del primer ciclo.

### Hallazgos que siguen valiendo

1. `volume_utilization` no discrimina cuando el pedido cabe en un pallet.
2. Con dos contenedores, los motores por puntos extremos abren el segundo pallet por contacto con el suelo vacío.

### Qué sigue (evaluación vs modelado)

- **Notebook `10`:** disciplina de consolidación, sin reentrenar. Independiente del PPO.
- **PPO:** fine-tuning del `mlp_v1_p1s1.pt` sobre un contenedor. Detalle en el README, sección 7. No es el paso C histórico “RL si B falla”.

---

## Registro

`artifacts/registry.json` y `artifacts/runs/<flujo>/v<N>/` (`report.json` + `manifest.json`). Una versión sellada no se reescribe.

```python
from registry import registry_table, latest_run, load_sealed_report

registry_table()
latest_run("eval_fase1_multipallet")
```
