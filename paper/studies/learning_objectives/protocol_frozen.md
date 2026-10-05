# Protocolo congelado — learning_objectives

Estado: **congelado**. No autoriza etiquetado, entrenamiento, desarrollo ni test.
Antecedente no congelado: `design_draft.md`.
HEAD de congelación: `904038ff7f495510f1b8f3d398da3e4eb281a406` en `research/paper-online-packing`.

SHA256 del JSON: ver campo `sha256` en `protocol_frozen.json`.

## 1. Contrato geométrico

- Secuencia: orden de entrada original del pedido.
- Un contenedor del target propio del pedido.
- `p = s = 1`.
- Hasta seis permutaciones de orientación según la conversión auditada compacta.
- Contención y no solape **activos**.
- Peso máximo, estabilidad básica y load-bearing **inactivos**.
- Parada en el primer ítem actual sin candidata legal.
- `U_geom =` volumen orientado colocado / volumen fijo del contenedor.
- `physical_stability_verified = null`.

## 2. Subconjunto S — `greedy_plus_orientation_position_diversity_v1`

Fuente única: `tools/candidate_support.py::build_candidate_support`.
Puntos de llamada: `pipeline.labeling_select_support`, `pipeline.deployment_select_action`, `support_api.build_S` / `build_S_from_options`.

### 2.1 Identidad geométrica y numeración

```
geometric_id = (int(bin_index), float(x), float(y), float(z),
                float(length), float(width), float(height))
orientation  = (float(length), float(width), float(height))
position     = (float(x), float(y), float(z))
```

Comparación: igualdad exacta de tuplas tras `float()` / `int()`. No hay tolerancia espacial en la identidad.

### 2.2 Pseudocódigo reproducible

```
chebyshev(a, b) = max(|a.x-b.x|, |a.y-b.y|, |a.z-b.z|)

dedupe(legal):
  seen ← ∅; out ← []
  for r in legal in legal order:
    if r.geometric_id ∉ seen:
      seen.add(r.geometric_id); out.append(r)
  return out

build_S(legal, greedy_id, limit=4):
  unique ← dedupe(legal)
  greedy ← unique row with geometric_id == greedy_id   # error if absent
  chosen ← [greedy]
  rest ← unique without greedy
  while |chosen| < limit and rest ≠ ∅:
    known_orient ← {orientation(r) for r in chosen}
    best ← argmax over rest of key:
      new_ori = 1 if orientation(c) ∉ known_orient else 0
      d = min{ chebyshev(c, s) for s in chosen }
      key = (new_ori, d, -source_index(c))   # lexicographic, maximize
    append best to chosen; remove best from rest
  return chosen   # order = final order of S
```

Prioridades de diversidad (en orden):

1. Preferir orientación aún no representada en los elegidos.
2. Entre empates, maximizar la distancia Chebyshev mínima a los ya elegidos.
3. Empate residual: mayor `-source_index` (menor índice en la lista legal original).

Orden final de S: Greedy en posición 0; el resto en el orden en que la diversidad los añadió.

Empate exacto de logits en despliegue: mayor score; si hay empate float exacto, menor índice en S.

## 3. Q_hat

`Q_hat(estado, acción) = U_geom` de una continuación **Greedy completa** tras aplicar la acción, usando el sufijo real del pedido **solo** para generar la etiqueta.

No es óptimo global, cota superior global ni valor de la política aprendida.

## 4. Brazos y pérdidas (mayor score = mejor)

Constantes: `TIE_EPS = 1e-9`, `TIE_COEFFICIENT = 1.0` (preferencias; sin temperatura).
Reducción entre estados: media aritmética con peso uno por estado (`mean_state_loss`).

1. **Clasificación** (`classification_loss`): CE natural con `softmax(logits)`; masa uniforme sobre argmax de `Q_hat` con tolerancia `1e-9`.
2. **Preferencias** (`preference_loss`): todos los pares `i < j`; no empatados → softplus del margen orientado al mayor `Q_hat`, peso `|ΔQ|` renormalizado a suma 1; empatados → media de `(logit_i − logit_j)² × 1.0`.
3. **Diferencias de retorno** (`return_difference_loss`): adaptación de Mandi et al. (2022) §4.3 Eq. (13); media de `((s_p − s_q) − (Q_p − Q_q))²` sobre pares estrictos `Q_p > Q_q + 1e-9`; 0 si no hay pares.

## 5. Arquitectura y ajuste

