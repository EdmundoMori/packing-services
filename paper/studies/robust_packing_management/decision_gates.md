# Puertas — post congelación G2 + preflight real

Laptop: 16 GB RAM, CPU. Tiempos de preflight **medidos** (≈4,4 s pared total).
Terminar documentación **no** autoriza G2 completo ni RL.

## G0 — Novedad y formulación

Sin cambio: formulación B operativa; novedad de publicación no establecida.

## G1 — Preflight sintético

**Estado:** ejecutado · `integridad_sintetica_verificada_para_disenar_G2`.

## Decisión final (rev 07)

**`cerrar_linea_por_justificacion_insuficiente`**

Sin nueva inversión experimental. Ver `reviews/07_final_novelty_and_go_no_go.md`.
Manuscrito = formulación / evaluación preliminar (no envío). Campañas previas conservadas.

## Decisión de rev 06 (corregida por rev 07)

**`pregunta_secuencial_no_trivial_para_revision_de_novedad`** — sobre-interpretaba insuficiencia de \(\mathcal{L}\) con \(\rho^\star=0.5\).
Tras baselines fuertes (prefer-\(m_g\), max \(U_{\mathrm{imm}}\), búsqueda limitada): residual **0**.

Existe un juguete enumerable donde la regla local \(\mathcal{L}\) es suboptimal
frente a elegir \(m_g\) bajo un supuesto de llegada declarado.
**Piloto RL: no justificado.** No autoriza G2 completo ni entrenamiento.
Siguiente filtro: novedad vs planificación/márgenes deterministas; si falla → cerrar sin datos.

Ver `reviews/06_sequential_decision_check.md`, `g2_formulation_v2.md`.

## G2 — Diagnóstico (v1 congelado histórico; revisión estocástica / novedad pendiente)

**Protocolo v1:** `g2_protocol_frozen.json` — **escenario determinista de crecimiento conocido** (`R=N(1+α)`, α público).
**Preflight v1:** 8 episodios — evidencia de arnés, **no** del problema estocástico.
**Auditoría:** `reviews/05_deterministic_model_and_m3_audit.md`
**Borrador corregido:** `g2_design_v2_draft.md`, `g2_formulation_v2.md` (no ejecutado, no congelado).

### Decisión previa (rev 05)

**`requiere_revision_estocastica_antes_de_G2`** — bajo v1/garantía, RL cerrada por trivialidad.

### Qué puede concluir G2 (recordatorio)

1. arnés inválido
2. sensibilidad insuficiente / diseño no informativo
3. baseline analítico suficiente en el alcance examinado
4. compromiso riesgo–volumen que justifica **diseñar** diagnóstico adicional de selección adaptativa (no entrena)

### Métodos congelados

M0 nominal · M1 uniforme (nivel de protección) · M2 eje α·nominal · M3 menú local.
M1 es comparación de **nivel de protección** dentro del escenario; M0/M2/M3 son métodos.

### Riesgo

Con R=1: **frecuencia observada en escenarios**, no calibración probabilística. 0 fallos ≠ garantía. No se usa 2 cm n-gram BED-BPP.

### Presupuesto

- Techo: **120** episodios (10×3×4); no ampliado.
- Preflight medido ≈4,4 s; extrapolación ingenua ≈40 s para 120 — **incierta**.
- Timeout diseño: 100 s/episodio; no tratarlo como predicción media.

### Reutilización preflight

Solo si coincidencia exacta de contrato/código/métodos/entradas/realizaciones. No autorizada aún.

## G3 / G4

Sin cambio: solo si G2 deja residual material y se autoriza explícitamente.

## Presupuesto de cupos

diseño · G1 sintético · **preflight G2 (hecho)** · G2 diagnóstico (pendiente de revisión) · G3 piloto · G4 test reservado.
