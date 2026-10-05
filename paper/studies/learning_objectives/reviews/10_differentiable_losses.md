# 10 — Pérdidas diferenciables

HEAD de trabajo: `ee1e6b925a8cb539139bd00958de9d6984937fc3`.
`tools/losses.py` permanece intacto (hash congelado).
Implementación tensorial: `tools/torch_losses.py`.

## Qué garantiza esta verificación

Las tres pérdidas coinciden numéricamente (float64) con las fórmulas de referencia,
admiten `autograd.gradcheck` en casos adecuados, producen gradientes finitos y
direcciones coherentes, y soportan `backward` sobre la media de varios estados.
**No** demuestra que 40 pasos Adam basten para converger, ni que una pérdida sea
superior a otra en packing.

## Fórmulas (sin cambio)

Constantes: `TIE_EPS=1e-9`, `TIE_COEFFICIENT=1.0`. Sin temperatura.
Reducción entre estados: media aritmética con peso uno.

1. Clasificación: masa uniforme sobre máximos de `Q_hat`; CE con `log_softmax`.
2. Preferencias: pares `i<j` estrictos con peso `|ΔQ|` renormalizado y
   `softplus(-(s_high−s_low))`; empates: media de `(s_i−s_j)² × 1`.
3. Diferencias de retorno: media de `((s_h−s_l)−(Q_h−Q_l))²` sobre pares estrictos;
   sin pares: pérdida `0` conectada al grafo (gradiente cero).

`Q_hat` se desacopla del grafo (`detach`); los scores no se convierten a float.

## Limitación de la referencia congelada

`losses.py` usa `math.exp`/`math.log` sobre softmax. Con logits extremos
(p. ej. ±80) puede underflow o dejar de ser finita. La equivalencia matemática
en ese régimen se comprueba con una referencia estable adicional
(log-sum-exp) en las pruebas; **no** se modifica el archivo congelado.

## Pruebas

`tests/test_torch_losses.py`: concordancia, gradcheck, empates, una candidata,
NaN/Inf, logits extremos, media de estados + un paso SGD sintético.
