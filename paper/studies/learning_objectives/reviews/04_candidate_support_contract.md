# Contrato único del subconjunto S

## Incumplimiento detectado en la regla counterfactual

La función `select_alternatives` de `paper/studies/counterfactual_ranking/tools/diagnostic.py` (líneas 84–119) cumple la mayoría de requisitos: incluye Greedy, usa solo geometría presente, limita a cuatro opciones, es determinista y no consulta `Q_hat` ni el sufijo.

No cumple del todo la eliminación de duplicados geométricos: el resto de opciones no se deduplica por `candidate_key` antes de completar S, de modo que dos entradas con la misma geometría podrían entrar en el subconjunto. Tampoco era una fuente única compartida con el despliegue: el actor antiguo puntuaba la lista legal completa.

## Regla adoptada

Nombre: `greedy_plus_orientation_position_diversity_v1`.
Implementación única: `paper/studies/learning_objectives/tools/candidate_support.py`, función `build_candidate_support`.
API de uso: `tools/support_api.py` (`build_S`, `build_S_from_options`, `argmax_in_S`).

Procedimiento:

1. Convertir la lista legal a `GeometryRecord` sin mutarla.
2. Deduplicar por `geometric_id = (bin_index, x, y, z, length, width, height)`.
3. Exigir que la propuesta Greedy esté entre las geometrías únicas y colocarla primera en S.
4. Completar hasta cuatro con la misma clave de diversidad que el diagnóstico: preferir orientación nueva, después máxima distancia de Chebyshev a lo ya elegido, después menor `source_index`.
5. Si hay menos de cuatro geometrías únicas, devolverlas todas.

Identidad de candidata: ese `geometric_id`. Orientaciones distintas no se colapsan.
Empate de logits en despliegue: mayor score; empate exacto → menor índice dentro de S (`select_logit_index`).
El encoder de 17 entradas no se modifica.

## Comparación justa

| Rol | Definición |
| --- | --- |
| A. GreedyBestFit | Política completa sobre todas las candidatas legales. |
| B. Actor aprendido | Construye el mismo S y elige solo dentro de S. |
| C. Mejor retorno examinado | `max_{a in S} Q_hat(s,a)`, solo en diagnóstico o etiquetado. |

Incluir Greedy en S garantiza disponibilidad de su propuesta; no garantiza que el actor reproduzca su packing.

`Q_hat(s,a)` es el `U_geom` de continuar con Greedy tras `a`, con sufijo privilegiado solo al etiquetar. No es óptimo global, ni cota superior del pedido, ni valor de la política aprendida.

## Regret en S

\[
R_S(s)=\max_{a\in S(s)} Q_\mathrm{hat}(s,a)-Q_\mathrm{hat}(s,\pi(s))
\]

Solo si todos los `Q_hat` necesarios son conocidos y \(\pi(s)\in S(s)\). Implementación: `support_metrics.support_regret`. No sustituye episodios completos.

## Compatibilidad de etiquetas anteriores

Auditoría de metadatos sobre 36 pedidos / 144 estados (`label_compatibility.py`):

- Greedy aparece en las alternativas etiquetadas.
- 122 estados tienen `n_legal` mayor que el número de alternativas guardadas.
- La lista legal completa no está persistida → no se puede reejecutar `build_candidate_support` desde el JSON.

Clasificación: **compatibilidad no comprobada para reutilización bajo el contrato único**; `reusable_under_new_support_contract=false`. No se mezclan esas etiquetas con un despliegue restringido a S sin regenerar.
