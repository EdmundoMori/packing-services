# Cierre de campaña — robust_packing_management

**Decisión:** `cerrar_linea_por_justificacion_insuficiente`
**HEAD al cierre:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2`
**Rama:** `research/paper-online-packing`
**Fecha:** 2026-10-05

## Objetivo original

Evaluar si una política de gestión puede seleccionar protección geométrica en packing online de pedidos **nominales** BED-BPP bajo incertidumbre dimensional **sintética**, reteniendo más volumen nominal que márgenes fijos bajo un criterio común de fallo geométrico — y si ello justificaría un piloto de RL frente a baselines analíticas.

## Qué se implementó y verificó

| Pieza | Estado |
|-------|--------|
| Formulación B (revelación post-éxito) + A garantista | Documentada |
| Contrato G1 (eventos, J_B, separación info, tests) | Verificado sintético |
| Diseño G2 + freeze v1 + manifiesto ≤10 pedidos | Congelado |
| Preflight real 8 episodios (crecimiento **determinista** conocido) | Ejecutado (arnés) |
| Auditoría: v1 no es estocástico; M3 ≠ riesgo | Verificado |
| Borrador estocástico v2 | **Propuesto, no evaluado** |
| Ejemplo sintético enumerable + corrección vs baselines fuertes | Verificado |
| Revisión de novedad (fuentes primarias) | Completada |
| Entrenamiento RL / G2 completo (≤120) | **No ejecutados** |

## Preflight determinista (8 episodios)

Pedidos `00100030`, `00100007` × métodos M0–M3 × escenario `sens_mid`.
Modelo: `R = N(1+α)` con α público → **escenario determinista de crecimiento conocido**.
Alcance: evidencia **operativa del arnés** (eventos, persistencia, emparejamiento).
**No** es diagnóstico de incertidumbre estocástica ni resultado de superioridad de métodos. Freeze y JSON de episodio se conservan byte a byte como histórico.

## Modelo estocástico propuesto (no evaluado)

`R = N(1+ε)` con ley pública i.i.d. (borradores `g2_design_v2_draft.md`, `g2_formulation_v2.md`).
No congelado como protocolo ejecutable; no muestreado; no usado para packing BED-BPP adicional.

## Ejemplo sintético y corrección

Un juguete de 2 ítems mostró que una regla local débil (\(\rho^\star=0.5\) + min margen) es suboptimal.
Corrección (rev 07): preferir protección garantista, maximizar utilidad inmediata y búsqueda limitada empatan el óptimo del menú (residual 0). Chooser sintético ≠ motor EP de producción. No justifica RL.

## Antecedentes y lagunas

Verificados: Wang & Hauser (δ adaptativo), GOPT §IV-E (buffer fijo), AR2L (secuencia), trabajos de drift/estabilidad.
BED-BPP no aporta ley empírica de error dimensional.
Lagunas de acceso (p. ej. PDF completo Shuai) marcadas como no verificadas; no se afirma exhaustividad global.

## Decisión

**`cerrar_linea_por_justificacion_insuficiente`**

- No hay evidencia suficiente de una contribución nueva distinguible.
- No se demuestra inferioridad universal ni inutilidad de RL en abstracto.
- No se evaluó ninguna política RL nueva en este estudio.
- BED-BPP no contiene una ley empírica de error dimensional.
- No se autoriza G2 completo ni entrenamiento.

Este documento y el manuscrito asociado son **formulación y evaluación preliminar archivada**, no un artículo listo para envío. Campañas anteriores permanecen cerradas e intactas.
