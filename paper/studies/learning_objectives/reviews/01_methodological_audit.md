# Auditoría metodológica del piloto counterfactual

Referencias al código publicado bajo `paper/studies/counterfactual_ranking/`. No se modificó ese código. Las diferencias de ranking y de episodios no se interpretan aquí como causa demostrada.

## 1. Información del actor frente a información privilegiada

El actor recibe 17 columnas del contenedor, del estado ya colocado, del ítem actual y de la candidata puntuada (`tools/actor_features.py`, `FEATURE_NAMES` líneas 15–33; `encode_candidate` líneas 65–100). El docstring del módulo (líneas 1–7) y de `encode_candidate` (líneas 65–66) excluyen sufijo, pedido, retorno, acción Greedy y conteo restante.

En despliegue, `ActorPolicy.decide` (`tools/actor_policy.py`, líneas 33–58) descarta `preview`, `remaining_count`, `constraints` y `mask` (línea 43), puntúa todas las opciones legales y elige el mayor logit.

`Q_hat` se construye solo en etiquetado: se continúa desde un checkpoint con el sufijo real mediante `continue_from` y se puntúa la captura (`tools/diagnostic.py`, `score_solution` líneas 397–470; asignación `"q_hat": float(scored["effective_u_geom"])` en la línea 470). Ese sufijo se registra como `suffix_ids_not_an_actor_input` (`tools/label_campaign.py`, líneas 265–267).

## 2. Clasificación y máximos empatados

Objetivo: uniforme sobre las candidatas a como máximo `eps=1e-9` del máximo (`tools/objectives.py`, `classification_target`, líneas 15–25).

Pérdida: entropía cruzada natural entre ese objetivo y `softmax(logits)` (`classification_loss`, líneas 37–48). La versión Torch del entrenamiento replica la misma regla (`tools/train_loop.py`, `_classification_loss`, líneas 82–88).

No hay temperatura. `Q_hat` no se usa como probabilidad.

## 3. Preferencias, ponderación y empates

Para cada par no empatado se orienta del mayor `Q_hat` al menor; la pérdida del par es `softplus(-(logit_alto - logit_bajo))`; el peso es `|ΔQ|`, renormalizado para que los pesos del estado sumen 1 (`tools/objectives.py`, `preference_loss`, líneas 59–97; Torch en `train_loop.py` líneas 91–117).

Empates (`|ΔQ| ≤ 1e-9`): media de `(logit_i - logit_j)^2` multiplicada por `TIE_COEFFICIENT = 1.0` (líneas 11–12 y 94–96).

Reducción: cada estado pesa uno (`mean_state_loss`, líneas 100–105; media de estados en `train_arm`, líneas 151–152). Las pérdidas de los dos brazos no son comparables entre sí por escala.

## 4. Igualdad de arquitectura, datos, inicialización, presupuesto y checkpoint

- Arquitectura: `Linear(17,64) → ReLU → Linear(64,1)` (`tools/model_spec.py`, `build_actor`, líneas 52–63); última capa a cero.
- Datos y normalización: mismos estados de train; media y desviación poblacional de train (`objectives.fit_normalization`, líneas 108–126); development no entra en las estadísticas.
- Inicialización emparejada: `paired_start` clona los pesos de una sola construcción por semilla (`train_loop.py`, líneas 174–180).
- Presupuesto: semillas 11/23/37, 40 épocas, un Adam por época sobre todos los estados, sin early stopping (`TRAINING_CONFIG`, `model_spec.py` líneas 11–44; `train_arm` líneas 132–171).
- Checkpoint: última época (`TRAINING_CONFIG["checkpoint"]`, línea 36). No hay selección de semilla (`seed_selection: False`, línea 37).

## 5. Cuatro candidatas etiquetadas frente a listas completas en despliegue

Etiquetado: `collect_choice_states(..., alternative_limit=4)` (`label_campaign.py`, líneas 41–46) y `select_alternatives` con diversidad de orientación y Chebyshev (`diagnostic.py`, líneas 84–119), siempre incluyendo Greedy.

Despliegue: el actor puntúa `options` completo (`actor_policy.py`, líneas 46–55). En packing se observaron hasta 142 candidatas legales (`campaign_closure.md` §6; `timings.max_legal_candidates` en resultados).

Eso es un desajuste de soporte entre entrenamiento y despliegue.

## 6. ¿Se aísla el objetivo de aprendizaje?

Dentro del piloto, arquitectura, datos, normalización, semillas, inicialización, épocas y checkpoint son comunes; el factor manipulado es la pérdida. Eso aisla el objetivo *condicional* a ese pipeline.

No aísla causas del resultado de packing respecto a: subconjunto de candidatas, estados solo de trayectoria Greedy, dependencia de la continuación Greedy en `Q_hat`, ni el reinicio tras el intento abortado. El regret de ranking sobre estados etiquetados no anticipó de forma uniforme el `U_geom` de episodios (`campaign_closure.md` §5–6); esa discordancia se registra, no se explica.

## 7. Significado de `Q_hat`

`Q_hat` es `effective_u_geom` de una continuación concreta que, tras la acción alternativa, sigue con la política Greedy del motor (`diagnostic.continue_from` + `score_solution`). No es un óptimo global del pedido ni el retorno garantizado de la política aprendida en un episodio completo.

## 8. Datos que faltan para atribuir causas

- Observaciones de estados visitados por cada política aprendida durante el packing, emparejadas con la lista legal completa.
- Etiquetas o scores sobre el mismo subconjunto que usa el actor en despliegue.
- Contrafactuales de arquitectura, presupuesto o regla de subconjunto.
- Incertidumbre preregistrada (el intervalo de este estudio es posterior y exploratorio).
- Test no consultado durante el diseño.

## 9. Intento de entrenamiento abortado

`learning_training_aborted_missing_checkpoint_dir/` falló al guardar: `torch.save` sin directorio padre. No dejó pesos, historiales ni ranking. Los hashes de inicialización y permutaciones del intento completo coinciden con los del abortado y se calculan antes del bucle; el optimizador se crea de nuevo en `train_arm`. El fuente exacto del ejecutor abortado no está en git. Procedencia documentada en `learning_packing/provenance_aborted_attempt.md` y en `run_learning_packing.py` (`_provenance`). No hay evidencia de selección entre varios ajustes completos; tampoco hay un único intento de toda la campaña.
