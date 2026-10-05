# Formulación v2 (borrador actualizado) — decisión secuencial de protección

**Estado:** borrador · no congelado · no ejecutado · no sustituye freeze v1
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Prueba asociada:** `reviews/06_sequential_decision_check.md`

---

## 1. Objetos

- Contenedor \(C=(C_L,C_W,C_H)\) mm, fijo (target del pedido).
- Ítem \(t\): nominal \(N_t\in\mathbb{R}_{>0}^3\); realizado \(R_t\in\mathbb{R}_{>0}^3\).
- Orientación \(\omega\): permutación de ejes; \(R_t\) **no** se remuestrea (se permuta el mismo vector).

## 2. Ley pública del error (sensibilidad sintética)

\[
R_{t,i}=\max\bigl(1,\, N_{t,i}(1+\varepsilon_{t,i})\bigr),\qquad i\in\{L,W,H\}.
\]

**Elección declarada para el análisis v2 (no calibración BED-BPP):**

- Entre ítems: \(\varepsilon_t\) independientes.
- Entre ejes: **mismo** \(\varepsilon_t\) en los tres ejes (dependencia perfecta intra-ítem); alternativa i.i.d. por eje queda como variante de sensibilidad a fijar solo al congelar.
- Soporte discreto de trabajo en la prueba sintética: \(\varepsilon\in\{0,\varepsilon_{\mathrm{hi}}\}\) con masas conocidas; en continuo, p. ej. \(\mathrm{Unif}[0,\varepsilon_{\max}]\).
- Unidades: \(\varepsilon\) adimensional; dims mm; positividad por `max(1,·)`.

Historial de errores **no** informa \(\varepsilon_{t+1}\) bajo independencia entre ítems.

## 3. Información

**Antes de actuar en \(t\):**
\(C\), \(N_t\), geometría revelada \(G^{\mathrm{rev}}\) (AABB realizados de éxitos), ley \(P_\varepsilon\), menú de protecciones.
**No:** \(R_t\), \(\varepsilon_t\), sufijo de ítems, resultados de protecciones no evaluadas.

**Después de un éxito:** se revela \(R_t\) exacto y se actualiza \(G^{\mathrm{rev}}\) (idealización de simulador).

## 4. Acción, chooser, transición

- Acción de gestión: protección \(m\in\mathcal{M}\) (márgenes por eje ≥0).
- Envelope orientado: \(E = N^{(\omega)}+m^{(\omega)}\).
- Chooser **fijo** (misma regla para todos los métodos): elige pose \(p\) entre candidatas cuya envelope es factible vs \(C\) y \(G^{\mathrm{rev}}\).
- Distinción: **margen** vs **seguridad de la pose realizada** — \(m\) cambia el conjunto de candidatas y por tanto \(p\); el fallo geométrico se evalúa con el AABB **realizado** en \(p\), no con la envelope.

**Eventos:** `no_candidate` · `envelope_exceeded` (≠ fallo) · `geometric_failure` (terminal).
Sin memoria latente, sin error de posición, sin recuperación.

## 5. Objetivo y riesgo

\[
J_B=\begin{cases}
V_{\mathrm{nom}}/\mathrm{Vol}(C) & \text{si no hay }\mathtt{geometric\_failure},\\
0 & \text{si hay }\mathtt{geometric\_failure}.
\end{cases}
\]

\(V_{\mathrm{nom}}\): suma de volúmenes **nominales** de ítems aceptados.
`no_candidate` conserva volumen parcial ya aceptado (sin poner \(J_B=0\) salvo que se declare otra regla al congelar).

**Riesgo inmediato** (pose \(p\), margen \(m\), revelados \(G\), ley \(P_\varepsilon\)):

\[
\rho_{\mathrm{imm}}(p,m,G;P_\varepsilon)
=\Pr_{R\sim P(\cdot\mid N)}\!\bigl(\mathrm{geom\_fail}(p,R;C,G)\bigr).
\]

No confundir con existencia de candidatas bajo envelope.

## 6. Independencia del error y layout futuro

La i.i.d. de \(\varepsilon\) elimina inferencia del próximo error, **pero** la pose actual cambia \(G^{\mathrm{rev}}\) y por tanto holguras y \(\rho_{\mathrm{imm}}\) futuros. Eso puede crear dependencia secuencial de **decisiones**, no de **ruido**.
Esa observación **no** demuestra necesidad de RL: una regla determinista con modelo de llegadas o un margen garantista puede capturar el efecto.

## 7. Referencia analítica local (correcta)

Ver rev 06–07. Resumen:

- Fallo por **salida** en eje \(i\): \(\Pr(R_i > C_i-p_i)\) exacto bajo \(P_\varepsilon\).
- Fallo por **solape**: evento sobre el AABB completo; **no** factorizar como producto de ejes independientes sin justificación; usar enumeración en soporte finito o cota \(\Pr(\mathrm{overlap})\le\sum_b\Pr(\mathrm{overlap\ con\ }b)\) (unión).
- Si \(m\) cubre el soporte de \(R\) y la envelope es factible ⇒ \(\rho_{\mathrm{imm}}=0\) (garantía).
- Regla local \(\mathcal{L}\): filtrar \(m\) con pose chooser y \(\rho_{\mathrm{imm}}\le\rho^\star\); minimizar \(\sum m\); desempate por rank del chooser. **Sin sufijo.**

**Trivialidad corregida (rev 07):** calcular \(m_g\) es directo. Optimizar packing seguro futuro **no** queda resuelto automáticamente en todo dominio solo por conocer \(m_g\). Pero si \(m_g\) es admisible, preferirlo (o maximizar utilidad inmediata) ya empata baselines fuertes en el juguete analizado; eso **no** justifica RL. Menor margen garantista admisible bajo \(\rho^\star=0\) **no** es tarea RL.
