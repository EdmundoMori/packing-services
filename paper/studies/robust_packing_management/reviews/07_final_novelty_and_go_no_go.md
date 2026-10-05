# Revisión 07 — novedad final y go / no-go experimental

**Fecha:** 2026-10-05
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2` · `research/paper-online-packing`
**AGENTS.md:** ausente
**Prohibido en esta pasada:** packing BED-BPP, ruido nuevo, entrenamiento, commit/push.

## Decisión inequívoca

**`cerrar_linea_por_justificacion_insuficiente`**

No se autoriza nueva inversión experimental (G2 estocástico, muestreo, RL).
Las campañas anteriores permanecen cerradas e intactas. El cuerpo documental se reinterpreta como **formulación y evaluación preliminar**, no como artículo listo para envío.

---

## Tarea 1 — Corrección del ejemplo secuencial

### Especificación explícita (código `tools/sequential_necessity_example.py`)

| Elemento | Valor |
|----------|--------|
| \(\rho^\star\) de \(\mathcal{L}\) | **0.5** |
| \(\varepsilon\) | \(\{0,\,0.25\}\) con masas \(1/2,\,1/2\) |
| Ejes | mismo \(\varepsilon\) en L,W,H (dependencia perfecta intra-ítem) |
| Ítems | independencia entre ítems |
| Info de \(\mathcal{L}\) | \(C\), \(N_1\), menú, ley \(P_\varepsilon\), candidatas sintéticas; **sin** \(R\), **sin** sufijo, **sin** \(N_2\) |
| Generación de poses | conjunto finito `{RIGHT=(4,0,0), LEFT=(0,0,0)}`; admisible si envelope cabe |
| Chooser | **sintético**: maximiza \(x\), luego min \(y,z\) — **no** es ExtremePoint del motor de producción |
| \(J_B\) | \(V_{\mathrm{nom}}/\mathrm{Vol}(C)\) si no hay `geometric_failure` en el episodio; **0** si falla (ítem-1 o ítem-2). \(\mathrm{Vol}(C)=10\cdot8\cdot5=400\). \(V_1=60\), \(V_2=12.03\), \(V_{1+2}/400=0.180075\) |
| Criterio \(\mathcal{L}\) | pose existe y \(\rho_{\mathrm{imm}}\le 0.5\); **minimizar** \(\sum m\); desempate por rank del chooser |

### ¿La “ventaja” se explica porque \(\mathcal{L}\) acepta riesgo 0.5 y minimiza margen?

**Sí.** Enumeración existente (sin nuevas simulaciones):

| Regla | \(m\) | \(\rho_{\mathrm{imm}}\) | \(U_{\mathrm{imm}}\) | \(\mathbb{E}[J_B]\) |
|-------|-------|------------------------|----------------------|---------------------|
| \(\mathcal{L}\) (\(\rho^\star=0.5\), min margen) | \(m_0\) | 0.5 | 0.075 | 0.0900375 |
| Preferir garantista si admisible | \(m_g\) | 0.0 | 0.15 | 0.13505625 |
| Maximizar \(U_{\mathrm{imm}}\) | \(m_g\) | 0.0 | 0.15 | 0.13505625 |
| Búsqueda limitada \(\mathbb{E}[J_B]\) con \(N_2\) declarado | \(m_g\) | 0.0 | 0.15 | 0.13505625 |

\(U_{\mathrm{imm}}=\mathbb{E}[V_1/\mathrm{Vol}\mid\text{ítem-1}]\).
Las tres referencias analíticas fuertes **coinciden** en \(m_g\) y empatan el óptimo del menú. Residual frente a ellas: **0**.

El ejemplo **no** es prueba sobre el motor EP real (chooser artificial).
Rev 06 sobre-interpretó “pregunta no trivial” respecto de una \(\mathcal{L}\) **débil**.

### Trivialidad corregida

- Calcular la protección **garantista** \(m_g=\varepsilon_{\mathrm{hi}} N\) es directo bajo soporte conocido.
- Eso **no** resuelve automáticamente todo packing seguro futuro en general (p. ej. si \(m_g\) es inadmisible y hay trade-offs de layout).
- **Este juguete** no exhibe residual tras “preferir \(m_g\) si admisible” ni tras maximizar utilidad inmediata.
- Por tanto no justifica RL ni una campaña experimental.

---

## Tarea 2 — Antecedentes verificados (fuentes primarias)

| Trabajo | Formulación / decisión | Evaluación | Citación | Limitación explícita vs inferencia |
|---------|------------------------|------------|----------|-------------------------------------|
| **Wang & Hauser**, Dense Robotic Packing, TRO 2021 (preprint leído) | Packing robótico de objetos irregulares; **robust planning** con umbral de holgura \(\delta\); si falla, \(\delta\) baja linealmente a 0; closed-loop vision | Sim Monte-Carlo + plataforma; V1–V4; \(\delta\approx 1\) cm | §B Error reduction; §D Robust planning (eq. scoring con \(C/\max(d_{\min},\delta)\)); Fig. 9; Tab. física | Explícito: márgenes conservadores + replanning. **Inferencia:** ya cubren selección adaptativa **determinista** de holgura bajo incertidumbre de ejecución/modelo — no RL de margen |
| **GOPT**, Yang et al., arXiv 2409.05344v2 | Online 3D-BPP DRL (Transformer); colocación | Sim + robot; buffer fijo | **§IV-E**: buffer 0.7 cm → 67.5% util.; buffer 0 → 2/20 fallos, 73.3% en éxitos; §V fiabilidad futura | Explícito: trade-off buffer/utilización con buffer **fijo**. **Inferencia:** no política de margen paso a paso; el trade-off riesgo–compactación **sí** está documentado |
| **Zhao et al.**, Online 3D-BPP constrained DRL, arXiv 2006.14978 | CMDP online; colocación bajo estabilidad/orden | Benchmarks sim | Texto leído (HTML) | Estabilidad/orden; **no** margen dimensional como acción de gestión |
| **Zhao et al.**, Practically feasible policies, arXiv 2108.13680 | DRL online; deriva de colocación ±5 cm (20% trials) | Utilización bajo drift | § sobre high-resolution / drift | Incertidumbre de **posición**, no política de holgura dimensional |
| **AR2L**, Pan et al., NeurIPS 2023 | Robustez a permutación de **secuencia** | Ataques de orden | PDF conferencia | Clase distinta de incertidumbre |
| **LBCP / SRP**, arXiv 2507.09123v1 | Estabilidad bajo incertidumbre de CoG acotada; buffer en despliegue real; ventana encogida ante sensibilidad a tamaño | Sim + robot | Eq. (1) \(\delta_{CoG}\); § real packing buffer / size sensitivity | Robustez geométrica/estabilidad; **no** formaliza gestión RL de protección dimensional online p=s=1 BED-BPP |
| **BED-BPP**, Kagerer et al., IJRR | Dataset pedidos nominales; KPI propios | Solvers publicados | §3 tolerancia 2 cm n-gram; §6 | **No** solver de protección; 2 cm ≠ ley de error de caja |
| **Shuai et al.**, IET CTA 2023 | Compliance / contacto bajo plural incertidumbre | Sim + físico | Abstract + cuerpo parcial | PDF completo: **parcialmente no verificado** (Cloudflare). No RL de margen en lo verificado |
| Online BP size estimates, arXiv 2505.09321 | 1D con estimados | Ratios competitivos | HTML | No 3D online protección |
| ASAP, arXiv 2501.17377 | Shift de distribución de ítems | Fine-tune selección | HTML | No margen geométrico |

**Regla respetada:** no se declara “nadie lo resolvió” por ausencia en la búsqueda. BED-BPP o RL **no** son novedad por sí solos.

---

## Tarea 3 — Matriz de contribución (máx. 2)

### Candidata A — “RL de protección geométrica online sobre nominales BED-BPP”

| Campo | Contenido |
|-------|-----------|
| Qué añade | Política que elige \(m\) online bajo error dimensional sintético, score \(J_B\) nominal |
| Antecedente más próximo | Wang & Hauser \(\delta\) adaptativo determinista; GOPT buffer fijo + DRL de colocación |
| Diferencia sustantiva | Acción = margen (no solo pose); metric nominal; ley sintética formalizada |
| Por qué importaría | Trade-off riesgo–volumen en pedidos industriales nominales |
| Artefactos reutilizables | Arnés G1; freeze/preflight v1 (solo determinista); formulaciones |
| Evidencia mínima | Residual material vs prefer-guarantee / cuantiles / búsqueda limitada en diseño emparejado |
| Baseline fuerte | \(m_g\) admisible; max \(U_{\mathrm{imm}}\); δ-style reduction; buffer fijo GOPT |
| Coste previsto | Alto (diseño estocástico, ≥O(10²) episodios, verify) sin garantía de residual |
| **Motivo de descarte** | El juguete secuencial **no** deja residual tras baselines fuertes; v1 fue trivial; no hay evidencia de que RL sea necesario ni superior; solapamiento conceptual con holguras conservadoras ya publicadas |

### Candidata B — “Benchmark de gestión de protección bajo sensibilidad dimensional sintética”

| Campo | Contenido |
|-------|-----------|
| Qué añade | Protocolo + escenarios + métricas de riesgo/J_B para comparar reglas de margen |
| Antecedente más próximo | Contratos de evaluación BED-BPP; ablations de buffer en GOPT §IV-E |
| Diferencia sustantiva | Separar envelope_exceeded / geom_fail / no_candidate; J_B nominal |
| Por qué importaría | Reproducibilidad de diagnósticos de protección |
| Artefactos | tools/, tests, protocol drafts |
| Evidencia mínima | Pregunta científica que el benchmark distinga y que antecedentes no midan |
| Baseline fuerte | Reglas analíticas de §Tarea 1 |
| Coste | Medio (ingeniería) pero vacío sin pregunta discriminante |
| **Motivo de descarte** | Una colección de scripts/escenarios **no** es contribución; sin residual ni pregunta que separe de buffers/δ ya estudiados, no justifica inversión |

**Ninguna candidata sobrevive** el filtro de contribución concreta + evaluación pequeña capaz de distinguirla.

---

## Tarea 4 — Go / no-go

| Pregunta | Respuesta |
|----------|-----------|
| ¿Hay contribución específica justificable ahora? | **No** |
| ¿Continuar a G2/RL/muestreo? | **No** |
| ¿Falta evidencia (sin prometer publicación)? | Residual vs baselines analíticas fuertes en un problema **no** juguete y **no** trivializado por \(m_g\); ley de error con anclaje empírico (hoy ausente en BED-BPP); novedad frente a δ/buffer que sobreviva revisión peer con fuentes primarias. Nada de esto autoriza experimentos en esta pasada |

### Opción elegida

**`cerrar_linea_por_justificacion_insuficiente`**

No `novedad_no_resuelta_por_fuentes_faltantes` (las fuentes clave **sí** se leyeron).
No `contribucion_concreta_para_diseno_experimental` (no hay contribución concreta).

---

## Manuscrito / alcance

Corregir: el ejemplo solo muestra fallo de \(\mathcal{L}\) débil; chooser sintético; no motor EP; no justifica RL.
Documento = formulación + chequeos preliminares (G1, preflight v1, auditoría, juguete).
**No** artículo listo para envío. Campañas previas conservadas.
