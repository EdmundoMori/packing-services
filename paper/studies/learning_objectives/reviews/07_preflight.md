# 07 — Preflight reducido de entrenamiento

HEAD: `904038ff7f495510f1b8f3d398da3e4eb281a406`. Sin entrenamiento, desarrollo ni test. Sin commit/push.

## Alcance

Pedidos train del manifiesto (primeros por target): `00105883` (euro-pallet), `00104801` (rollcontainer).
Por pedido: dos primeros estados de la selección por cuantiles; todas las alternativas de S.
Totales: 4 estados, 16 continuaciones. Un intento por continuación.

## Resultado

| Campo | Valor |
| --- | --- |
| status | completed |
| unknown_returns | 0 |
| wall_seconds | 35.121554053999716 |
| ru_maxrss_kb | 399836 |
| greedy_in_all_recorded_supports | true |
| action↔placement del ítem actual | true en 16/16 |
| geometry_valid | true en 16/16 |
| Q_hat recompuesto | coincide |
| training/development/test | false |

La verificación de acción usa el placement del `current_item_id`, no `placements[0]` (incorrecto en estados intermedios).

Los dos pedidos quedan observados como train. Continuaciones reutilizables en campaña futura solo con compatibilidad exacta de contrato y hashes.

## Extrapolación de presupuesto (incertidumbre explícita)

Base: piloto counterfactual (~38 s/pedido etiquetado; ~2.9 s/episodio packing) y este preflight (~17.6 s/pedido con 8 continuaciones). Orden de magnitud bajo 28800 s:

- preflight medido ≪ 900 s
- etiquetado 72 pedidos ≪ 13500 s
- entrenamiento 9 ajustes ≪ 1800 s
- desarrollo ~240 episodios ≪ 3600 s
- test ~1000 episodios ≪ 9000 s

No demuestra el techo; no hay reasignación automática.

## Decisión

**viable_para_autorizar_etiquetado** — no autoriza ni ejecuta etiquetado en este paso.
