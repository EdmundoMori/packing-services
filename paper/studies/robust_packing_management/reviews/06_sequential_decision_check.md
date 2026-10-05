# Revisión 06 — prueba de necesidad de decisión secuencial

**Fecha:** 2026-10-05
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2` · `research/paper-online-packing`
**No:** packing BED-BPP, muestreo nuevo, entrenamiento, overwrite freeze/8 episodios, commit/push.

## Precomprobación

Rama/HEAD OK. `AGENTS.md` ausente. Freeze v1 y preflight determinista conservados como histórico.

## Estado previo

V1 = crecimiento determinista conocido (cerrada para RL). M3-v1 ≠ riesgo. V2 = errores i.i.d. con ley pública; historial no infiere el próximo ε.

---

## 1. Riesgo inmediato (definición correcta)

Para pose fija \(p\), margen \(m\) (solo vía la pose que induce el chooser), revelados \(G\) y ley pública \(P_\varepsilon\):

\[
\rho_{\mathrm{imm}}(p;G,P_\varepsilon)=\Pr_R\bigl(\text{salida o solape del AABB realizado en }p\bigr).
\]

- **Salida (por eje):** exacta si se conoce la marginal de \(R_i\): \(\Pr(R_i>C_i-p_i)\).
- **Solape:** no asumir independencia entre separaciones eje-a-eje; en soporte finito, enumerar; si no, cota por unión sobre obstáculos revelados.
- **Garantía por soporte:** si \(R\subseteq E(p,m)\) c.s. y \(E\) factible ⇒ \(\rho_{\mathrm{imm}}=0\).
- **No** es “existen candidatas EP”.

El margen cambia el conjunto de poses admisibles; la seguridad se evalúa en el **realizado**, no en la envelope.

## 2. Referencia analítica local \(\mathcal{L}\)

Menú \(\{m_0=0,\, m_g=\varepsilon_{\mathrm{hi}} N\}\).
Chooser sintético fijo.
\(\mathcal{L}\): admitir \(m\) si hay pose y \(\rho_{\mathrm{imm}}\le\rho^\star\); minimizar \(\sum m\); desempate por rank del chooser.
Sin sufijo, sin modelo de llegadas.

**Trivialidad garantista:** si se exige \(\rho^\star=0\) y \(m_g\) es admisible, \(\mathcal{L}\) elige \(m_g\). Eso **no** es un problema RL.

Formulación: `g2_formulation_v2.md`.

## 3. Ejemplo sintético enumerado

Código: `tools/sequential_necessity_example.py`
Test: `tests/test_sequential_necessity_example.py`
Tiempo: ≪ 60 s (enumeración 2×2 de ε).

| Elemento | Valor |
|----------|--------|
| Ítems | 2 (+ análisis); máx. 3 |
| Contenedor | (10, 8, 5) |
| \(N_1\) | (6, 5, 2) |
| \(N_2\) (solo análisis) | (4.01, 1.5, 2) |
| \(\varepsilon\) | {0, 0.25} masas ½; mismo ε en tres ejes |
| Menú | \(m_0=0\), \(m_g=0.25 N_1\) |
| Poses | RIGHT (4,0,0) vs LEFT (0,0,0) |

Resultados exactos:

| Acción | Pose chooser | \(\rho_{\mathrm{imm}}\) | \(\mathbb{E}[J_B]\) |
|--------|--------------|------------------------|---------------------|
| \(m_0\) | RIGHT | 0.5 | 0.0900375 |
| \(m_g\) | LEFT | 0.0 | 0.13505625 |

- \(\mathcal{L}\) con \(\rho^\star=0.5\) elige \(m_0\) (menor margen).
- Óptimo del menú bajo **supuesto adicional** “el siguiente ítem es \(N_2\) con la misma ley” elige \(m_g\).
- El sufijo **no** entra en \(\mathcal{L}\).

**Límites:** juguete construido; no frecuencia industrial; no novedad; no residual vs *toda* regla determinista — solo vs \(\mathcal{L}\). La política óptima del menú es **determinista** (`siempre \(m_g\)`).

## 4. Alternativas a RL

| Enfoque | Qué hace | Coste / dificultad |
|---------|----------|-------------------|
| Regla analítica local \(\mathcal{L}\) | \(\rho_{\mathrm{imm}}\) + min margen | Barata; ciega al layout futuro |
| Búsqueda limitada bajo modelo de llegadas | 1-paso / horizonte corto con \(P_{\mathrm{arr}}\) declarada | Requiere supuesto de llegadas; sigue siendo planificación, no RL |
| Política aprendida | Aproxima valor/política | Coste de datos, especificación de reward/riesgo, validación |

En el ejemplo, búsqueda/regla “preferir \(m_g\) si admisible” ya alcanza el óptimo del menú.
**Justificación para un piloto RL: insuficiente.** Falta: residual material vs búsqueda limitada y vs garantista en instancias no juguete; novedad frente a márgenes deterministas adaptativos (Wang & Hauser δ); evidencia de que el modelo de llegadas no se puede usar directamente.
Posibilidad de usar RL ≠ necesidad ni superioridad.

## 5. Novedad (matriz existente)

| Capa | Estado |
|------|--------|
| Problema ya estudiado | Trade-off buffer/util (GOPT); margen δ determinista + reducción (Wang & Hauser); robustez de **secuencia** (AR2L); dataset nominal BED-BPP |
| Extensión propuesta | Protección como acción online p=s=1 bajo error dimensional **sintético** i.i.d., score \(J_B\) nominal, vs reglas locales/garantistas |
| No verificado / no afirmar | Novedad por usar BED-BPP; necesidad de RL; superioridad empírica; laguna global de literatura |
| Lagunas de acceso | Partes de Shuai et al. PDF (Cloudflare) ya marcadas en la matriz |

Usar pedidos nominales BED-BPP **no** constituye novedad.

## 6. Decisión

**`pregunta_secuencial_no_trivial_para_revision_de_novedad`**

Motivo: existe al menos un ejemplo sintético enumerable donde \(\mathcal{L}\) es suboptimal respecto a una elección de protección que internaliza consecuencias de layout bajo un modelo de llegadas **declarado**. La pregunta secuencial no es vacía.

**No autoriza** entrenamiento ni G2 completo.
**No** establece justificación de piloto RL (ausente).
Si la revisión de novedad no sostiene una diferencia frente a planificación/márgenes deterministas ya publicados, la línea experimental debe cerrarse sin generar datos.
