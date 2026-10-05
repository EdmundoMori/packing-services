# Revisión 05 — modelo determinista y auditoría M3

**Fecha:** 2026-10-05
**HEAD:** `74c878e1a7bc7e77a2182d92d72c8a76f39d6de2` · `research/paper-online-packing`
**Alcance:** lectura de código + protocolo + ocho episodios ya guardados.
**No:** packing nuevo, muestreo, entrenamiento, overwrite del freeze, commit/push.

## Precomprobación

Rama y HEAD correctos. Evidencia G1/G2-preflight conservada. `AGENTS.md` ausente.

---

## Tarea 1 — Modelo real (código + protocolo)

### Qué implementa el código

`error_model.expand_nominal`:

\[
R_i = \max\bigl(1,\, N_i\cdot(1+\alpha)\bigr),\qquad i\in\{L,W,H\}.
\]

- `α` fijo por escenario (`sens_mid` ⇒ 0.05), **público** en `PublicErrorModel`.
- Sin muestreo, sin RNG, sin variable aleatoria adicional.
- `MODEL_SEED_NAMESPACE` no interviene en la generación (R=1, mapa determinista).
- Orientación: `realized.permute(order)` — misma realización, sin remuestreo.
- Métodos M0–M3 reciben el mismo `model` / mismos parámetros públicos.

Protocolo congelado (`g2_protocol_frozen.json`, `realization_rule`):
«Determinista dado (order_id, scenario_id, alpha)».

### Qué conoce cada método **antes** de actuar

| Información | ¿Disponible? |
|-------------|--------------|
| Contenedor, nominal actual, geometría revelada | Sí (PolicyObservation) |
| `α`, `u`, familia `R=N(1+α)` | Sí (público, idéntico para todos) |
| Realización del ítem actual como objeto oculto en el arnés | No se pasa a la política |
| Realización **calculable** como `N(1+α)` | **Sí**, por cualquiera que use la ley pública |

Conclusión: el arnés oculta el campo `realized` en la observación, pero la ley hace que ese valor sea **función conocida** de datos públicos. No hay observación parcial genuina.

**Registro obligatorio:**
**`escenario determinista de crecimiento conocido`.**

No es riesgo probabilístico. No es POMDP. No es “incertidumbre dimensional desconocida bajo ley pública”.

El preflight validó el arnés bajo ese escenario determinista; **no** validó un problema estocástico.

---

## Tarea 2 — Auditoría M3 (episodios guardados, sin relanzar)

### Definición real del indicador M3 (código)

```text
risk_hat(m) = 0  si list_envelope_candidates(m) ≠ ∅
            = 1  si no hay candidatas EP bajo la envolvente de m
selección: argmin (risk_hat, sum(m), rank_key)
```

Eso es un **indicador de existencia de candidatas bajo envolvente**, no:

- probabilidad inmediata de fallo,
- cota de riesgo,
- ni “garantía por soporte” del realizado.

Dimensiones que usa el indicador: **nominal + margen del menú** (tamaño de envelope para EP).
**No** usa el realizado (aunque el realizado sea calculable).

### Fallo M3 — pedido `00100030` (ítem `00105990#32`)

| Campo | Valor |
|-------|--------|
| Margen elegido | `(0,0,0)` ≡ brazo m0 del menú |
| FLB / orientación | `(693, 210, 588)`, order `(0,1,2)` |
| Nominal orientado | `(390, 260, 290)` |
| Envelope (m0) | `(390, 260, 290)` |
| Realizado orientado | `(409.5, 273.0, 304.5)` = ×1.05 |
| `envelope_exceeded` | True |
| Fallo geométrico | **solape** con cajas aceptadas #14 y #30 (no pared) |
| `n_candidates` bajo m0 | 18 → indicador marca **0** |
| Criterio de selección | `(0, sum(m)=0, rank)` gana frente a m1/m2 si también tienen candidatas |

