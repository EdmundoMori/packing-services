# G2 — diseño (sin congelar IDs, sin ejecutar packing)

**Estado:** diseño listo para congelar y preflight real · **no ejecutado** · **no emite muestra**
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`

Pregunta de G2: ¿queda oportunidad de gestión adaptativa **después** de reglas analíticas/deterministas pertinentes, o conviene `descartar_rl_por_no_ser_necesario`?

G2 **no** está diseñado para demostrar que RL es necesario.

---

## 1. Baseline analítico propuesto

### Entradas (misma información que un brazo homologado)

- Contenedor \(C\); nominal del ítem; margen candidato o menú pequeño \(\mathcal{M}\)
- Geometría revelada \(G^{\mathrm{rev}}\)
- Ley o cotas **públicas** del error (B1): denotadas \(P\) o \(\Delta\)

### Clearance de una pose \((p,\omega)\)

Para cada eje \(i\in\{x,y,z\}\):

- Holgura a pared: \(g^{\mathrm{wall}}_i = C_i - p_i - \texttt{nominal\_oriented}_i\)
- Holgura a obstáculo revelado en dirección \(+i\): distancia desde \(p_i+\texttt{nominal\_oriented}_i\) hasta el inicio del siguiente AABB revelado que intersecte la “columna” ortogonal (o \(+\infty\) si no hay)

La realización orientada \(R_i\) provoca:

- **salida** si \(R_i > C_i-p_i\)
- **solape** (si hay obstáculo a distancia \(d_i\) en +) si \(R_i > d_i\) de forma compatible en los tres ejes (conservador: usar min holgura crítica)

### Riesgos distinguidos

| Tipo | Definición | Calculable 1 paso? |
|------|------------|---------------------|
| Riesgo inmediato de colocación | \(\Pr(\texttt{geometric\_failure}\mid p,\omega,m,G,P)\) | Aprox. sí bajo B1 e independencia por ejes **declarada**; solape EP raro ⇒ énfasis en paredes |
| Riesgo acumulado de episodio | \(\Pr(\exists t:\mathrm{fail}_t)\) | **No** es \(1-\prod(1-\rho_t)\) sin independencia; si se usa unión \(\le\sum\rho_t\), es **cota conservadora** |
| Consecuencia futura | Holgura/m pose cambia layout y holguras posteriores | No se reduce a 1 paso; baselines deterministas de holgura libre intentan proxy |

### Regla local analítica (baseline obligatorio en G2)

Para el ítem actual, sobre un menú finito \(\mathcal{M}\) y candidatas EP bajo cada \(m\):

1. Descartar pares \((m,\mathrm{cand})\) con riesgo inmediato estimado \(>\rho_{\mathrm{local}}\) (umbral de sensibilidad documentado, no calibrado post-hoc sobre resultados).
2. Entre los restantes, maximizar un score local (p. ej. \(-\)rank_key, o holgura residual esperada).
3. Si el conjunto queda vacío → elegir el de menor riesgo inmediato (o `no_candidate` si ninguno es factible bajo \(m\)).

**No** se limita la comparación a márgenes fijos débiles: el brazo analítico local es el comparador principal frente a cualquier futuro RL.

Cotas/distribución → margen por eje fijo: baseline `B1a`/`B1d` (cuantil o \(\Delta\)).
B2 (θ latente) **no** se adopta en G2 inicial (ver §2).

---

## 2. Modelo de error recomendado

### Qué permiten las fuentes ya registradas

| Fuente | Dato / supuesto | ¿Magnitudes medibles para BED-BPP? |
|--------|-----------------|-------------------------------------|
| GOPT §IV-E | Buffer de **0,7 cm** en robot; trade-off util./fallos | Supuesto/ingeniería de su testbed, **no** ley sobre BED-BPP |
| BED-BPP §3 | Tolerancia **2 cm** en n-gram (redondeo) | Criterio de análisis de variedad, **no** error de caja medido |
| Wang & Hauser | \(\delta\approx 1\) cm en experimentos | Holgura de planificación; no distribución BED-BPP |
| Shuai | Incertidumbres cualitativas de percepción/ejecución | Sin familia numérica reutilizable aquí |
| AR2L | Secuencia adversaria | Otra clase de incertidumbre |

**Conclusión:** no hay evidencia primaria para una distribución dimensional medida en BED-BPP ni para correlaciones ítem–ítem. Los números literarios son **escenarios de sensibilidad / ingeniería**, no “errores reales del dataset”.

### Recomendación inicial: **B1 simple**

- Errores **independientes entre ítems** (declarado).
- Por eje: familia aditiva o multiplicativa con parámetros **públicos** en un **juego pequeño de sensibilidades** (p. ej. tres niveles etiquetados `eps_low/mid/high`), documentados como escenarios sintéticos, no como verdad industrial.
- Mismo vector de realizados por ítem entre métodos (fijado al crear el escenario, antes de ver métricas de métodos).
- Orientación = permutación del mismo realizado.

**No B2** en G2 inicial: no hay justificación empírica de que errores previos informen los siguientes en BED-BPP; introducir θ latente solo crearía memoria artificial para RL. Si en el futuro se adopta B2, será obligatorio un baseline estimador determinista \(\hat\theta\to m\) con la misma info.

---

## 3. Diseño emparejado (máx. 10 pedidos) — **sin emitir IDs**

### Tamaño

- **≤ 10 pedidos de desarrollo:** 5 `euro-pallet` + 5 `rollcontainer`.
- Test de estudios anteriores: **cerrado** (no se toca `full.test` / holdout de learning_objectives).

### Exposiciones e independencia

Fuentes a consultar al congelar (pasada futura de emisión):

- `paper/studies/learning_objectives/sample_manifest.json` (train/dev/test; `absolute_independence: false`; firmas bloqueadas; remaining val reportado)
- `paper/studies/rl_rule_selection/exposure_audit.json` (`absolute_independence: false`)
- `paper/studies/counterfactual_ranking/.../exposure_registry.json` y manifiestos afines
- Resultados/pilotos en `paper/results/*exposure*`

**Regla determinista prevista (aún no aplicada a IDs):**

1. Pool = pedidos val BED-BPP del target, con firma de clon calculable.
2. Excluir IDs con exposición registrada en manifiestos/registros anteriores **y** firmas en conjuntos bloqueados.
3. Ordenar IDs restantes por `order_id` ascendente.
4. Tomar los primeros 5 por target.
5. Documentar que **ausencia de exposición registrada ≠ independencia absoluta** (`absolute_independence: false` en auditorías previas).

**Esta pasada no emite la lista de IDs ni ejecuta pedidos.**

### Métodos mínimos (emparejados)

| ID | Método |
|----|--------|
| M0 | Nominal sin protección |
| M1 | Margen uniforme suministrado (nivel de sensibilidad, no optimizado post-hoc) |
| M2 | Protección por eje desde cotas/cuantil público (B1a/B1d) |
| M3 | Selección local analítica (§1) |
| M4 | Adaptación al historial | **Omitido** en G2 inicial (B2 no adoptado) |

Todos: misma secuencia, mismo chooser base cuando aplique, misma info pública, mismas realizaciones por ítem.

### Escenarios / repeticiones / cómputo de episodios

- \(S = 3\) escenarios de sensibilidad de error (bajo/medio/alto), **fijos a priori**.
- \(R = 1\) realización por escenario y pedido (determinista dado seed de escenario); no confundir con “pedidos independientes”.
- Métodos \(M = 4\) (M0–M3).
- Pedidos \(N \le 10\).

**Máximo de episodios G2:** \(N \times S \times M \le 10 \times 3 \times 4 = 120\) episodios de packing.
Cada episodio = un pedido × un escenario × un método.

---

## 4. Métricas y puerta G2

### Métricas

- \(J_B\) (0 si `geometric_failure`)
- Frecuencia de `geometric_failure` por episodio
- \(V_{\mathrm{nom}}\) parcial previo al fallo (secundario)
- Tasas `no_candidate`, `envelope_exceeded` (exceso **sin** fallo ≠ fallo)
- Tiempo pared por episodio / total
- Desglose por target y por escenario de sensibilidad

Cero fallos en muestra pequeña **≠** riesgo cero.

### Puerta (cualitativa; umbrales numéricos solo con interpretación práctica al congelar)

1. **Integridad:** arnés, revelación, mismos realizados, sin filtración (extiende G1 a preflight real).
2. **Compromiso observable** riesgo–volumen entre M0/M1/M2 (no trivialmente plano).
3. **Oportunidad adicional:** M3 no deja residual material frente a un hipotético menú exhaustivo pequeño / no justifica RL si empata con M2/M3.
4. **Coste** dentro del techo de presupuesto.

**Cerrar RL (`descartar_rl_por_no_ser_necesario`) si:** empate relevante de M2/M3 con el mejor del menú; M0 domina bajo los escenarios; o no hay compromiso riesgo–volumen.
**No** usar oracle con futuro conocido como prueba de aprendibilidad.
**No** elegir márgenes retrospectivos por pedido.

G2 positivo solo autoriza **diseñar** un piloto G3, no demuestra aprendizaje ni publicabilidad.

---

## 5. Presupuesto propuesto (estimaciones)

| Fase | Techo propuesto | Nota |
|------|-----------------|------|
| Preflight real pequeño | estimación **≤ 15 min** pared; 1–2 pedidos × 1 escenario × 2 métodos | **No** extrapolar 0,006 s sintéticos |
| G2 completo | estimación **≤ 90 min** pared laptop 16 GB; timeout por episodio **estimación 120 s** | Medir al ejecutar; incompleto si se corta |
| Persistencia | JSON por episodio; reanudación sin reescribir éxitos; no reordenar selectivamente fallidos | |

Todas las cifras de tiempo son **estimaciones** hasta medición.

### Tests sintéticos añadidos (solo los justificados por §1)

Ver `tests/test_g2_reachability_audit.py`: cáscara abstracta solape; margen provoca `no_candidate` con realización válida a margen 0.

---

## 6. Decisión de esta pasada

**`listo_para_congelar_G2_y_preflight_real`**

Siguiente paso autorizado solo tras revisión explícita: congelar IDs con la regla §3 y preflight real.
No entrena, no muestrea errores de pedidos, no packing masivo en esta pasada.
