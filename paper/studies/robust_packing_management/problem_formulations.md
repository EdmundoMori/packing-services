# Formulaciones — cierre científico (pasada 01)

**Decisión de diseño:** desarrollar **B** como formulación candidata; mantener **A** como baseline conservador y referencia de garantía.
**Alcance de incertidumbre:** **solo dimensiones**. Inactivos: error de posición, deformación, estabilidad física, trayectoria robótica, recovery post-colisión.
**Contrato online:** \(p=s=1\), un contenedor = target propio BED-BPP, secuencia original.
**Instancias:** BED-BPP aporta nominales, secuencia y target. Los errores son **sintéticos**; no están medidos en BED-BPP.
**Revelación:** exacta tras colocación **exitosa** (idealización de simulador, no capacidad robótica demostrada).

No se fuerza RL: si una regla analítica o baseline determinista resuelve el frente riesgo–volumen, se cierra sin entrenar.

---

## Restricciones activas e inactivas

| Restricción | Estado |
|-------------|--------|
| Contención en el contenedor | **Activa** |
| No solape entre ítems | **Activa** |
| Orientaciones explícitas (permutaciones de ejes) | **Activa** |
| Parada al primer ítem sin colocación admisible bajo la regla vigente | **Activa** (con tipología de evento; ver §3) |
| Un solo contenedor del target del pedido | **Activa** |
| \(p=s=1\) (sin preview ni elección entre futuros) | **Activa** |
| Volumen útil = volumen **nominal** de ítems colocados / vol. contenedor | **Activa** |
| Soporte mínimo / fricción / estabilidad de pila | **Inactiva** |
| Peso, fragilidad, reglas de producto | **Inactiva** |
| Accesibilidad / trayectoria / compliance | **Inactiva** |
| Error de posición de colocación | **Inactiva** |
| Deformación de cajas | **Inactiva** |
| Reintento, descarte o recolocación tras fallo geométrico | **Inactiva** |
| Métricas Zhao `Uti.` / Kagerer `xkpi` / `Σalgo` como sinónimos | **Prohibido** |

---

## 1. Qué observa el agente

### Antes de intentar colocar el ítem \(t\)

| Observable | Contenido |
|------------|-----------|
| \(d_t^{\mathrm{nom}}\) | Dimensiones nominales del ítem actual (BED-BPP), en mm |
| \(C\) | Dimensiones del contenedor (target propio) |
| \(G_{t-1}^{\mathrm{rev}}\) | Geometría **revelada** de ítems ya colocados con éxito (AABB con dims realizadas + poses) |
| \(H_{t-1}\) | Historial permitido de errores ya revelados (p. ej. \(\{e_i\}_{i<t}\) o estadísticas derivadas permitidas) |
| \(\mathcal{K}_{\mathrm{pub}}\) | Conocimiento público del modelo generativo que el protocolo declare (familia, cotas, o “θ desconocido”) |
| \(\mathcal{C}_t(m)\) | Candidatas calculadas **solo** con información disponible y protección \(m\) candidata (ver §3) |

### No observa (antes de colocar)

- Dimensiones realizadas del ítem actual \(d_t^{\mathrm{real}}\)
- Errores futuros \(e_{t+1},\ldots\)
- Sufijo de ítems / secuencia restante
- Resultados de acciones alternativas (no hay rollouts retrospectivos ni contrafácticos en el entorno)

### Después de una colocación **exitosa**

1. Se revelan las dimensiones realizadas \(d_t^{\mathrm{real}}\) (revelación **exacta** en el simulador).
2. El estado geométrico pasa a \(G_t^{\mathrm{rev}}\) ocupando el AABB realizado en la pose elegida.
3. El historial se actualiza con el error revelado \(e_t = \mathrm{map}(d_t^{\mathrm{nom}}, d_t^{\mathrm{real}}, \mathrm{orientación})\).

Si la colocación **no** es exitosa (sin candidata bajo \(m\), o violación geométrica tras realizar), no hay revelación “útil” de un ítem colocado: el episodio termina según §3.

**Nota de idealización:** la revelación exacta post-éxito **no** se afirma como sensor robótica real; es un contrato de simulador. Cualquier revelación ruidosa exigiría una nota de cambio **antes** de adoptarla.

---