- Encoder presente de 17 características, sin información del sufijo.
- `Linear(17, 64) → ReLU → Linear(64, 1)`; última capa inicializada a cero.
- Semillas informadas: 11, 23, 37; inicializaciones emparejadas entre brazos.
- 40 épocas; un paso Adam por época sobre la media de pérdidas de estado.
- Adam: `lr=0.001`, `weight_decay=1e-4`, `betas=(0.9, 0.999)`, `eps=1e-8`; `amsgrad`, `foreach`, `fused` desactivados.
- Clip de norma 2 con máximo 1.
- Checkpoint de época 40; sin early stopping ni selección de semilla.
- CPU; un hilo Torch y uno de interoperación por proceso.
- Misma secuencia de permutaciones por semilla y brazo.
- Normalización solo con filas de train: peso igual por fila; desviación poblacional; denominador 1 si la columna es constante. No reajustar en desarrollo/test.

## 6. Muestras

Cadena de selección (antes de ordenar):

```
learning-objectives-v1|20261005|{split}|{order_id}
```

Orden: SHA256 de esa cadena; desempate por `order_id`.

| Split | n | por target | pool |
| --- | ---: | ---: | --- |
| train | 48 | 24 | full.val |
| development | 24 | 12 | full.val |
| test | 100 | 50 | full.test |

Tamaños = alcance/presupuesto; **no** potencia estadística.

Exclusiones: exposición positiva registrada (manifiestos, casos, `execution_ids`, exclusiones positivas); no se tratan como exposición positiva los catálogos de ausencia (`uncertain` / `missing` / `absent` / `candidates`). `full.test` no se autoexcluye al muestrear test. Firmas de snapshot: clones de exposición positiva y de train/dev seleccionados bloquean test. Ausencia de registro ≠ independencia absoluta.

El manifiesto de test identifica pedidos; **no** se ejecutan conversiones analíticas de packing/etiquetas/predicciones/retornos sobre test en este paso.

## 7. Etiquetado y métricas

Hasta cuatro estados por pedido en cuantiles de la trayectoria Greedy:

```
si N ≤ 4: todos
si no: índice_i = floor(i*(N-1)/(4-1) + 1/2); duplicados descartados sin relleno
```

Máximos previstos: train 192 estados / 768 continuaciones; desarrollo 96 / 384.
Estados incompletos se conservan; no se entrena con etiquetas parciales; no se reutilizan etiquetas antiguas incompatibles.

Contraste primario: `d_i =` media en semillas de `U_geom(preferencias,i) − U_geom(clasificación,i)`; resultado = media aritmética de `d_i` (peso igual por pedido).

Secundarios: diferencias de retorno vs otros brazos; ambos principales vs Greedy; desglose por target; `R_S` en estados etiquetados; fallos y tiempos. Greedy una vez por pedido bajo el mismo contrato.

Bootstrap de test (solo cuando se autorice): 20000 réplicas, `numpy.random.default_rng(20261005)`, remuestreo de pedidos estratificado por target, semillas y métodos juntos; percentiles 2.5 y 97.5, `method="linear"`.

## 8. Puertas

Operativa (antes de campaña): soporte/entradas/restauración/geometría; ningún retorno desconocido en preflight; hashes verificables; presupuesto estimado compatible con incertidumbre.

Tras entrenamiento: nueve modelos; emparejamiento; datos/normalización; sin no-finitos. No decide por pérdidas favorables.

Desarrollo (umbrales fijados ahora): media pref−class ≥ 0.005; diferencia positiva en ≥2/3 semillas; agregada no negativa en cada target; evaluación completa auditada; presupuesto restante para test. Puerta de ingeniería, no de significancia. No exige superar Greedy.

Si falla: no cambiar brazos, semillas, S, umbrales ni tamaños; no abrir test.

## 9. Presupuesto de pared (cómputo experimental nuevo)

Techo total 28800 s: preflight 900; etiquetado 13500; entrenamiento 1800; desarrollo 3600; test 9000.
Sin reasignación automática. Auditoría incluida en cada etapa. Redacción aparte.
Retornos desconocidos = `null`, no cero. Fallo operativo en episodio: caso en denominador con `U_geom` efectivo 0 y fallo visible.

## 10. Preflight de este paso

Dos primeros pedidos train por target; dos primeros estados de su selección por cuantiles; todas las alternativas de S; ≤4 estados y ≤16 continuaciones; techo 900 s. Sin entrenamiento, desarrollo ni test.
