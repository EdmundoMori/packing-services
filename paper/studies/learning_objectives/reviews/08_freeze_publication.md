# 08 — Cierre y publicación del freeze learning_objectives

HEAD de ejecución del freeze/preflight: `904038ff7f495510f1b8f3d398da3e4eb281a406`
en `research/paper-online-packing`. Este cierre no ejecuta etiquetas, entrenamiento,
desarrollo, test ni preflight nuevo. No abre los 17 pickle históricos.

## Estado de ejecución

| Elemento | Estado |
| --- | --- |
| Protocolo | congelado (`status=frozen`) |
| Autorizaciones | labeling/training/full_campaign = false |
| Muestra | train 48 / desarrollo 24 / test 100 seleccionados |
| Preflight | completado (2 pedidos train, 4 estados, 16 continuaciones) |
| Etiquetado / entrenamiento / desarrollo / test | no ejecutados |
| Decisión operativa | `viable_para_autorizar_etiquetado` |
| Estabilidad física | `physical_stability_verified=null` |
| Piloto counterfactual | exploratorio; no es resultado de esta campaña |
| Etiquetas anteriores | incompatibles / no comprobadas bajo el contrato único de S |
| Presupuesto | extrapolación informativa; **no demostrado** |

## Digests del protocolo (dos definiciones distintas)

1. **Digest interno del contenido** (campo `sha256` del JSON; no es un hash del archivo completo):
   - Valor: `a5959cb602ee00dfcb56b531de02d6e9d1dd618c42a54b7aa1e0d2214e6ad155`
   - Serialización: tomar el objeto protocolo **sin** la clave `sha256`;
     `json.dumps(..., indent=2, ensure_ascii=False) + "\n"`; SHA256 de esos bytes UTF-8.
   - Recalculado en este cierre: coincide.
   - Este campo resume el contenido congelado; **no** se introduce un segundo campo autorreferencial.

2. **SHA256 de los bytes completos del archivo** `protocol_frozen.json` (incluye la línea `sha256`):
   - Valor: `385f25c60e92dc936c02363b7152031d20b2728db13c2f9d4911446930b83b05`
   - Distinto del digest interno por construcción.

## Manifiesto de muestra

- Archivo: `sample_manifest.json`
- SHA256 de bytes completos: `782eb3abe10163270db8dec9594d099ea936e4491747278bee1b06a73accda62`
- Cadena: `learning-objectives-v1|20261005|{split}|{order_id}`
- IDs únicos; splits disjuntos; cuotas por target verificadas.
- `absolute_independence=false`; límites de procedencia documentados en el manifiesto.
- Test listado para elegibilidad/disyunción/firma; sin análisis de packing/retornos.

## Preflight reauditado desde artefactos

- Pedidos: `00105883`, `00104801` ∈ train.
- 4 estados, 16 continuaciones, 0 retornos desconocidos, 0 fallos.
- Greedy ∈ S; acción alineada con el placement del ítem actual; `Q_hat` = volumen recompuesto de capturas guardadas.
- Hashes de código coherentes con el protocolo.
- Tiempo exacto de pared: `35.121554053999716` s.
- Reutilización futura: las 16 continuaciones cuentan **una sola vez** y esos `35.121554053999716` s entran en el cupo de preflight/etiquetado según el contrato de reuso, sin relanzar el preflight.

## Brazos, contraste y puertas

- Brazos: classification, preferences, return_difference.
- Primario: media por pedido de (preferencias − clasificación) tras semillas emparejadas.
- Puerta de desarrollo: media ≥ 0.005; positiva en ≥2/3 semillas; no negativa por target; evaluación completa; presupuesto restante para test.
- Techo 28800 s: preflight 900 / etiquetado 13500 / entrenamiento 1800 / desarrollo 3600 / test 9000.
- JSON, Markdown y manuscrito alineados en estos puntos.

## Publicación

Commit de cierre del diseño, manuscrito provisional y evidencia de preflight.
No autoriza la campaña completa.