## 2. Modelo generativo explícito (sin fijar distribución ni niveles)

### Notación y unidades

- Dimensiones en **milímetros** (unidad BED-BPP).
- Para un ítem en orientación canónica de catálogo:
  \(d^{\mathrm{nom}} = (L,W,H) \in \mathbb{R}_{>0}^3\).
- Realización: \(d^{\mathrm{real}} = (L',W',H') \in \mathbb{R}_{>0}^3\).
- **Positividad:** \(L',W',H' > 0\) siempre (rechazo/resampleo en el generador si un sorteo viola positividad; la política no elige ese mecanismo).

### Relación nominal ↔ realizado (forma general)

Definimos un error por eje en el marco del ítem (antes de orientar en el contenedor):

\[
e = (e_L, e_W, e_H), \qquad
d^{\mathrm{real}} = \phi(d^{\mathrm{nom}}, e)
\]

con \(\phi\) monótona por eje en \(e\) y tal que \(d^{\mathrm{real}} \succ 0\).
Ejemplos de forma ( **no elegidos aún** como ley numérica ): aditivo \(L' = L + e_L\), multiplicativo \(L' = L(1+e_L)\), etc. La pasada **no** fija la familia por conveniencia.

### Orientaciones

Una orientación \(\omega\) es una permutación de ejes del ítem.
Sea \(d^{\mathrm{real}}\) el vector realizado **del ítem** (muestreado una vez).
La caja orientada usa \(\Pi_\omega(d^{\mathrm{real}})\).
**Prohibido:** remuestrear \(e\) al cambiar de orientación. Todos los métodos ven el **mismo** \(d^{\mathrm{real}}\) subyacente por ítem y escenario.

### Dependencia (candidatos conceptuales; no fijados)

| Régimen | Ítems | Ejes | Parámetros |
|---------|-------|------|------------|
| B1 | \(e_t\) i.i.d. entre ítems | independientes o con covarianza declarada | Ley **conocida** para la política (\(\mathcal{K}_{\mathrm{pub}}\) incluye \(P\)) |
| B2 | \(e_t \mid \theta\) i.i.d. condicional | idem | \(\theta\) **desconocido** por episodio; prior/familia pública; \(\theta\) inferible vía \(H_{t-1}\) |

### Cuándo se muestrean los errores

- **Antes del episodio (recomendado para igualdad entre métodos):** para cada ítem de la secuencia se fija \(e_t\) (o \(d_t^{\mathrm{real}}\)) del escenario \(k\). Métodos distintos se evalúan en el **mismo** \(\{d_t^{\mathrm{real}}\}_t\).
- La política **no** observa \(d_t^{\mathrm{real}}\) hasta después de un éxito en \(t\).
- No se muestrean errores “al vuelo” de forma distinta por método ni por orientación.

### Comparación B1 vs B2 (necesidad de adaptación)

**B1 (ley conocida, independent errors):**
la protección óptima de un paso suele ser una función de la ocupación observable y de cuantiles/cotas de \(P\). Un baseline **derivado de la distribución** (homologado si \(P\in\mathcal{K}_{\mathrm{pub}}\)) o una regla determinista estado-dependiente puede agotar la oportunidad. La secuencialidad existe (la pose bajo \(m\) cambia el layout futuro), pero **no implica** RL.

**B2 (θ desconocido por episodio):**
añade un estado de creencia. Una adaptación determinista \(\hat\theta(H_{t-1})\mapsto m(\hat\theta, \text{ocupación})\) es el baseline natural. RL solo aportaría si la interacción creencia–ocupación–menú no se reduce a esa tabla/regla.
**No** inventamos un régimen oculto (p. ej. cambios adversarios no declarados de θ a mitad de episodio) solo para justificar RL.

**Evidencia/aplicación que justificaría B2:** lotes con calibración dimensional desconocida pero cuasi-constante (mismo proveedor/turno), donde tras pocas colocaciones el error típico se vuelve estimable — **hipótesis de aplicación**, no dato BED-BPP medido.

**Recomendación de trabajo:** implementar el generativo de forma que admita B1 y B2; el diagnóstico G2 decide si B2 aporta oportunidad más allá de la adaptación determinista. Para el preflight G1 basta un generativo explícito con errores fijados por escenario (compatible con ambos).

### Formulación A (referencia, no candidata principal)

Si existe cota conocida \(\Delta\) con \(d^{\mathrm{real}}\) en un conjunto acotado alrededor del nominal, la protección garantista \(m^\star(\Delta)\) se calcula **directamente**. A permanece como **baseline conservador / referencia de garantía**, no como MDP de aprendizaje.

---

## 3. Acción, transición, fallos (contrato G1)

### Tres eventos (no sinónimos)

| Código | Significado | Terminación | Volumen |
|--------|-------------|-------------|---------|
| `no_candidate` | No hay colocación bajo la protección elegida | **Sí** (early stop) | Conserva \(V_{\mathrm{nom}}\) parcial |
| `envelope_exceeded` | Algún eje de `realized_oriented` supera `envelope` | **No** por sí solo | Si la geometría realizada es válida → **continúa**; se registra el evento; se actualiza con geometría **realizada** |
| `geometric_failure` | Caja realizada **solapa** otra realizada o **sale** del contenedor | **Sí**, sin recovery | No suma el ítem fallido; Obj-B → 0 |

**Obligatorio:** `envelope_exceeded` **≠** `geometric_failure`.
Si hay exceso de reserva **sin** solape ni salida: continuar, revelar realizado, **nunca** modificar retrospectivamente la acción \(m\).

### Vocabulario dimensional (única definición)

En el marco de catálogo del ítem: `nominal`, `realized`, `margin` (mm, ≥0 por eje).
Una orientación \(\omega\) es una permutación de ejes aplicada al **mismo** triplete (sin remuestreo):

- `nominal_oriented = Π_ω(nominal)`
- `margin_oriented = Π_ω(margin)`
- `envelope = nominal_oriented + margin_oriented` (suma por ejes)
- `realized_oriented = Π_ω(realized)`

**Prohibido** el término ambiguo `d_plan` sin calificar.
FLB compartido envolvente/realizado; **no** protección centrada.

### Acción y chooser

Menú \(m\in\mathcal{M}\) (márgenes por eje en mm). Chooser fijo idéntico entre métodos.
El chooser recibe **solo** nominales, margen, contenedor y geometría previamente revelada — **no** el realizado del ítem actual (separación de objetos, no solo omitir un campo).

### Transición tras elegir \(m\)

1. Generar candidatas con AABB \((p,\texttt{envelope})\) vs contenedor y \(G^{\mathrm{rev}}\) (cajas **realizadas** previas).
2. Si no hay candidata → `no_candidate` → fin.
3. Chooser fija \((p,\omega)\); **después** el entorno consulta `realized`.
4. Calcular `envelope_exceeded` (comparación por ejes).
5. Auditar AABB realizado en el mismo \(p\): solape o fuera → `geometric_failure` → fin sin recovery ni otras \(m\).
6. Si geometría válida (con o sin `envelope_exceeded`): éxito → incorporar AABB **realizado** a \(G^{\mathrm{rev}}\) (no la envolvente).

### Certificado geométrico elemental (integridad, no novedad)

Si, para cada colocación, el AABB realizado está contenido en su envolvente planificada (mismo FLB), y las envolventes se validaron sin solape entre sí respecto de la ocupación **relevante en el momento de planificar** y dentro del contenedor, entonces los realizados cumplen contención y no solape respecto de esa misma ocupación.
Con geometría ya revelada: la ocupación relevante son AABB **realizados** previos, no envolventes antiguas. El certificado **no** aplica cuando hubo `envelope_exceeded` (hace falta la auditoría directa del realizado).

---

## 4. Objetivo y riesgo

### Cantidades (siempre reportables)

| Símbolo | Definición |
|---------|------------|
| \(V_{\mathrm{nom}}\) | \(\sum_{i\in\mathrm{Placed}} L_i W_i H_i\) con dims **nominales** |
| \(V_{\mathrm{real}}\) | idem con dims **realizadas** (diagnóstico; no es mercancía de negocio del estudio) |
| \(V_{\mathrm{prot}}\) | volumen artificial \(\sum (d^{\mathrm{env}}-d^{\mathrm{plan}})\) en éxitos — **no cuenta como mercancía** |
| \(U_{\mathrm{nom}}\) | \(V_{\mathrm{nom}} / \mathrm{vol}(C)\) |
| Riesgo | \(\Pr(\texttt{geometric_failure})\) (y tasas de early-stop), estimado en escenarios |

### Dos objetivos posibles

**Obj-A — Volumen nominal acumulado al terminar**
\[
J_A = V_{\mathrm{nom}} \quad \text{(al fin del episodio, incl. si hubo } \texttt{geometric_failure}\text{; el ítem fallido no suma)}.
\]
Incentivo: compactar hasta el fallo; un episodio que “casi llena” y luego falla geométricamente sigue luciendo buen \(J_A\). El riesgo debe mirarse aparte; una penalización en reward **no** convierte esto en restricción garantizada.

**Obj-B — Utilización nominal si el episodio es geométricamente válido**
\[
J_B = \frac{V_{\mathrm{nom}}}{\mathrm{vol}(C)} \cdot \mathbf{1}[\text{no hubo }\texttt{geometric\_failure}],
\quad \text{else } 0.
\]
`envelope_exceeded` sin fallo geométrico **no** anula \(J_B\).
`no_candidate` conserva la utilización parcial.
Se guarda además \(V_{\mathrm{nom}}\) previo al fallo como diagnóstico.
\(J_B\) es resultado de episodio, **no** especificación de reward PPO.

### Recomendación (antes de fijar reward PPO)

Adoptar **Obj-B** como criterio primario de comparación entre métodos bajo un riesgo reportado por separado.
Motivo: alinea el valor del episodio con la ausencia de violación geométrica, coherente con “packing management bajo riesgo”, sin fingir que una penalización lineal impone \(\Pr(\mathrm{fail})\le\rho\).

Aún **no** se fijan coeficientes, umbrales \(\rho\) numéricos ni reward PPO definitivo.

---

## 5. Necesidad de RL y tipo de proceso

### Efectos secuenciales reales

- \(m_t\) cambia \(\mathcal{C}_t(m)\) y, vía el chooser, la pose; el layout revelado futuro cambia.
- Tras revelación, la ocupación usa dims realizadas (el slack de protección no se “solidifica” como mercancía).
- En B2, \(H_{t-1}\) actualiza la creencia sobre \(\theta\).

### ¿MDP o parcialmente observable?

- **B1 + \(\mathcal{K}_{\mathrm{pub}}\) incluye \(P\):** proceso de decisión Markoviano en el estado observable \((G^{\mathrm{rev}}, d^{\mathrm{nom}}_t, H\text{ opcional})\) si \(H\) no aporta (errores i.i.d. conocidos). Llamarlo MDP es lícito.
- **B2 con \(\theta\) latente:** es un **POMDP** / belief-MDP. Llamarlo “MDP” omitiendo \(\theta\) sería una **aproximación**; debe etiquetarse como tal si se entrena solo sobre \(o_t\) sin creencia explícita.

### ¿Basta una regla de un paso?

Si \(m^\star(o_t)\) es una función cerrada (cuantil de \(P\), o \(m(\hat\theta_t, \text{holgura libre})\)) y G2 muestra que satura el frente, **RL no es necesario**.
La existencia de secuencialidad **no** demuestra superioridad de RL.

### Novedad bibliográfica (provisional)

| Afirmación | Estado |
|------------|--------|
| GOPT usa buffer fijo en robot y documenta trade-off (§IV-E, §V) | Verificado |
| Wang & Hauser usan δ y reducción determinista (preprint TRO, robust planning) | Verificado |
| AR2L = incertidumbre de secuencia | Verificado |
| Formulación idéntica: menú de protección + chooser fijo + revelación exacta post-éxito solo dimensional sobre BED-BPP sintético | **No verificada como ya publicada**; no se afirma exclusividad global |

Limitaciones de autores ≠ nuestra extensión: GOPT pide mejorar fiabilidad/compactación (§V) sin formalizar este MDP/POMDP; BED-BPP (§6) pide cerrar sim–realidad sin este contrato sintético.

---

## 6. Papel de A vs B (cierre)

| | A (baseline garantía) | B (candidata) |
|--|----------------------|---------------|
| Uso | Protección calculable desde cotas; referencia | Gestión estocástica + revelación post-éxito |
| RL | No | Solo si G2 deja oportunidad tras baselines |

**Estado tras pasada 01:** formulación B operativa para diseñar G1; RL no autorizado.
