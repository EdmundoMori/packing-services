# Documentación técnica

Documento hijo de [`../README.md`](../README.md). Empieza siempre por el README:
objetivo, prioridades y estado. Aquí solo hay detalle.

## Orden de lectura

1. [`../README.md`](../README.md) — objetivo único y mapa.
2. [`roadmap.md`](roadmap.md) — prioridades (online, inputs, benchmark; espacio de datos al final).
3. [`architecture.md`](architecture.md) — capas y flujos.
4. [`algorithm_catalog.md`](algorithm_catalog.md) — inventario de algoritmos.
5. [`api_examples.md`](api_examples.md) — contratos HTTP y ejemplos.
6. [`algorithm_implementation_traceability.md`](algorithm_implementation_traceability.md) — cómo añadir un algoritmo.
7. [`external_adapters.md`](external_adapters.md) — motores externos.

Fuera de `docs/` (también hijos del README):

- [`../notebooks/README.md`](../notebooks/README.md) — notebooks didácticos.
- [`../web-demo/README.md`](../web-demo/README.md) — interfaz web.

## Qué no buscar aquí

El espacio de datos (`GET /api/v1/services`, `DataspaceService`) existe como
preparación. **No** es la línea de trabajo actual. Ver el último apartado de
[`roadmap.md`](roadmap.md).
