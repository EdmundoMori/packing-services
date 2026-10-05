# G2 diseño v2 (borrador) — modelo estocástico propuesto

**Estado:** borrador independiente · **no congelado** · **no ejecutado** · no sustituye `g2_protocol_frozen.*`
**HEAD de referencia:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Precedente:** rev 05 — v1 = escenario determinista de crecimiento conocido (RL trivial bajo garantía).
**Formulación matemática actualizada:** `g2_formulation_v2.md` · **prueba secuencial:** `reviews/06_sequential_decision_check.md`.

---

## 0. Separación de artefactos

| Artefacto | Rol |
|-----------|-----|
| `g2_protocol_frozen.json` + 8 episodios | Históricos: arnés bajo crecimiento determinista |
| Este documento | Propuesta corregida; requiere revisión antes de nuevo freeze |

El preflight **no** valida este problema estocástico.

---

## 1. Modelo aleatorio sencillo (propuesto, no calibrado)

### Generativo

Para cada ítem \(t\), ejes \(i\in\{L,W,H\}\) en mm:

\[
R_{t,i} = \max\bigl(1,\, N_{t,i}\cdot(1+\varepsilon_{t,i})\bigr).
\]

### Ley pública (sensibilidad sintética — **no** calibración BED-BPP)

Propuesta inicial de familia (declarada propia):

- \(\varepsilon_{t,i}\) i.i.d. entre ítems y entre ejes (o i.i.d. entre ítems con \(\varepsilon\) compartido por ejes — elegir **una** y fijarla al congelar).
- Soporte acotado, p. ej. \(\varepsilon\sim\mathrm{Unif}[0,\varepsilon_{\max}]\) **o** \(\varepsilon\sim\mathrm{TruncNormal}\) en \([0,\varepsilon_{\max}]\) con parámetros de sensibilidad.
- Unidades: adimensionales; dims en mm; positividad por el `max(1,·)`.
- \(\varepsilon_{\max}\) y la familia son **parámetros de escenario de sensibilidad**, no estimaciones de campo.

**No** se introduce un parámetro oculto por episodio (θ) para fabricar necesidad de RL.
Con ley i.i.d. conocida, el historial de errores **no informa** el siguiente \(\varepsilon\): un estimador online del próximo error no tiene señal más allá de la ley pública.

### Información

- **Pública:** \(N\), contenedor, revelados, ley \(P_\varepsilon\) (familia + \(\varepsilon_{\max}\) del escenario).
- **No observada antes de actuar:** la realización actual \(R_t\) (ni \(\varepsilon_t\)).
- Tras éxito: revelación exacta de \(R_t\) (idealización de simulador, igual que v1).
- Orientación: permuta el mismo vector \(R_t\).
- Métodos emparejados: mismas realizaciones por ítem.

---

## 2. Qué resuelve cada clase de regla (sin RL)

### Protección por cotas / soporte (garantía)

Si \(\varepsilon\in[0,\varepsilon_{\max}]\) casi seguro, el margen

\[
m_i = \varepsilon_{\max}\, N_i
\]

garantiza \(R_i \le N_i + m_i\) en el marco de catálogo (tras orientación, el envelope cubre \(R\)).
Cualquier pose cuya **envolvente** sea geométricamente factible es segura para todo el soporte.
Elegir el menor margen suficiente bajo garantía es **analítico y trivial** → **no** es un problema RL.

### Protección por cuantiles

Si se admite riesgo inmediato \(\rho\) por colocación, un margen por cuantil

\[
m_i = q_{1-\rho}\,(\varepsilon)\, N_i
\]

(controla, bajo independencia por ejes y modelo de fallo por exceso de envelope, una cota/aprox. de Pr(exceso de envelope); el fallo geométrico real también depende de holguras a pared/cajas).
Sigue siendo una **regla analítica** dada \(P_\varepsilon\) y \(\rho\). No requiere aprendizaje.

### Qué decisión secuencial podría quedar

Bajo i.i.d. conocido, **no** hay inferencia bayesiana del próximo error.
Puede quedar solo:

