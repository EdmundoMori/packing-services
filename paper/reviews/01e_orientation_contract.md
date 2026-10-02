# Paso 01E — Contrato de orientación yaw estricto

**Ejecución:** `01e-20261002T125842Z`
**UTC:** 2026-10-02T12:58:42Z
**Rama:** `research/paper-online-packing`
**Commit de origen:** `75de9ac1546f32f8eeeec0734e66338f3b403ce9`

No hubo inferencia nueva, ni commit, ni push. No se modificó producción. No se sobrescribieron los resultados 01A ni 01C.

## Qué valida el auditor

`audit_internal_solution.py` sigue leyendo las dimensiones orientadas tal como vienen en la captura. Ahora exige, además:

- `flb_mm`, `original_lwh_mm` y `oriented_lwh_mm` son listas de exactamente tres números finitos. Un booleano no cuenta.
- Las dimensiones de entrada y las originales son positivas y coinciden eje a eje. Una permutación entre entrada y original se rechaza.
- La permutación solo se admite al comparar originales con orientadas, y solo si la captura ya autoriza la rotación.
- Los IDs de contenedor duplicados se detectan antes de construir un diccionario. Con datos inválidos no se calculan altura ni volumen de esas cajas.
- Un documento mal formado deja `internal_geometry_valid=false` sin excepción no controlada.

`physical_stability_verified` sigue en null. El auditor no cubre todas las restricciones físicas ni las reglas de los papers. `contrast_historical` se llama ahora comparación de IDs ordenados y FLB (`same_ordered_ids_and_flb`). La igualdad completa del plan es `legacy_actions_equal`, que mira id, dimensiones, orientation y coordenadas.

## Qué conserva el adaptador

`export_yaw_strict.py` solo escribe un plan si el auditor endurecido acepta la geometría, hay un solo contenedor y cada orientación colocada es exactamente `(L,W,H)` o `(W,L,H)`. Conserva el id, las dimensiones originales y el FLB. Si ambas opciones coinciden por simetría, elige 0.

## Qué hace si el yaw no representa la orientación

Enumera todos los IDs incompatibles y rechaza el plan entero. No sustituye dimensiones, no recoloca, no descarta ítems y no escribe un plan parcial. Si se pide `--plan` y la conversión falla, el código de salida es distinto de cero y el archivo no se crea ni se sobrescribe. `--report` puede emitirse solo. Esta versión también rechaza más de un contenedor.

## Resultados observados

La auditoría endurecida de la captura 01C no cambia la conclusión geométrica de 01C: válida, 26/26, altura 1970 mm, volumen 1241041750 mm³, 0 fuera, 0 solapes, estabilidad física null.

El adaptador, sin fijar la cifra de antemano, cuenta 24 orientaciones no representables. `yaw_representable=false` y `yaw_exportable=false` aunque la geometría sea válida. No se escribió un plan yaw.

## Tres cosas distintas

La geometría interna puede ser válida y, a la vez, no ser representable como yaw 0/1. La estabilidad física no está verificada. Nada de esto es una comparación con PCT.

## Límites

Falta el formato canónico que conserve las seis permutaciones. El adaptador estricto no repara el exportador de producción. Un contenedor extra queda fuera de esta versión.
