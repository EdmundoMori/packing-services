# Decisiones de diseño del experimento (sin congelar)

Estado: revisable. No autoriza campaña. No selecciona IDs nuevos.

## 1. Pérdidas

Signo común: **mayor score = mejor candidata**. Reducción entre estados: media aritmética con peso uno por estado (`mean_state_loss`). Encoder: 17 entradas, sin cambio.

### 1.1 Clasificación (existente)

- Objetivo: masa uniforme sobre argmax de `Q_hat` con tolerancia `1e-9`.
- Pérdida: entropía cruzada natural con `softmax(logits)`.
- Empates de máximo: masa repartida. Si todas empatan, objetivo uniforme en S.
- Pares: no aplica.
- Constantes pendientes de protocolo: ninguna propia; lr/épocas abiertos.

Código: `tools/losses.py` `classification_loss`.

### 1.2 Preferencias (existente)

- Pares: todos los `i<j` en S.
- No empatados (`|ΔQ|>1e-9`): softplus del margen orientado al mayor `Q_hat`; peso `|ΔQ|` renormalizado a suma 1 en el estado.
- Empatados: media de `(logit_i-logit_j)^2` × `TIE_COEFFICIENT=1.0`.
- Si todas empatan: solo el término de empates.
- No es la pairwise-difference de Mandi.

Código: `preference_loss`.

### 1.3 Diferencias de retorno (adaptación de Mandi)

Referencia verificada: Mandi et al., ICML 2022, PMLR 162:14935–14947, Section 4.3 “Regress on Pairwise Difference”, Equation (13). El PDF oficial se descargó; el folio tipográfico exacto de la Eq. (13) dentro de ese rango no se recuperó por extracción automática de texto, pero la ecuación y la sección se verificaron en el PDF/HTML.

Forma adaptada sobre candidatas de S:

\[
L_{\mathrm{rd}}(s)=\frac{1}{|\mathrm{OP}|}\sum_{(p,q)\in\mathrm{OP}}
\bigl((s_p-s_q)-(Q_p-Q_q)\bigr)^2
\]

donde `OP` son pares con `Q_p > Q_q + 1e-9`, y `s` son scores del modelo. Si `OP` vacío, pérdida 0.

No es reproducción exacta: Mandi puntúa soluciones de un CO vía costes predichos; aquí se puntúan candidatas locales con `Q_hat` de continuación Greedy.

Código: `return_difference_loss`. Hiperparámetros de optimización: pendientes.

## 2. Contrastes

- **Principal:** media por pedido, tras promediar semillas emparejadas, de
  `U_geom(preferencias) − U_geom(clasificación)`.
- **Secundario de aprendizaje:** el brazo de diferencias de retorno frente a cada uno de los anteriores, sin promoverlo a primario a posteriori.
- **Referencia práctica obligatoria:** GreedyBestFit (política A), visible aunque el contraste principal sea entre objetivos.
- `R_S` es diagnóstico de ranking en S, no el contraste primario de episodio.

No se eligen hiperparámetros ni tamaños a partir del piloto exploratorio como si fuera confirmatorio.

## 3. Datos utilizables (sin emitir IDs)

Fuentes estructuradas inspeccionadas:

- Pool de selección counterfactual: `sample_manifest.json` sobre `val_order_ids_full.json` (n=1500), con exclusiones de splits train/test históricos, holdouts y firmas de clones.
- Pedidos ya usados en counterfactual train/development (36) y en rl_rule_selection train/development.
- Evaluación independiente histórica: protocolo 07 / 200 pedidos (`paper/reviews/08_independent_evaluation_run.md`).

Exclusiones: IDs de splits previos, exclusiones positivas documentadas, clones por firma de snapshot cuando el protocolo lo declare.
Límite: la ausencia de un ID en los registros de exposición **no** demuestra independencia absoluta frente a toda fuga posible.

Desarrollo del piloto counterfactual no puede reutilizarse como train de un estudio nuevo sin declararlo y excluirlo de evaluaciones posteriores. Las etiquetas antiguas no se reutilizan bajo el contrato único (véase review 04).

## 4. Presupuesto preliminar (tiempos ya medidos)

| Fase | Evidencia medida | Lectura preliminar |
| --- | --- | --- |
| Etiquetas | 1378.87 s para 36 pedidos / 553 continuaciones | ~38 s/pedido de pared en aquella campaña; no prueba un tamaño futuro |
| Entrenamiento | 12.08 s para seis ajustes (2 brazos × 3 semillas, 40 épocas) | Barato frente al packing; un tercer brazo escala ~lineal en brazos |
| Desarrollo | 244.25 s para 84 episodios (12 pedidos × 7 políticas) | ~2.9 s/episodio de pared de campaña con 4 workers |
| Evaluación independiente | Protocolo 07: 400 episodios completos en el actor histórico | Coste de packing domina; no se fija aún el n |
| Auditoría | Incluida en etiquetas (~439 s) y en medias de packing (~3.07 s/caso) | Debe reservarse aparte en cualquier reloj futuro |

Las extrapolaciones **no demuestran** que una campaña quepa en ocho horas. Cualquier estimación de precisión inspirada en el piloto declara que procede de **doce pedidos exploratorios** y puede ser inestable; no se usa para fijar un test que “salga bien”.

## 5. Decisiones pendientes y opción mínima recomendada

| Decisión | Opción mínima recomendada | Justificación |
| --- | --- | --- |
| Cardinalidad de S | 4 (ya implementada) | Alineada al presupuesto de etiquetado previo y al contrato codificado |
| Regla de S | `greedy_plus_orientation_position_diversity_v1` | Una sola fuente; corrige deduplicación |
| Contraste primario | preferencias − clasificación | Ya motivado por el piloto; no se cambia post hoc |
| Brazo return-difference | Secundario | Adaptación nueva; no desplaza el primario |
| Semillas | 11, 23, 37 | Emparejamiento ya usado; evita rediseñar sin ganancia clara |
| Checkpoint | Última época, sin selección | Evita filtrado por desarrollo |
| Train/dev tamaños | Posponer freeze; borrador 24/12 por target-balance como en el piloto | Continuidad operativa, no confirmación |
| Test | No seleccionar IDs ahora | Evita contaminación |
| Puerta | Posponer umbrales numéricos | Requiere protocolo formal |
| Etiquetas | Regenerar bajo contrato único | Reutilización no comprobada |
| Presupuesto reloj | Medir viabilidad tras fijar n; no adoptar 8 h como demostrado | Extrapolaciones inciertas |

## 6. Decisión de este paso

**listo_para_revisar_congelacion**: el desajuste de soporte está resuelto en código y pruebas sintéticas, con contrastes y pérdidas especificados. Esto **no autoriza** etiquetar, entrenar ni empaquetar.
