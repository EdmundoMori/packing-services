# R02 — Entorno reutilizable y exportación verificable (sintético)

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `38bb9d5192b20844bd071e83debc9675c313a9ca`
**Rama:** `research/paper-online-packing`
**Decisión:** `implementacion_sintetica_verificada_para_disenar_preflight_real`

Sin pedidos reales, entrenamiento, generación de corpus industrial, apertura de
test ni pickle históricos.

## Objetivo R02

Convertir el diseño R01 en una interfaz de interacción y un formato de
experiencias cuya semántica pueda comprobar un usuario independiente, con
evidencia de **corrección contractual** sobre instancias sintéticas.

## Implementación

| Pieza | Ruta |
|-------|------|
| Entorno | `paper/studies/bed_bpp_rl/tools/environment.py` |
| Spec 36-D | `paper/studies/bed_bpp_rl/tools/observation_spec.py` |
| Contrato corpus | `paper/studies/bed_bpp_rl/tools/corpus_contract.py` |
| Writer atómico | `paper/studies/bed_bpp_rl/tools/corpus_writer.py` |
| Loader agente | `paper/studies/bed_bpp_rl/tools/corpus_loader.py` |
| Verificador | `paper/studies/bed_bpp_rl/tools/resource_verifier.py` |
| Export episodio | `paper/studies/bed_bpp_rl/tools/episode_export.py` |
| Motor post-C04 | `paper/studies/bed_bpp_rl/tools/engine_check.py` |
| Pruebas | `paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py` (18 pass) |

No se modificaron implementaciones históricas hasheadas de
`rl_rule_selection/tools/`.

## Contrato terminación / truncación

1. **terminated:** primer ítem imposible en reset (0 transiciones); siguiente
   ítem imposible tras placement (auto-stop); todas las cajas colocadas.
2. **truncated:** corte de presupuesto con episodio aún abierto; obs/máscara
   siguiente reales para bootstrap; retorno parcial observado (no bootstrap
   estimado como retorno).
3. Si el límite coincide con fin natural → **terminated** gana.
4. Sin acciones + corte → resumen sin transición fabricada.
5. `step` tras cierre → rechazo.
6. Flags de cierre se fijan al **close** del episodio antes del publish atómico;
   no se reescribe una transición ya publicada.

## Corpus

Campos agente: `observation`, `observation_next`, `action`, `action_mask`,
`action_mask_next`, `reward`, `terminated`, `truncated`.
Auditoría separada; loader de entrenamiento solo devuelve campos agente.
`off_policy_importance_supported=false`.

## Pruebas

```text
python3 -m pytest paper/studies/bed_bpp_rl/tools/test_r02_synthetic.py -v
# 18 passed
```

No interpretadas como medición de rendimiento en BED-BPP.

## Manuscrito

Actualizado `paper/manuscript/bed_bpp_rl/` (interfaz, observabilidad, cierres,
esquema, procedimiento sintético). Resultados de corpus real / RL /
caracterización computacional siguen pendientes.

## Límites

- Solo sintético; no autoriza experiencias reales ni entrenamiento.
- Observación no reclamada Markov-suficiente.
- Estabilidad física no verificada (`null`).

## Siguiente paso operativo (no ejecutado)

Diseñar preflight real medido (tamaños/presupuestos) **sin** generar todavía el
corpus industrial ni entrenar.

## Decisión

`implementacion_sintetica_verificada_para_disenar_preflight_real`
