# Borrador de diseño — post corrección de formulación (01)

## 1. Formulación adoptada

- **Candidata:** B — packing online con incertidumbre **dimensional** sintética y **revelación exacta** tras colocación exitosa (`problem_formulations.md`).
- **Referencia:** A — cotas conocidas → protección calculable; baseline conservador de garantía (sin RL).
- **Chooser:** fijo e idéntico en todos los métodos.
- **Acción RL (si G2/G3):** menú pequeño de protecciones geométricas por eje / escalar.

## 2. Contrato (activo)

| Elemento | Valor |
|----------|--------|
| Secuencia | Original BED-BPP |
| Contenedor | Target propio |
| Online | \(p=s=1\) |
| Incertidumbre | Solo dimensiones (sintéticas) |
| Factibilidad activa | Contención + no solape |
| Orientaciones | Explícitas; mismo \(d^{\mathrm{real}}\) bajo permutación |
| Volumen de negocio | Solo nominal; márgenes no son mercancía |
| Objetivo primario propuesto | **Obj-B** (volumen nominal si episodio sin `geometric_failure`; si no, 0) |
| Riesgo | Métrica separada \(\Pr(\texttt{geometric_failure})\) (+ early-stop) |
| Estabilidad / pose error / recovery | Fuera |

Instancias BED-BPP ≠ evaluación sintética propia: los pedidos aportan nominales; los escenarios \(k\) aportan \(\{d^{\mathrm{real}}\}\).

## 3. Baselines suficientes (misma información homologada)

Evaluación en los **mismos** escenarios \(\{d^{\mathrm{real}}_{t,k}\}\).

| ID | Método | Información | Rol |
|----|--------|-------------|-----|
| B0 | Nominal sin protección \(m=0\) | Solo \(o_t\) | Fragilidad |
| B1u | Protección uniforme \(m=\bar m\mathbf{1}\) | \(o_t\); \(\bar m\) razonable documentado (**no** excesivo a propósito) | Baseline |
| B1a | Protección por eje desde **cotas** (estilo A) | \(o_t\) + cotas públicas | Baseline si cotas ∈ \(\mathcal{K}_{\mathrm{pub}}\); si no, **referencia informada** |
| B1d | Protección por eje desde **distribución** (cuantil/función de \(P\)) | \(o_t\) + \(P\) pública | Baseline homologado en B1; si \(P\) no es pública para RL, **oracle/informado** |
| B2h | Adaptación determinista al historial \(\hat\theta(H)\mapsto m\) | \(o_t\) incl. \(H\) | Baseline natural en B2 |
| RL | Menú \(\mathcal{M}\) + misma info que el brazo homologado | Idem al comparable | Solo candidato post-G2 |

**Criterio común de riesgo:** reportar \(J_B\) (o curva) a tasa de `geometric_failure` comparable, o frentes (riesgo, \(J_B\), early-stop).
**Prohibido:** comparación principal RL vs uniforme deliberadamente enorme.
**Oracle:** cualquier método con conocimiento extra del generativo se etiqueta y no cuenta como baseline homologado.

## 4. Criterio para descartar RL antes de entrenar

`descartar_rl_por_no_ser_necesario` si:

- el frente de B1a/B1d/B2h domina o iguala (dentro de tolerancia G2) a cualquier menú exhaustivo pequeño sobre \(\mathcal{M}\); o
- la acción óptima en \(\mathcal{M}\) es constante / regla cerrada trivial del observable; o
- solo A-garantía es el objetivo adoptado.

## 5. Qué podría aportar RL (sin demostrar)

Explorar dependencias no lineales ocupación–creencia–menú cuando el diagnóstico G2 muestre residual tras B1d/B2h.
**No demostrado:** que ese residual exista; que PPO lo cierre; novedad de publicación.

## 6. Implementación (aún no autorizada)

Herramientas nuevas bajo el estudio cuando se autorice G1; no modificar `src/` sin necesidad demostrada; no cargar pickle/checkpoints; no packing BED-BPP real en G1 (solo sintético mínimo).
