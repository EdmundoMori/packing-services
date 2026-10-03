# 17 — calibración del selector compacto

Congelado antes de empaquetar, sobre `91ee3ed10cb028881c2d0823239c3203759b429d`. No modifica el protocolo 16 ni sus resultados.

La fórmula es `contacto_normalizado - a * incremento_altura_normalizado - b * techo_normalizado + c * apoyo`, versión `compact_contact_height_v1`. El contacto sale de `-rank_key[0]` y no es una prueba de estabilidad. La cuadrícula tiene 32 configuraciones en orden lexicográfico. No se amplía después de ver resultados.

Train usa los 40 IDs ya guardados en el protocolo 16, primero los euro-pallet y después los rollcontainer, en el orden de cada lista. Desarrollo usa los 50 `execution_items` del protocolo 10, en ese orden.

La selección de train conserva los fallos en el denominador. Las tres primeras pasan a los 50 pedidos. La puerta A/B/C se aplica solo a la configuración elegida entre esas tres. No es una prueba estadística ni una comparación con OnlineBPH o PCT.

Presupuesto estimado antes de ejecutar: media de pared del smoke Greedy por 1520 casos, y también el máximo de esos cinco. La incertidumbre queda en el JSON. `physical_stability_verified` permanece null.
