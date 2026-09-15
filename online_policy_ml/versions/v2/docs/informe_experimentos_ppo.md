# Informe: política online aprendida y PPO

13 de septiembre de 2026. Mismos pedidos BED-BPP (`data/scale/` 80 train / 20 val), mismo validador, geometría 1200×800×2000 mm, encoder v1 (`FEATURE_DIM=35`). El holdout de producto (`examples/5_bed-bpp.json`) no se usó para entrenar ni elegir hiperparámetros. La API no se cambió: sigue cargando `artifacts/models/mlp_v1_p1s1_ppo.pt`.

**Conclusión:** se probaron tres diseños de PPO, cada uno para cerrar el fallo del anterior. Ninguno supera al heurístico ni a la imitación con IC al 95 %. El último (STEP) es idéntico a la imitación en los 20 pedidos de validación. No hay evidencia para reemplazar el checkpoint de producción ni para repetir fine-tuning sobre este encoder.

---

## 0. De dónde se partió

El subproyecto no busca un packer óptimo. Compara metodologías sobre la misma entrada. El modo online ya tenía un heurístico de puntos extremos. La política aprendida debía ser **otro motor**, no un algoritmo nuevo en el catálogo.

Se entrenó primero por imitación (P2O) con el maestro `receding_horizon_ep` (el maestro de volumen privilegiado se descartó: era tautológico respecto al encoder). El MLP de producción es `Linear(35, 64) → ReLU → Linear(64, 1)` y solo puntúa candidatas ya legales.

**Compuerta 04** (val p=1 s=1, n=8, muestra de trabajo):

| Motor | Utilización |
|-------|-------------|
| Heurístico | 0.6826 |
| MLP imitación | 0.6865 |
| Maestro receding | 0.6784 |

El maestro no ganó al heurístico. Imitar más no tenía techo que perseguir. Por eso se decidió PPO: fine-tuning del actor ya entrenado, sin rehacer `01`–`03`.

---

## 1. Primera prueba — PPO con recompensa terminal

**Por qué.** Un PPO clásico espera un retorno al final del episodio. Se usó la utilización de volumen del pallet como única señal.

**Qué se hizo.** p=1, s=1, actor inicial `mlp_v1_p1s1.pt`, muestra corta 24/8.

**Qué salió.** `policy_loss ≈ 0`. El actor no se apartó de la imitación. Un reward que solo aparece al cerrar el pedido no asigna crédito a cada colocación. Esa receta se cerró.

---

## 2. Segunda prueba — PPO v1, recompensa densa de volumen

**Por qué.** GOPT y Zhao (AAAI 2021) usan `r = volumen_ítem / volumen_contenedor` en cada paso. En sus papers esa señal bate a un reward solo terminal. Se pasó a train scale (80) y val (20) para poder hablar de IC.

**Qué se hizo.** Mismo actor, p=1 s=1, 6 epochs, 2 rollouts, `lr=1e-4`, `γ=0.99`. Corte congelado en `versions/v1/`.

**Val n=20, p=1 s=1**

| Motor | Utilización | Ítems | vs PPO |
|-------|-------------|-------|--------|
| Heurístico | 0.6695 | 41.60 | 8–6–6 |
| Imitación | 0.6733 | 41.85 | 5–1–14 |
| PPO | 0.6802 | 42.20 | — |

PPO vs heurístico: +1.07 pp, IC95 [−0.004, +0.026].  
PPO vs imitación: +0.70 pp, IC95 [−0.0001, +0.015].  
`policy_loss` siguió ≈ 0. La entropy subió (2.42 → 2.53): la política se suavizó, no se especializó. En 14 de 20 pedidos el PPO empata con la imitación.

**Lectura.** Hay un sesgo medio a favor del PPO, pero no es significativo. En p=1 s=1 el ítem está fijado: todas las poses legales pagan el mismo volumen. El PPO no tiene señal para elegir *dónde* colocar. Aun así, este `.pt` pasó a ser el default de la API (se retiró la imitación del servicio) como única política aprendida expuesta, **no** porque ganara la compuerta estadística.

---

## 3. Tercera prueba — PPO v2, soporte / altura / critic / KL

**Por qué.** O4M-SP y el repo `alvaro-frank/3d-bpp` añaden al volumen un término de altura y de contacto/soporte, para que dos poses del mismo ítem no paguen igual. GOPT estima V(s) del contenedor, no la media de las candidatas. Un KL hacia la imitación evita que la entropy se escape.

**Qué se hizo.** Mismos 80/20 y p=1 s=1. Reward = volumen + 0.15×soporte − 0.15×z. Critic de 5 números de estado. `PPO_KL_COEF=0.02`. Artefactos en `versions/v2/artifacts/reports/05_ppo.json`.

**Val n=20, p=1 s=1**

| Motor | Utilización | Ítems | vs PPO |
|-------|-------------|-------|--------|
| Heurístico | 0.6695 | 41.60 | 7–6–7 |
| Imitación | 0.6733 | 41.85 | 3–0–17 |
| PPO | 0.6755 | 41.95 | — |

