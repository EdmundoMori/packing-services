# Campaña científica — packing-services

Documentación de investigación. No es el producto ni un resultado publicable.

## Objetivo provisional

Evaluar si el selector aprendido de colocaciones mejora al heurístico del mismo entorno, o si mantiene calidad comparable a PCT con menor coste. La superioridad y la publicación no están demostradas. Esta carpeta no busca confirmar una conclusión previa.

## Protocolos que no se mezclan

- **Z — homologación con Zhao.** Protocolo del artículo PCT (bin, Uti., Num. y restricciones tal como los defina ese paper). No se copia aquí una definición que no se haya vuelto a leer en el PDF.
- **K — evaluación BED-BPP de Kagerer.** Métricas y empaquetados publicados en ese benchmark (xkpi, ηutil, hn, score). No es Table 1 de Zhao.
- **P — producto packing-services.** `volume_utilization` del execute, heurístico del mismo bucle y holdout de producto.

Un número de un protocolo no decide otro.

## Resultados históricos

Los informes y JSON ya existentes en `online_policy_ml/` son corridas previas. No demuestran superioridad del selector aprendido ni frente al heurístico ni frente a PCT.

## Dónde está el estado

- Estado de la campaña: [`state.json`](state.json).
- Revisiones por paso: [`reviews/`](reviews/).
- Paso 00, primera ejecución: [`reviews/00_inventory.md`](reviews/00_inventory.md) (`inv-00-20261002T122453Z`).
- Paso 00, segunda ejecución: [`reviews/00_inventory_inv-00-20261002T123046Z.md`](reviews/00_inventory_inv-00-20261002T123046Z.md). El registro anterior no se sustituye.
- Paso 01A: [`reviews/01a_export_audit.md`](reviews/01a_export_audit.md). Resultado geométrico: [`results/01a_export_audit_00100408.json`](results/01a_export_audit_00100408.json).
- Paso 01C: [`reviews/01c_internal_geometry.md`](reviews/01c_internal_geometry.md).
- Paso 01E: [`reviews/01e_orientation_contract.md`](reviews/01e_orientation_contract.md). Informe yaw: [`results/01e_yaw_compatibility_00100408.json`](results/01e_yaw_compatibility_00100408.json).
- Paso 02: [`reviews/02_effective_protocol.md`](reviews/02_effective_protocol.md). Exposición de splits: [`results/02_split_exposure.json`](results/02_split_exposure.json).
