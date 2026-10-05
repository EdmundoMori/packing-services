# 22 — Evaluación development completa (reuso smoke)

## Hotfix de geometría
Solo cambió la lectura post-captura: `internal_geometry_valid` (clave real del
auditor) en lugar de `geometry_valid` (ausente). `U_geom` desde `recompute_u`.
No alteró captura, candidatas, dimensiones, política ni puntuación. Smoke
compatible.

## Ejecución
- HEAD `ee9e0ec`; run_id `dev_full_ee9e0ec854c3_20261005T174540Z`
- 8 reutilizadas (`dev_smoke_ee9e0ec854c3_20261005T173933Z`) + 232 nuevas
- prior wall = 45.43316340446472 s; esta corrida ≈ 697.39 s
- cupo restante ≈ 2857.17 s; restante campaña→test ≈ 25828 s

## Puerta (congelada)
1. media pref−class ≥0.005 → **no** (−0.0081)
2. ≥2 semillas positivas → **no** (solo seed 23)
3. agregado ≥0 por target → **no** (euro-pallet −0.030)
4. completa y auditada → **sí**
5. presupuesto test → **sí**

Decisión: **`no_avanzar_con_esta_configuracion`**
Desventaja vs Greedy destacada en ambos brazos aprendidos.
Test no ejecutado.
