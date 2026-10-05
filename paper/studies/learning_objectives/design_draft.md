# Borrador de diseño: learning_objectives

Estado: borrador revisado tras el contrato único de S. No congela protocolo. No autoriza etiquetas, entrenamiento ni packing.

## Pregunta

¿Cómo afecta el objetivo de supervisión a la calidad de episodios completos de packing online, manteniendo comunes representación, etiquetas, motor, presupuesto y subconjunto de candidatas S?

## Registro de correcciones

1. **Desajuste etiquetado/despliegue (corregido en especificación).** El piloto counterfactual etiquetaba ≤4 candidatas y desplegaba sobre la lista legal completa. Ahora etiquetado, entrenamiento y despliegue deben llamar a la misma `build_candidate_support` (`tools/candidate_support.py` / `support_api.py`).
2. **Deduplicación geométrica.** Se documentó que `select_alternatives` del diagnóstico no deduplicaba el resto; la regla v1 añade dedupe por `geometric_id` y reutiliza la diversidad de orientación/posición.
3. **Comparación justa.** Se distinguen Greedy completo (A), actor restringido a S (B) y mejor `Q_hat` en S (C); se define `R_S` sin sustituir episodios.
4. **Contraste primario fijado en el diseño (aún no congelado en protocolo):** media por pedido tras semillas emparejadas de preferencias−clasificación. Diferencias de retorno = secundario. Greedy = referencia obligatoria.
5. **Etiquetas antiguas:** compatibilidad no comprobada / no reutilizables bajo el contrato único sin regenerar.

Detalle: `reviews/04_candidate_support_contract.md`, `reviews/05_experiment_design_decisions.md`.

## Motivación acotada

El piloto counterfactual aisló dos objetivos y, en desarrollo, preferences superó a classification en media de `U_geom` sin superar a Greedy. Ese piloto es exploratorio e incompatible con una reproducción exacta del nuevo soporte. Mandi et al. (2022, §4.3, Eq. 13) inspiran el brazo de diferencias de retorno; la preferencia existente no es esa pérdida.

## Brazos

1. Clasificación sobre máximos empatados de `Q_hat` en S.
2. Preferencias existentes en S.
3. Diferencias de retorno adaptadas de Mandi sobre S (secundario).

## Contrato geométrico propuesto

- Secuencia original; un contenedor del target; `p=s=1`.
- Orientaciones explícitas; contención y no solape.
- Peso, estabilidad y load-bearing inactivos.
- Parada ante el primer ítem sin candidata legal.
- `physical_stability_verified=null`.

## Subconjunto S

Fuente única: `build_candidate_support` / `build_S_from_options`.
Máximo cuatro geometrías distintas; Greedy siempre incluido; solo información presente; empates deterministas; sin mutar la lista legal.

## Lo que todavía no se congela

Tamaños e IDs de muestra, hiperparámetros, umbrales de puerta, presupuesto demostrado, selección de test. Opciones mínimas recomendadas en review 05.

## Relación con campañas cerradas

Compacta, counterfactual y PPO de reglas permanecen cerradas. Este borrador no las reabre.