Comprobación post-hoc en el mismo FLB (sin re-packing):

- Envelope M2 = `nom·(1+α)` **cubre** el realizado.
- Ese envelope M2 en el **mismo** FLB **no** es factible (solapa ocupación) ⇒ el chooser bajo m2 habría buscado otra pose o `no_candidate`.
- Envelope M1 = nom+7 **no** cubre el realizado (excesos 12.5 / 6.0 / 7.5 mm).

M0/M3 fallan en el mismo ítem/pose: M3 colapsó a M0.

### Fallo M3 — pedido `00100007` (ítem `00104044#4`)

| Campo | Valor |
|-------|--------|
| Margen | `(0,0,0)` |
| FLB / orientación | `(0, 357, 0)`, order `(0,2,1)` |
| Nominal orientado | `(390, 330, 240)` |
| Realizado | `(409.5, 346.5, 252.0)` = ×1.05 |
| Fallo | **salida por pared Y**: `y+W = 703.5 > 700` |
| `n_candidates` | 30 → indicador **0** |

Mismo patrón: M2-env cubriría el realizado pero no es factible en ese FLB; M1 no cubre.

### Clasificación (no excluyente)

| Hipótesis | ¿Aplica? |
|-----------|----------|
| Fallo de implementación del indicador *tal como está documentado en código* | **No** — el código hace lo que dice (existencia de candidatas) |
| Indicador que mide **otra cosa** que “riesgo” | **Sí** — mal llamado “riesgo 0/1” |
| Aceptación deliberada de pose insegura bajo crecimiento **conocido** | **Sí** — elige m=0 sabiendo (vía ley pública) que `R=N(1+α) ⊃ envelope` |
| Ausencia de acción segura bajo el chooser en ese estado | **No demostrable sin re-simular** m1/m2 en ese estado; en el FLB elegido, m2-env no cabe |
| Contradicción indicador↔validador *si el indicador usara el realizado determinista* | **No aplica**: el indicador **no** usa el realizado → no hay contradicción lógica con el validador |

### Relación con tests sintéticos G1

Los tests de certificado (`realized ⊆ envelope` ⇒ sin fallo geométrico si envelope factible) **siguen válidos**.
No hay bug del validador. Hay **desalineación semántica** del baseline M3 respecto a un riesgo geométrico bajo modelo conocido.

### Implicación para RL

El “fallo” de M3 frente a M2 en el preflight **no** es evidencia de oportunidad de aprendizaje. Es un baseline que optimiza volumen de reserva sujeto a factibilidad EP, bajo un crecimiento ya conocido. **No atribuir a RL** un residual causado por ese diseño.

---

## Trivialidad de la formulación v1 para RL

Bajo crecimiento conocido `R=N(1+α)`:

1. Protección **garantizada** por soporte: `m_i = α N_i` (M2) hace `envelope = R` en ejes.
2. Cualquier margen estrictamente menor es **subprotección deliberada**.
3. El problema de “elegir protección” se reduce a usar el margen suficiente mínimo conocido (o aceptar `no_candidate`).

Comparar políticas de aprendizaje contra ese margen es **trivial**: la formulación RL bajo v1 debe **cerrarse** como problema de decisión bajo incertidumbre.

La línea de investigación solo puede continuar tras una **revisión estocástica** (borrador independiente), no reinterpretando el freeze.

---

## Decisión de esta pasada

**`requiere_revision_estocastica_antes_de_G2`**

- Bajo v1 determinista: formulación RL **cerrada por trivialidad** (subcaso).
- Antes de cualquier G2 con sentido para gestión bajo incertidumbre: adoptar (tras revisión) un modelo estocástico en borrador v2; el freeze y los 8 episodios permanecen evidencia de arnés determinista únicamente.

Artefactos nuevos: `g2_design_v2_draft.md` (propuesta, **no ejecutada**).
Freeze original **no** sobrescrito.
