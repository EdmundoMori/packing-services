# C04 — Corrección de intercepción en franjas EP (motor simplificado)

**Fecha:** 2026-10-06
**HEAD de trabajo (edición):** `59fc0d81b115a274f1b8635335b7ec3668a62289`
**Rama:** `research/paper-online-packing`
**Alcance:** `_support_z` / `_generate_extreme_points`; pruebas; esta revisión.
**No altera:** protocolos/hashes congelados, resultados de campañas cerradas, checkpoints, notebooks; no reevalúa packing real.

**Decisión:** `correccion_proyeccion_lista_para_revision`

## Defecto reproducido

Tras colocar un AABB, la generación consulta franjas de ancho exactamente `EPS`:

- derecha: `[x1, x1+EPS] × [y0, y1]`
- frente: `[x0, x1] × [y1, y1+EPS]`

`_support_z` exigía `overlap_x > EPS` y `overlap_y > EPS`. Para un obstáculo cara-a-cara en el borde de la franja, el solape máximo es `EPS`, así que `> EPS` falla en exacto y, con float, depende del redondeo.

### Caso mínimo observado (código anterior)

Referencia `(10,0,0)+(10,10,7)` → `x1=20`. Obstáculo flush en `x=x1`, techo 5.

| Consulta | ox observado | Resultado previo |
|----------|--------------|------------------|
| Franja EPS, `x1=20.0` | ≈ `1.000000001e-6` > EPS | support **5** (pasa por redondeo) |
| Franja EPS, `x1=0.1+0.3` | ≈ `9.999e-7` < EPS | support **0** |
| Región `[x1,x1+1]` | ≈ 1 | support del techo (contraste; **no** es la corrección) |

## Definición geométrica y comportamiento realmente implementado

**No** es un rayo descendente (−z) desde un origen `(x,y,z0)`.

| Aspecto | Implementación |
|---------|----------------|
| Región | Solo XY: franja de generación de ancho `EPS` (aproximación **explícita** del motor para muestrear el exterior inmediato de la cara; no representa otra entidad publicada) |
| Dirección / altura de origen | Ninguna: no hay proyección paramétrica en z |
| Valor `z★` | `max(bz1)` entre cajas en la lista pasada cuya intersección XY con la franja tiene **área positiva**; si ninguna, `0` |
| Obstáculos | En generación: `placed_before` (todas las ya colocadas **excepto** el ítem nuevo). No hay otro subconjunto espacial |
| Exclusión por encima | **No** se excluyen techos por encima de `z0`/`z1` del ítem nuevo. Una caja alta o “flotante” que cruza la franja XY contribuye su techo |
| Validación | Contención / no solape / peso son posteriores (`_feasible`, `_valid_new_ep`); independientes de `z★` |

Distinciones no intercambiables: cima máxima XY ≠ contacto de caras (`face_contact_area`) ≠ estabilidad física.

**Referencia:** Crainic, Perboli, Tadei (2008), *Extreme Point-Based Heuristics for Three-Dimensional Bin Packing* (CIRRELT-2007-41 / IJOC 20(3)), § Extreme Points y Appendix I (Algorithm 1, seis proyecciones). Este motor es una **simplificación**; C04 no afirma reproducción completa.

## Justificación del umbral (`> 0`)

- Intersección de área positiva ⇔ la huella del obstáculo ocupa interior de la franja.
- Contacto exacto que deja `ox=0` u `oy=0` (cara izquierda terminando en `x1`, arista, esquina) ⇒ área nula ⇒ no intercepta.
- Solape positivo aunque sea `< EPS` ⇒ hay ocupación real de la franja ⇒ debe interceptar.
- `> EPS` era inconsistente con franja de ancho `EPS` (máximo solape flush = `EPS`).
- No se usa `>= EPS`: con float `ox` puede ser `9.99e-7 < EPS` y seguir siendo solape positivo real.
- No se ensancha la franja ni se cambia `EPS` global.

## Corrección

Único cambio de lógica: en `_support_z`, `overlap > EPS` → `overlap > 0`. Docstrings alineados con el comportamiento real (cima máxima XY, no rayo −z). `_compaction._support_z` intacto.

## Pruebas que descartan interpretaciones incorrectas

`tests/test_extreme_point_projection.py`:

| Prueba | Descarta / confirma |
|--------|---------------------|
| flush frágil + contraste región ancha | defecto del umbral `> EPS` |
| solape `< EPS` vs contacto `ox=0` | umbral área positiva |
| obstáculo solo dentro de franja EPS | franja como región de consulta |
| obstáculo bajo | contribuye techo |
| caja alta con `z0` nuevo &lt; techo | **no** es rayo −z desde `z0` |
| caja flotante z∈[40,55] | no se excluye por “estar arriba” |
| varias alturas + aside | max entre interceptores XY |
| traslación XY (mm) | invariancia relativa |
| generación luego `_feasible` | validación independiente |
| `placed_before` vacío | el ítem nuevo no se auto-intercepta |
| `x+EPS==x` a 1e15 | límite numérico documentado; EPS sin cambiar |
| motor 3d + sesión online | regresión sintética |

Ejecutados además: `test_extreme_points_3d`, `test_online_packing`. Sin snapshots alterados.

## Límites numéricos y algorítmicos

- Si `x + EPS == x` en float64 (órdenes ~`1e15` y mayores), la franja tiene ancho 0 y la intercepción degenera. En escalas típicas de mm (`≤ ~1e6`) `x+EPS ≠ x`. **No** se cambia `EPS` para ocultar el límite.
- Una sola `z★` (máximo global en la franja) se aplica al EP de esquina; no hay EP por subsegmento.
- Sin las seis proyecciones de Crainic Algorithm 1.
- Sin estabilidad física.

## Consumidores e impacto histórico

Consumen el packer / sesión: `extreme_points_3d`, `best_fit_decreasing_3d`, `single_container`, `weight_aware_container_loading`, cartonization, `ExtremePointOnlineSession`. Estudios que usaron el generador EP simplificado corrieron bajo el **código anterior**.

Pueden cambiar candidatas cuya `z` dependía de obstáculos con solape de franja ≤ EPS (antes a menudo `z=0`). **No** se atribuye a este defecto el rendimiento de modelos ni campañas previas. **No** se reevaluaron campañas cerradas. Protocolos/hashes intactos.

### Recuperación histórica

Para **reproducir una campaña** hay que usar el **commit y entorno completos** de esa campaña (código, datos, protocolos, semillas, binarios). Inspeccionar o recuperar solo `_extreme_points.py` desde `59fc0d81…` (o el blob pre-C04) sirve para **ver la función anterior**, no garantiza reproducir la campaña.
