# Ordenación por consecuencias de acciones alternativas

Estudio nuevo, separado de la campaña corta ya cerrada. La configuración compacta `a=1, b=0.5, c=0` sigue abandonada. Este directorio no afirma mejora, novedad suficiente ni publicabilidad.

## Problema

La pregunta es si hay margen para aprender a ordenar candidatas legales a partir de las consecuencias de acciones alternativas, en vez de copiar la elección de un teacher. Es una hipótesis propia. No se presenta como reproducción de LOLS, AggreVaTe, PCT, GOPT u OPAL.

## Alcance

El contrato geométrico es el del paso 16. El diagnóstico puede usar el sufijo real: es privilegiado de desarrollo, no un baseline online. `Q_hat` es una continuación Greedy concreta. `physical_stability_verified` permanece `null`.

El preflight de rendimiento se ejecutó una vez sobre `00109938` y `00105640`. El diagnóstico completo se ejecutó una vez sobre los 20 pedidos de la muestra. La clasificación es margen suficiente para diseñar el experimento de aprendizaje. Esa clase no autoriza entrenamiento automático y no demuestra mejora de una política online.

## Etapas

1. Borrador y muestra. El plan de análisis queda escrito.
2. Preflight de rendimiento, ejecutado una vez. Revisión: [`preflight_review.md`](preflight_review.md). Evidencia: [`preflight_results/`](preflight_results/).
3. Protocolo congelado y diagnóstico único. Revisión de la congelación: [`freeze_review.md`](freeze_review.md). Resultado: [`diagnostic_review.md`](diagnostic_review.md). Evidencia: [`diagnostic_results/`](diagnostic_results/).
4. Diseño del experimento de aprendizaje, sin ejecución. Revisión: [`learning_design.md`](learning_design.md). Borrador: [`learning_protocol_draft.json`](learning_protocol_draft.json). No está congelado, no genera etiquetas y no entrena.

## Archivos

- `protocol_draft.md` y `protocol_draft.json`: borrador conservado.
- `protocol_frozen.md` y `protocol_frozen.json`: protocolo operativo de la corrida.
- `sample_manifest.json`: lista, orden, hashes y firmas. No contiene retornos observados.
- `design_review.md`: decisiones, límites e incertidumbres.
- `tools/`: selección, diagnóstico, preflight y campaña.
- `preflight_review.md` y `preflight_results/`: la corrida única de rendimiento.
- `diagnostic_review.md` y `diagnostic_results/`: la campaña única.
- `learning_design.md` y `learning_protocol_draft.json`: diseño del experimento controlado, todavía sin ejecutar.
- `tests/`: pedidos sintéticos.
