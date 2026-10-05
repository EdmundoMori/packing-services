# Revisión metodológica de cierre — diseño robust_packing_management

**Fecha local de pasada:** 2026-10-05
**HEAD verificado:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Rama:** `research/paper-online-packing`
**AGENTS.md:** no presente en el repositorio
**Acciones prohibidas respetadas:** sin entrenamiento, sin packing real, sin perturbaciones experimentales, sin commit/push/PR, sin tocar campañas cerradas ni pickle

## Qué problema explícito abordamos

El compromiso entre **protección geométrica** (fiabilidad ante error dimensional/de colocación) y **compactación** medido en volumen **nominal**, en packing **online** con pedidos **BED-BPP**, distinguido de la robustez ante permutaciones de secuencia (AR2L) y de mitigaciones por compliance robótica (Shuai).

Motivación primaria verificada: GOPT §IV-E (buffer fijo vs fallos) y Wang & Hauser (δ conservador).

## Diferencia candidata y novedad sin comprobar

**Candidata:** acción de gestión = nivel de protección; colocación espacial puede permanecer heurística; evaluación bajo riesgo declarado y volumen nominal; baselines de margen fijo, derivado y adaptativo determinista.

**Sin comprobar:** exhaustividad bibliográfica; que RL no colapse a Wang-δ; que Formulación B con revelación sea la correcta frente a A.

## ¿RL tiene función científica necesaria?

**Aún no.** Bajo Formulación A, el margen garantista se calcula sin RL. Bajo B, RL solo es candidato tras demostrar (G2) que baselines deterministas no saturan el frente riesgo–volumen con la misma información. Inventar latentes no observables solo para justificar RL está prohibido; bajo p=s=1 la utilidad secuencial debe anclarse en ocupación + revelación post-intento.

## Reutilización vs faltantes

**Reutilizable:** BED-BPP I/O, target del pedido, extreme-point candidates, GreedyBestFit, orientaciones, captura/contraste/auditoría, runctl/budget patterns, infraestructura PPO (bucles).

**No reutilizar:** contratos/recompensas/pesos de PPO histórico; métricas Zhao/Kagerer como sinónimos; OnlineBPH como PCT; resultados de campañas cerradas.

**Falta:** modelo sintético de incertidumbre, acción de holgura, baselines, ledger propio, preflight (no ejecutado).

## Riesgos metodológicos

1. Colapsar a “margen fijo vs RL” con baseline débil.
2. Confundir incertidumbre de secuencia (AR2L) con geométrica.
3. Contar volumen de márgenes como mercancía.
4. Observar dimensiones reales o el futuro bajo p=s=1.
5. Declarar estabilidad física.
6. Tratar perturbaciones sintéticas como datos BED-BPP reales.
7. Autorizar cómputo por documentación completa.
8. Contagio de escenarios/semillas de estudios cerrados.

## Decisión de esta pasada

**`requiere_corregir_formulacion`**

Motivo: A vs B y el contrato de revelación post-colocación no están cerrados; sin eso G0 no puede pasar a preflight con pregunta científica estable. La novedad provisional es plausible pero no autoriza G1.

Pasos siguientes **no autorizados automáticamente:** cerrar A/B en una nota corta de formulación; solo entonces considerar `listo_para_preflight_sintetico`.
