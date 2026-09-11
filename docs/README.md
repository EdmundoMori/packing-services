# Documentación Técnica

Este documento sirve como índice para la documentación técnica del proyecto **packing-services**.

## Prerrequisito de Lectura

Antes de consultar esta documentación técnica, se recomienda leer el documento principal [`../README.md`](../README.md), que presenta:

- El objetivo del proyecto
- Las prioridades de desarrollo
- El estado actual del sistema
- Las instrucciones de instalación y ejecución

## Objetivo del Proyecto

El objetivo de **packing-services** es comparar metodologías de *Cutting and Packing* bajo condiciones homogéneas:

- **Misma entrada:** formato de datos unificado para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo.
- **Mismas métricas:** indicadores de rendimiento calculados uniformemente.

El sistema soporta tanto el modo `packing_mode=offline` (pedido completo conocido de antemano) como `packing_mode=online` (ítems que llegan en secuencia).

---

## Orden de Lectura Recomendado

La documentación está organizada de forma progresiva. Se recomienda seguir este orden:

1. **[`../README.md`](../README.md)** — Visión general, objetivo y mapa del proyecto.

2. **[`roadmap.md`](roadmap.md)** — Estado de las prioridades del proyecto. Los objetivos 1–3 (homogeneización, benchmark, packing online) están operativos. El siguiente paso es la mejora de calidad (§4). El espacio de datos está despriorizado (§5).

3. **[`architecture.md`](architecture.md)** — Arquitectura del sistema: capas de software, flujos de datos y descripción del módulo `online/`.

4. **[`algorithm_catalog.md`](algorithm_catalog.md)** — Inventario completo de los 52 algoritmos disponibles: 31 implementados, 6 adaptadores y 15 futuros.

5. **[`api_examples.md`](api_examples.md)** — Ejemplos prácticos de uso de la API REST: contratos HTTP, comandos curl y formatos de entrada/salida.

6. **[`algorithm_implementation_traceability.md`](algorithm_implementation_traceability.md)** — Guía paso a paso para implementar y registrar nuevos algoritmos.

7. **[`external_adapters.md`](external_adapters.md)** — Documentación sobre la integración con motores de empaquetado externos.

---

## Documentación Complementaria

Los siguientes documentos se encuentran fuera del directorio `docs/`, pero forman parte de la documentación del proyecto:

- **[`../notebooks/README.md`](../notebooks/README.md)** — Notebooks didácticos con demostraciones visuales del sistema (notebooks 00–09).

- **[`../web-demo/README.md`](../web-demo/README.md)** — Documentación de la interfaz web de demostración para catálogo, ejecución y benchmark.

- **[`../online_policy_ml/README.md`](../online_policy_ml/README.md)** — Documentación del subproyecto de entrenamiento de políticas de aprendizaje automático para el modo online.

---

## Temas Fuera de Alcance

Los siguientes temas no son parte del alcance actual del proyecto:

- **Espacio de datos distribuido:** Aunque los descriptores de servicios están implementados (`GET /api/v1/services` y `DataspaceService`), la integración completa con un espacio de datos distribuido (publicación, descubrimiento, negociación) no es prioritaria.

Para más información sobre las prioridades y el trabajo pendiente, consultar [`roadmap.md`](roadmap.md).
