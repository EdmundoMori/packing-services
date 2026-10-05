# Revisión 04 — congelación G2 + preflight real

**Fecha:** 2026-10-05
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2` · rama `research/paper-online-packing`
**AGENTS.md:** ausente
**Commit/push:** no
**Entrenamiento / G2 completo:** no

## Precomprobación

Rama y HEAD coinciden con lo esperado. Cambios locales y campañas cerradas conservados. No se abrieron tests reservados de learning_objectives.

## Congelación (antes de packing)

- `sample_manifest.json`: 10 pedidos (5+5), regla determinista por `order_id` ascendente tras exclusiones de exposición/firmas/pools train+test.
  Preflight: `00100030` (euro-pallet), `00100007` (rollcontainer).
  `absolute_independence=false`.
- `g2_protocol_frozen.json` / `.md`: modelo B1, métodos M0–M3, métricas, presupuesto ≤120, preflight 8, hashes.
- Escenario preflight fijado: `sens_mid` (α=0.05, u=7 mm). R=1 ⇒ **frecuencia observada en escenarios**, no Pr(fallo).

## Modelo sintético

`realized = max(1, nominal·(1+α))` mm; escenarios sens_low/mid/high; no calibrado en BED-BPP; no usa 2 cm n-gram. Misma realización por ítem entre métodos; orientación permuta el triplete.

## Métodos

| ID | Definición | Comparación |
|----|------------|-------------|
| M0 | m=0; chooser rank_key | método |
| M1 | m=(u,u,u) | nivel de protección |
| M2 | m_i=α·nominal_i | método |
| M3 | menú {0,u,eje}; riesgo 0/1 factibilidad | método |

Parámetros no retocados tras packing.

## Preflight ejecutado

| Previstos | Ejecutados | Pendientes |
|-----------|------------|------------|
| 8 | 8 | 0 |

Techo: 100 s/episodio, 900 s global. Pared total ≈ **4,4 s**. RSS máx. ≈ **405 MB**. Sin reintentos selectivos. Persistencia atómica. `g2_full_not_launched=true`.

### Resultados operativos (evidencia de arnés, no confirmatorios de oportunidad RL)

| Pedido | Método | Terminación | J_B | wall s |
|--------|--------|-------------|-----|--------|
| 00100030 | M0 | geometric_failure | 0 | 0.42 |
| 00100030 | M1 | geometric_failure | 0 | 0.56 |
| 00100030 | M2 | no_candidate | 0.555 | 0.67 |
| 00100030 | M3 | geometric_failure | 0 | 0.81 |
| 00100007 | M0 | geometric_failure | 0 | 0.006 |
| 00100007 | M1 | geometric_failure | 0 | 0.007 |
| 00100007 | M2 | no_candidate | 0.516 | 0.12 |
| 00100007 | M3 | geometric_failure | 0 | 0.011 |

Emparejamiento de realizados: OK. Verificación independiente: OK (`results/g2_preflight/verify_independent.json`).
`physical_stability_verified=null`. Fallos conservan `failed_attempt` distinto de colocaciones aceptadas.

## Presupuesto G2 completo (estimación incierta)

- Techo: **120** episodios (no ampliado).
- Extrapolación ingenua desde preflight: media ≈0,33 s/ep × 120 ≈ **40 s** pared.
- **Incertidumbre:** pedidos preflight no representan necesariamente tamaños/ocupación/escenarios high; no extrapolar desde G1 sintético; conviene margen operativo (p. ej. timeout 100 s × 120 como cota pesimista de diseño, no predicción).

## Reutilización preflight→G2

Permitida **una vez** solo con coincidencia exacta de contrato/código/métodos/entradas/realizaciones. **No autorizada aún.**

## Decisión

**`preflight_valido_para_revisar_ejecucion_G2`**

El arnés es interpretable y operativamente viable bajo el protocolo congelado.
No se declara necesidad de RL, superioridad de método ni autorización de entrenamiento/G2 completo.
