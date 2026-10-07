# R06 — Preparación estática de la campaña BED-BPP-RL

## Verificación comunicada
Seis pruebas unitarias correctas.
Dataset, selector, pool y fuentes de exclusión contrastados.
Muestra: 16 pedidos train y 8 evaluation.
24 firmas reconstruidas desde metadatos.
Selección determinista reproducida.
42 fuentes; unión de 8744 IDs excluidos.
Inventario de implementación: 210 archivos hasheados.

## Entorno observado
Torch 2.14.0+cpu; NumPy 2.2.6; Pydantic 2.13.4.
Estas versiones observadas no constituyen un entorno bloqueado reproducible.

## Borrador
resource_campaign_protocol_draft.json:
SHA256 026d55a70f6452d761389451d4c9d25cee3d0cf221f1472da7b67bb61e11b59f.

## Alcance
Sin generación de candidatas, packing ni entrenamiento.
El tiempo de comprobación de metadatos no estima el coste experimental.
Protocolo no congelado; ejecución industrial no autorizada.
El inventario deberá actualizarse después de implementar los adaptadores,
conservando este borrador como registro de preparación.

## Decisión
Preparación estática verificada contra el dataset local.
Continuar con implementación y pruebas sintéticas de adaptadores industriales.