1. **Compromiso local volumen–riesgo** al elegir \(m\) en un menú cuando el margen de garantía deja `no_candidate` pero un margen menor aún tiene candidatas con riesgo inmediato estimado \(>0\); o
2. **Efectos de layout** (la pose actual cambia holguras futuras) — proxy determinista de holgura libre / score local, no necesariamente RL.

Esas decisiones pueden ser resolubles con:

- menú + umbral de riesgo inmediato analítico,
- o selección greedy de holgura residual,

**sin** RL. Solo si, tras un diagnóstico G2\* bien definido, queda un residual **material e identificable** frente a esos brazos, se plantearía un piloto de aprendizaje — y aun así no se habría demostrado necesidad.

---

## 3. Comparadores y semántica de “riesgo” (corregidos)

### Prohibido

Llamar “riesgo 0/1” a “existen candidatas EP bajo envelope” (error de M3-v1).

### Separar explícitamente

| Concepto | Definición |
|----------|------------|
| Probabilidad inmediata | \(\widehat{\Pr}(\mathrm{geom\_fail}\mid p,\omega,m,G^{\mathrm{rev}},P_\varepsilon)\) si se calcula (aprox. bajo supuestos declarados) |
| Cota conservadora | p. ej. unión / holgura mínima vs soporte de \(R\) |
| Frecuencia empírica | tasa en repeticiones i.i.d. del mismo (pedido, escenario, método) |
| Indicador de garantía por soporte | 1 si envelope cubre todo el soporte de \(R\) orientado y envelope factible |

### Dos regímenes de estudio

**A — Protección garantizada (soporte).**
Comparar métodos bajo margen de garantía hace trivial elegir el menor margen suficiente.
**Recomendación:** cerrar formulación RL en este régimen.

**B — Protección no garantizada (riesgo positivo admitido).**
- Criterio común de riesgo: p. ej. frecuencia empírica de `geometric_failure` a nivel episodio, o media de probabilidad inmediata — **fijar uno** al congelar.
- Unidad de análisis: episodio (pedido × escenario × método × repetición).
- Repeticiones: \(R\ge 5\)–\(10\) por celda si el presupuesto lo permite; con techo ≈120 episodios totales, la precisión de frecuencias es **baja** (p. ej. 10 pedidos × 2 escenarios × 4 métodos × \(R=1\) agota el techo; subir \(R\) obliga a bajar \(N\) o \(S\)).
- Cero fallos en muestra pequeña ≠ seguridad.
- No declarar residual RL por variación post-hoc del “mejor” método por pedido.

### Baseline analítico correcto (sustituto de M3-v1)

Menú \(\mathcal{M}\) de márgenes derivados de \(P_\varepsilon\) (p. ej. {0, cuantil medio, garantía}).
Para cada \(m\), sobre candidatas EP:

1. Calcular **garantía por soporte** o **probabilidad inmediata aproximada** (no existencia de candidatas).
2. Descartar si supera umbral \(\rho\) predeclarado **o** si no hay garantía cuando el régimen es A.
3. Entre admisibles, maximizar score local (p. ej. −rank_key o holgura).
4. Si vacío → `no_candidate` o el de menor riesgo estimado (declarar la regla).

---

## 4. Relación con el preflight v1

| Pregunta | Respuesta |
|----------|-----------|
| ¿El arnés de eventos/J_B/revelación funciona? | Sí (evidencia v1) |
| ¿Hay incertidumbre estocástica validada? | **No** |
| ¿M3-v1 es baseline de riesgo? | **No** — indicador de candidatas |
| ¿Se puede lanzar G2 completo bajo v1? | **No** como diagnóstico de gestión bajo incertidumbre |

---

## 5. Decisión propuesta para la línea

1. Cerrar RL bajo formulación de **protección garantizada / crecimiento conocido** (v1).
2. **`requiere_revision_estocastica_antes_de_G2`**: revisar y eventualmente congelar un protocolo v2 antes de cualquier diagnóstico emparejado estocástico.
3. No entrenar; no reutilizar los 8 episodios v1 como evidencia del problema v2 (contrato de realizaciones distinto).