PPO vs heurístico: +0.61 pp, IC95 [−0.011, +0.023].  
PPO vs imitación: +0.23 pp, IC95 [0.000, +0.006], 17 empates.  
El `value_loss` sí bajó (de cientos a ~0.33): el critic por fin estimaba algo. El `policy_loss` siguió en cero. La val (0.6755) es **peor** que el PPO v1 (0.6802).

**Lectura.** Se arregló el baseline de valor y se empeoró el producto. En p=1 s=1 el cuello no era “el critic está roto” ni “falta shaping”. Era la decisión: no hay ítem que elegir.

---

## 4. Cuarta prueba — STEP, PPO sobre el buffer (p=3, s=2)

**Por qué.** El repo más cercano al fallo anterior es [STEP](https://github.com/nikitasarawgi/step-bpp) (ICRA 2026, encima de GOPT). Ellos congelan el colocador y entrenan con RL *qué ítem* del conjunto candidato empaquetar. En nuestro bucle eso es `select_s=2` con lookahead 3, colocación congelada en `mlp_v1_p3s2.pt` (ya existía de la fase de imitación). El volumen **sí** cambia entre acciones. No se tocó el encoder ni el bucle de producción.

**Qué se hizo.** 6 epochs, mismos 80/20. Colocación congelada; PPO solo sobre las poses supervivientes (una por ítem). Informe: `versions/v2/artifacts/reports/05_step.json`. Checkpoint: `versions/v2/artifacts/models/mlp_v1_p3s2_step.pt`.

**Entrenamiento.** Entropy 0.46–0.52 (coherente con ~2 acciones; ln 2 ≈ 0.69). `value_loss` ~0.08. `policy_loss` otra vez ≈ 0. KL 0.0004 → 0.012. El mejor `val_util` es el de la **época 0**: el actor inicial, antes de PPO. Cada epoch posterior empeoró o no mejoró.

**Val n=20, p=3 s=2**

| Motor | Utilización | Ítems |
|-------|-------------|-------|
| Heurístico | 0.6812 | 41.90 |
| Imitación (`mlp_v1_p3s2.pt`) | 0.6832 | 42.15 |
| STEP | 0.6832 | 42.15 |

STEP vs heurístico: +0.20 pp, IC95 [−0.010, +0.016], 7–6–7.  
STEP vs imitación: **+0.00 pp, 20 empates de 20**.

**Lectura.** El espacio de acción sí era el de STEP (la entropy lo confirma). El PPO no encontró ninguna política de selección distinta de la imitación. El colocador congelado más el selector BC ya empatan con el heurístico. Fine-tunear el selector no añade nada.

---

## 5. Lectura conjunta

```
prueba 1  reward terminal     → no hay gradiente
prueba 2  volumen (GOPT)      → media +1 pp, IC cruza 0, 14 empates
prueba 3  shaping + critic    → critic ok, producto peor, 17 empates
prueba 4  STEP p=3 s=2        → copia exacta de la imitación
```

Tres veces se cambió la *hipótesis* (señal, baseline, decisión). Tres veces el actor de PPO no se apartó de la imitación de forma útil. El tope no es el optimizador ni el número de epochs. Es el encoder v1 + el bucle irrevocable de puntos extremos: la imitación ya satura lo que esos features pueden puntuar, y el heurístico está en el mismo sitio.

La política de producción (`mlp_v1_p1s1_ppo.pt`) es un baseline comparable al heurístico, no un packer mejor. Decirlo de otro modo sería mentir con los IC.

---

## 6. Plan de acción

1. **Cerrar el fine-tuning PPO sobre este encoder.** No más `05` con otros coeficientes, más rollouts o más KL. Las cuatro pruebas cubren la familia de recetas que se podía aplicar sin cambiar el contrato `packing-services-online-policy` v1.

2. **No promocionar** el STEP ni el PPO de shaping. No copiar `mlp_v1_p3s2_step.pt` ni el `.pt` de v2 al path de la API.

3. **Dejar la API como está** (`policy=rl`, `mlp_v1_p1s1_ppo.pt`) y documentar en producto que es un empate estadístico con el heurístico online. Si se quiere el motor más simple, el heurístico basta: misma validez, misma geometría, sin PyTorch.

4. **No reabrir `01`–`04`** para “ganar décimas” sobre los mismos 20 de val. El holdout de producto sigue bloqueado.

5. **Si más adelante se busca un packer mejor**, el siguiente experimento no es PPO. Es **otro estado**: heightmap 2D u otra representación (Zhao: el mapa de alturas bate al vector de ítems). Eso es `FEATURE_VERSION=2`, otro checkpoint y otra carga en el execute. No se abre ahora; se abre solo si se decide un ciclo de modelado nuevo, con val y holdout distintos de este informe.

6. **Trabajo útil que no es modelado:** notebook `10` (consolidación multi-pallet) y el informe de holdout ya existente. Miden producto; no reentrenan.

**Estado del plan (13 de septiembre de 2026):** los seis puntos están en vigor. El `05` no se relanza (hace falta `--force`). La API sigue en `mlp_v1_p1s1_ppo.pt` y el producto documenta el empate. El trabajo vivo es el notebook `10`.
