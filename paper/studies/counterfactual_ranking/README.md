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
4. Diseño congelado y etiquetas generadas una vez. Protocolo: [`learning_protocol_frozen.md`](learning_protocol_frozen.md). Revisión: [`learning_labels_review.md`](learning_labels_review.md).
5. Ajuste único de los dos brazos, semillas 11, 23 y 37. Revisión: [`training_review.md`](training_review.md). Evidencia: [`learning_training/`](learning_training/).
6. Episodios completos de development y puerta congelada. Revisión: [`packing_review.md`](packing_review.md). Evidencia: [`learning_packing/`](learning_packing/). La clasificación es no avanzar con esta configuración.
7. Cierre. Síntesis: [`campaign_closure.md`](campaign_closure.md). Matriz: [`claims_evidence.md`](claims_evidence.md). El test final no se selecciona ni se ejecuta. No hay continuación automática.

## Archivos

- `protocol_draft.md` y `protocol_draft.json`: borrador conservado.
- `protocol_frozen.md` y `protocol_frozen.json`: protocolo operativo de la corrida.
- `sample_manifest.json`: lista, orden, hashes y firmas. No contiene retornos observados.
- `design_review.md`: decisiones, límites e incertidumbres.
- `tools/`: selección, diagnóstico, preflight y campaña.
- `preflight_review.md` y `preflight_results/`: la corrida única de rendimiento.
- `diagnostic_review.md` y `diagnostic_results/`: la campaña única.
- `learning_design.md` y `learning_protocol_draft.json`: diseño y borrador antecedente.
- `learning_protocol_frozen.md` y `learning_protocol_frozen.json`: protocolo de las etiquetas.
- `learning_labels/` , `learning_labels_verification.json` y `learning_labels_review.md`: la corrida única de etiquetas.
- `training_operational_annex.md`, `learning_training/`, `training_verification.json` y `training_review.md`: el ajuste único.
- `learning_packing/`, `packing_verification.json` y `packing_review.md`: los 84 episodios y la puerta. No elige semilla ni abre el test final.
- `campaign_closure.md` y `claims_evidence.md`: cierre de la campaña y matriz de afirmaciones.
- `tests/`: pedidos sintéticos.
