# C06 — Alineación manuscritos ↔ código ↔ protocolos ↔ resultados

**Fecha:** 2026-10-06
**HEAD de trabajo:** `a40d2b3051e6c3192af55eec5c1c28e1dd0e6093`
**Rama:** `research/paper-online-packing`
**Decisión:** `cerrado_manuscritos_alineados`

Sin experimentos, entrenamiento, inferencia ni packing real. Sin regenerar episodios.
Test cerrado conforme al protocolo; no se propone abrirlo.

## Inventario

| Manuscrito | Estudio / protocolos | Ejecución real | Qué puede presentar | Condición |
|------------|----------------------|----------------|---------------------|-----------|
| `paper/manuscript/learning_objectives/` | `studies/learning_objectives/` | Etiquetas + train + **development** 240; **test no abierto** | Contrastes development, puerta fallida, límites | Borrador development-only cerrado |
| `paper/manuscript/robust_packing_management/` | `studies/robust_packing_management/` | G1 + preflight G2 v1 determinista; **sin RL, sin G2 estocástico** | Formulación + integridad preliminar | Nota preliminar archivada |

Piloto counterfactual: sección propia, exploratorio, muestra/$S$/protocolo distintos;
**sin** causalidad hacia el signo de la campaña. Robust no se mezcla con LO.

## Problemas corregidos (matriz)

| Afirmación / defecto anterior | Corrección | Evidencia | Tipo | Límite restante |
|------------------------------|------------|-----------|------|-----------------|
| `10\|` LaTeX en piloto | Eliminado | `06_results.tex` | Factual | — |
| Agregación «order-then-seed» | Semillas dentro del pedido → media entre pedidos | `aggregation` en verificación | Factual | — |
| 3 semillas = pedidos | Texto: semillas anidadas | discusión | Factual | — |
| 40 epochs / minibatch | 40 Adam full-batch; `n_optimizer_steps=40` | `meta` + `model_spec` | Factual | — |
| Encoder 17 opaco | Tabla nombres/escalas + fuente congelada | `actor_features` + norm JSON | Factual | — |
| EP vs C04 | Motor `ee9e0ec` pre-C04 | histórico `_extreme_points.py` | Factual | No reevalúa bajo C04 |
| Valoración de publicación confusa | Planos (a)(b)(c); no exigir Greedy+/test/estabilidad como universales | `publication_assessment.md` | Mejora editorial | Venue/novedad no establecidos |
| Normalización / selección | Train-only; sin selección época/semilla/brazo | protocolo `normalization`, `seed_selection=false` | Factual | — |

## Afirmaciones respaldadas vs no reclamadas

**Respaldado (development):** pref−class ≈ −0.00808; brazos bajo Greedy (descriptivo);
puerta fallida; test cerrado; $S$ compartido; $Q_{\hat{}}$ Greedy; 9×40 Adam.

**No reclamado:** superioridad general; PCT; causalidad vs piloto; estabilidad física;
novedad/venue; generalización fuera de development.

## Valoración de publicación (cierre)

| Plano | Estado |
|-------|--------|
| (a) Coherencia técnica del manuscrito | Alineada con evidencia |
| (b) Afirmaciones limitadas | Respaldadas |
| (c) Novedad / relevancia / venue | **No establecido** |

La puerta no exige batir Greedy (`does_not_require_beating_greedy`). Un resultado
negativo o no concluyente en development no invalida por sí solo la coherencia
documental. Abrir el test no se propone como remedio editorial.

## Verificación LaTeX

Compilación a `/tmp/c06_lo_build` y `/tmp/c06_rpm_build` (PDF/aux fuera del índice).

## Archivos de publicación C06

Solo documentación/manuscrito revisado (lista exacta en la entrega de commit).
