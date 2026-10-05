# Mapeo respecto a Mandi et al. (ICML 2022)

## Fuente verificada

- Título: *Decision-Focused Learning: Through the Lens of Learning to Rank*
- Autores (PMLR): Jayanta Mandi, Víctor Bucarey, Maxime Mulamba Ke Tchomba, Tias Guns
- Venue: Proceedings of the 39th International Conference on Machine Learning, PMLR 162:14935–14947, 2022
- HTML: https://proceedings.mlr.press/v162/mandi22a.html
- PDF: https://proceedings.mlr.press/v162/mandi22a/mandi22a.pdf (descargado para lectura; size 1809349 bytes)
- Preprint arXiv: https://ar5iv.labs.arxiv.org/html/2112.03609 (ecuaciones leídas también en HTML ar5iv)
- Código de los autores: https://github.com/JayMan91/ltr-predopt (no ejecutado)

Nota de autoría: el HTML de PMLR lista “Maxime Mulamba Ke Tchomba”; el abstract HTML de ar5iv usa “Maxime Mulamba”. Se adopta la forma de PMLR para la cita del proceedings.

## Formulación del artículo

Marco predict-and-optimize / decision-focused learning: un modelo predice parámetros de coste \(\hat{c}\) de un problema combinatorio; la pérdida mira la calidad de la decisión \(v^\star(\hat{c})\).

Regret (Eq. 3): \(\mathrm{Regret}(\hat{c},c)=f(v^\star(\hat{c}),c)-f(v^\star(c),c)\).

Surrogate NCE de Mulamba et al. (Eq. 5): promedio de \(f(v^\star(c),\hat{c})-f(v^s,\hat{c})\) sobre un subconjunto \(S\).

Pérdidas de ranking sobre un subconjunto \(S\subseteq V\):

1. Pointwise (Eq. 6): \(\frac{1}{|S|}\sum_{v\in S}(f(v,\hat{c})-f(v,c))^2\).
2. Pairwise margin / best-vs-rest (Eq. 11–12): hinge sobre pares ordenados por el coste verdadero; con margen 0 y best-vs-rest recupera una forma próxima a NCE.
3. Pairwise-difference (Eq. 13): promedio de cuadrados de la diferencia entre \((f(v^p,\hat{c})-f(v^q,\hat{c}))\) y \((f(v^p,c)-f(v^q,c))\) sobre pares ordenados.
4. Listwise / ListNet (Eq. 15–16): softmax con temperatura \(\tau\) sobre \(-f(v,\cdot)/\tau\) y entropía cruzada entre \(p_\tau(\cdot|c)\) y \(p_\tau(\cdot|\hat{c})\).

El artículo trata soluciones factibles de un CO con solver; controla \(|S|\) para coste computacional.

## Formulación nuestra (piloto counterfactual)

No hay predicción de un vector de costes \(\hat{c}\) ni llamada a un solver CO durante el entrenamiento. Hay un puntuador \(s_\theta(x_a)\) por candidata local \(a\) en un estado de packing online. Las etiquetas son \(Q_\mathrm{hat}(a)\): retorno geométrico de continuar con Greedy tras elegir \(a\).

Pérdidas existentes (`tools/objectives.py`):

- Clasificación: CE entre softmax de logits y uniforme sobre máximos empatados de \(Q_\mathrm{hat}\).
- Preferencias: pares con peso \(|\Delta Q|\), softplus del margen de logits, más penalización cuadrática de empates.

Despliegue: argmax de logits sobre candidatas legales del ítem actual.

## Elementos adaptables

- Tratar candidatas (o un subconjunto determinista) como el conjunto \(S\) a ordenar.
- Usar una pérdida de diferencias de retorno inspirada en la pairwise-difference (Eq. 13), sustituyendo \(f(v,c)\) por \(Q_\mathrm{hat}\) y \(f(v,\hat{c})\) por el score del modelo, con la misma \(S\) en train y en despliegue.
- Mantener listwise con temperatura como brazo futuro, sin fijar aún \(\tau\).
- Reportar regret de ranking en \(S\) además de `U_geom` de episodio completo.

## Diferencias que impiden hablar de reproducción exacta

| Dimensión | Mandi et al. | Nuestro piloto |
| --- | --- | --- |
| Objeto puntuado | Soluciones factibles \(v\in V\) de un CO | Candidatas locales de un paso online |
| Predicción | Costes \(\hat{c}=m(\omega,x)\) | Score directo por candidata |
| Etiqueta | Objetivo verdadero \(f(v,c)\) / óptimo del solver | Continuación Greedy del sufijo |
| Subconjunto \(S\) | Cache de soluciones del solver | Hasta 4 alternativas diversas + Greedy |
| Pérdida pairwise-difference | Eq. 13, MSE de diferencias de \(f\) | No implementada; la preferencia usa softplus ponderado |
| Listwise | Eq. 16 con \(\tau\) | No implementada |
| Métrica final | Regret del CO | `U_geom` de episodio completo bajo contrato compacto |

## Comparación explícita con nuestras pérdidas

- Nuestra clasificación se parece más a un listwise degenerado sin temperatura y con masa solo en los máximos empatados, no a la Eq. 16 con \(p_\tau(v|c)\) suave.
- Nuestra preferencia **no** es la pairwise-difference de Mandi (Eq. 13): no regresa la diferencia de retornos con un error cuadrático entre pares; usa softplus sobre el margen de logits y pesos \(|\Delta Q|\). Llamarla “pairwise-difference de Mandi” sería incorrecto.
- Tampoco es exactamente la pairwise hinge (Eq. 11): no hay margen \(\nu\) fijo ni esquema best-vs-rest exclusivo; se usan todos los pares no empatados.

## Límite de lectura

Las ecuaciones anteriores se verificaron en el PDF de PMLR (vía extracción de texto) y en el HTML ar5iv del preprint `2112.03609`. No se ejecutó el repositorio de los autores. No se inventan números de tabla más allá de los citados en el HTML leído para contexto.
