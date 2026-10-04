# Matriz de antecedentes

La pregunta de este borrador es si una política elige, entre tres reglas geométricas que comparten las mismas candidatas, mejor que cada regla fija. La tabla registra fuentes y diferencias. No afirma prioridad temporal.

| Fuente | Qué se consultó | Qué hace | Diferencia con esta propuesta |
| --- | --- | --- | --- |
| Verma, Singhal, Khadilkar, Basumatary, Nayak, Singh, Kumar y Sinha, arXiv:2007.00463, PackMan | HTML del preprint | Genera ubicaciones y orientaciones factibles y un método de valor elige entre ellas. Menciona selección de heurísticas en bin packing offline de una dimensión, con citas no resueltas en el HTML (`?`). | La acción elige una candidata geométrica, no una de tres reglas fijas sobre la misma lista de puntos extremos. El estado incluye una vista de alturas y contenedores futuros de capacidad. |
| Yang, Song, Chu, Song, Cheng, Li y Zhang, IEEE T-ASE, vol. 21, pp. 939–950, documento 10018146, “Heuristics Integrated Deep Reinforcement Learning for Online 3D Bin Packing” | La ficha IEEE y el resumen visible en la búsqueda. El PDF no se abrió. La lista de autores coincide con la referencia 13 del HTML de Wong, Tsai y Ou. | El resumen describe tres familias heurísticas —física, empaquetado y desempaquetado— integradas en un pipeline de DRL. | Integran heurísticas dentro del pipeline. Esta propuesta mantiene tres acciones aunque propongan la misma geometría. |
| Wong, Tsai y Ou, Sensors 2024, 24, 5370, HHPPO, https://doi.org/10.3390/s24165370 | HTML de MDPI | Ordenan puntos extremos por espacio desperdiciado, usan una rejilla 3D y soporte parcial, y rediseñan recompensa y espacio de acción de PPO. | La heurística entra en la construcción de la acción y de la recompensa. Aquí la recompensa es solo volumen colocado sobre volumen del contenedor, con gamma 1. |
| Zhao, Pan, Yu y Xu, 2023, arXiv:2212.02094, “Learning Physically Realizable Skills for Online Packing of General 3D Shapes” | Texto del PDF | Empaqueta formas irregulares: genera candidatas y una política elige una colocación. Cita a Hu (TAP-Net), Duan 2019, Zhao 2021 y Zhao 2022a. | El objeto no es un ortoedro de BED-BPP y la acción no es una de tres reglas geométricas de este contrato. |

## Fuentes citadas y no abiertas

Estos trabajos aparecen en Zhao, Pan, Yu y Xu (arXiv:2212.02094) o en el resumen de Yang. Sus PDF no se abrieron en este paso:

- Hu, TAP-Net, 2017/2020: la cita describe selección del orden y colocación heurística.
- Duan et al., 2019: la cita describe selección del orden.
- Zhao, She, Zhu, Yang y Xu, 2021, “Online 3D Bin Packing with Constrained Deep Reinforcement Learning”: el título aparece en la bibliografía de Zhao, Pan, Yu y Xu. El PDF no se abrió. La heurística OnlineBPH de este repositorio no es esa política.
- Zhao, Yu y Xu, 2022a, “Learning Efficient Online 3D Bin Packing on Packing Configuration Trees”: el título aparece en la bibliografía de Zhao, Pan, Yu y Xu. El PDF no se abrió. Ese trabajo es el PCT citado; la heurística OnlineBPH de este repositorio no es esa política.

PackMan también alude, sin resolver la cita en el HTML, a clasificadores que eligen una heurística en bin packing de una dimensión. Esas fuentes no se abrieron.

## OnlineBPH

El adaptador de este repositorio ejecuta la heurística OnlineBPH: espacios máximos vacíos ordenados por `(z, y, x)` y la primera de seis orientaciones que acepta la colocación virtual. El contrato de captura de ese baseline ya se comprobó en el paso 16A. Esa heurística no es un PCT aprendido, no es la Tabla 1 de Zhao y no sustituye a las tres reglas de puntos extremos de este estudio.
