# packing-services

## Descripción General

**packing-services** es una plataforma de software desarrollada en Python 3.10 con FastAPI que permite empaquetar, validar y comparar metodologías del dominio *Cutting and Packing*. El sistema soporta múltiples formulaciones del problema: 3D Bin Packing Problem (3D-BPP), Container Loading, Cartonization, Palletization y Stacking-aware Packing.

### Objetivo del Proyecto

El objetivo principal de este proyecto es proporcionar un marco de comparación justo entre diferentes metodologías de empaquetado. Para ello, todas las metodologías se evalúan bajo las mismas condiciones:

- **Misma entrada:** formato de datos homogéneo para todos los algoritmos.
- **Mismo validador:** verificación geométrica independiente del algoritmo que genera la solución.
- **Mismas métricas:** indicadores de rendimiento calculados de forma uniforme.

El sistema soporta dos modos de operación:
- **Modo offline** (`packing_mode=offline`): el pedido completo se conoce de antemano y puede reordenarse.
- **Modo online** (`packing_mode=online`): los ítems llegan en secuencia y deben procesarse en orden de llegada.

> **Nota importante:** Este proyecto no busca desarrollar un algoritmo óptimo ni implementar un espacio de datos distribuido. Su propósito es exclusivamente la comparación objetiva de metodologías.

**Versión actual:** 0.1.0

---

## Estructura de la Documentación

La documentación sigue una estructura jerárquica en cascada. Este README constituye el documento raíz; los documentos subsecuentes profundizan en aspectos específicos.

| Nivel | Documento | Contenido |
|:-----:|-----------|-----------|
| 0 | **Este README** | Objetivo, prioridades, estado actual e instrucciones de ejecución |
| 1 | [`docs/README.md`](docs/README.md) | Índice de la documentación técnica |
| 1 | [`docs/roadmap.md`](docs/roadmap.md) | Hitos completados y trabajo pendiente |
| 2 | [`docs/architecture.md`](docs/architecture.md) | Arquitectura del sistema, capas y flujos de datos |
| 2 | [`docs/algorithm_catalog.md`](docs/algorithm_catalog.md) | Catálogo de 52 algoritmos disponibles |
| 2 | [`docs/api_examples.md`](docs/api_examples.md) | Ejemplos de uso de la API REST |
| 3 | [`docs/algorithm_implementation_traceability.md`](docs/algorithm_implementation_traceability.md) | Guía para implementar nuevos algoritmos |
| 3 | [`docs/external_adapters.md`](docs/external_adapters.md) | Integración con motores externos |
| 3 | [`notebooks/README.md`](notebooks/README.md) | Notebooks de demostración visual |
| 3 | [`web-demo/README.md`](web-demo/README.md) | Interfaz web de demostración |
| 3 | [`online_policy_ml/README.md`](online_policy_ml/README.md) | Entrenamiento de políticas de aprendizaje automático |

> **Convención:** En caso de discrepancia entre la documentación y el código fuente, el código fuente (`src/packing_services/`) prevalece como fuente de verdad.

---

## Prioridades del Proyecto

El desarrollo del proyecto sigue un orden de prioridades establecido. Los primeros tres objetivos ya se encuentran operativos:

1. **Homogeneización de entradas** — *Completado.*
   Contrato unificado `PackAlgorithmInput` y conversión desde formato BED-BPP hacia el formato canónico interno. Trabajo pendiente: normalización de unidades entre instancias showcase y datos BED-BPP (mm/kg).

2. **Benchmark de metodologías** — *Completado.*
   Sistema de perfiles por tipo de problema y experimento conjunto con validador y métricas comunes. Trabajo pendiente: ampliar el conjunto de pedidos BED-BPP de prueba.

3. **Empaquetado online** — *Completado.*
   Implementación de heurístico dedicado y política aprendida de producción (RL / PPO). La imitación P2O quedó en `online_policy_ml/versions/v1`. Cierre: [`online_policy_ml/docs/informe_cierre_rl_online.md`](online_policy_ml/docs/informe_cierre_rl_online.md).

4. **Mejoras de calidad** — *Siguiente paso.*
   Restricciones avanzadas (centro de gravedad, fragilidad), activación de adaptadores externos, métodos exactos de referencia.

5. **Espacio de datos** — *Despriorizado.*
   Los descriptores de servicios están implementados (`GET /api/v1/services`), pero la integración completa no es prioritaria.

Para más detalles, consultar [`docs/roadmap.md`](docs/roadmap.md).

---

## Estado Actual del Sistema

| Componente | Estado |
|------------|--------|
| Contrato canónico (`Item`, `Container`, `PackingProblem`, `PackingSolution`) | Operativo |
| Validador geométrico y métricas comunes | Operativo |
| Algoritmos ejecutables (31 implementados) | Operativo |
| Benchmark por tipo de problema | Operativo |
| Entrada BED-BPP con holdout de producto | Operativo |
| Modos offline y online | Operativos |
| Experimento conjunto con euro-pallet | Operativo |
| Heurístico online y política DRL | Operativos |
| Adaptadores externos | Registrados (solo `py3dbp` ejecutable) |
| Descriptores de espacio de datos | Preparados, no prioritarios |

El catálogo contiene **52 algoritmos**: 31 implementados, 6 adaptadores y 15 futuros. La tabla completa está disponible en [`docs/algorithm_catalog.md`](docs/algorithm_catalog.md).

### Algoritmos Implementados (31)

| Categoría | Algoritmos |
|-----------|------------|
| 3D-BPP Constructivos | `heuristic_3d_bpp_v1`, `first_fit_decreasing_3d`, `best_fit_decreasing_3d`, `extreme_points_3d`, `maximal_spaces_3d` |
| 3D-BPP Mejora/Híbridos | `solution_compaction`, `constructive_plus_local_search`, `relocation_improvement`, `swap_improvement`, `orientation_improvement`, `bin_reduction` |
| 3D-BPP Metaheurísticas | `simulated_annealing_3d_bpp`, `genetic_algorithm_3d_bpp`, `grasp_3d_bpp`, `tabu_search_3d_bpp`, `lns_3d_bpp`, `vns_3d_bpp`, `aco_3d_bpp` |
| Container Loading | `single_container_constructive`, `weight_aware_container_loading`, `wall_building_3d` |
| Cartonization | `smallest_feasible_box`, `best_box_volume_utilization`, `first_fit_box`, `largest_feasible_box`, `multi_box_cartonization` |
| Palletization | `layer_based_palletization`, `stack_based_palletization` |
| Stacking-aware | `stacking_aware_constructive` |
| Online | `online_3d_bpp_heuristic`, `drl_policy_3d_bpp` |

> **Nota sobre Cartonization:** Este tipo de problema selecciona una caja de un catálogo, a diferencia del resto que reciben el contenedor como parámetro de entrada.

---

## Contrato de Ejecución

### Endpoint Principal

```
POST /api/v1/algorithms/{algorithm_name}/execute
```

### Tipos de Entrada por Problema

| Tipo de Problema | Esquema de Entrada | Modo |
|------------------|-------------------|------|
| `3D_BPP`, `CONTAINER_LOADING`, `SINGLE_CONTAINER_LOADING`, `PALLETIZATION`, `STACKING_AWARE` | `PackAlgorithmInput` | Offline y Online |
| `CARTONIZATION` | `CartonizationAlgorithmInput` | Solo Offline |

### Características del Contrato

- **Campo `packing_mode`:** acepta valores `offline` (predeterminado) u `online`. Ambos modos utilizan el mismo formato JSON de entrada.
- **Salida uniforme:** todas las ejecuciones retornan `AlgorithmExecuteResponse`, que incluye la solución, el informe de validación y las métricas calculadas.
- **Soporte BED-BPP:** el endpoint acepta el formato wrapper `{ "input_format": "bed_bpp", "order_id", "orders", "packing_mode" }` y realiza la conversión automática al contrato interno.

### Filtrado del Catálogo

```bash
# Filtrar por modo de packing
GET /api/v1/algorithms?packing_mode=offline

# Obtener descripción de los modos disponibles
GET /api/v1/packing-modes
```

Para ejemplos detallados, consultar [`docs/api_examples.md`](docs/api_examples.md).

---

## Instalación y Ejecución

### Requisitos Previos

- Python 3.10 o superior
- pip (gestor de paquetes de Python)

### Instalación Básica

```bash
# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
pip install -e .

# Ejecutar pruebas
pytest

# Iniciar servidor de desarrollo
PYTHONPATH=src uvicorn packing_services.api.main:app --reload
```

### Dependencias Opcionales

```bash
# Para inferencia con modelos MLP (archivos .pt)
pip install 'packing-services[torch]'

# Para el adaptador externo py3dbp
pip install py3dbp
```

### Documentación Interactiva

Una vez iniciado el servidor, la documentación interactiva de la API está disponible en: http://localhost:8000/docs

### Ejecución de Experimentos

```bash
# Experimento conjunto: pedido BED-BPP con euro-pallet (modo offline por defecto)
PYTHONPATH=src python scripts/run_joint_single_container.py

# Interfaz web de demostración
./web-demo/start.sh   # API en puerto 8000, UI en puerto 8080
```

---

## Referencia de Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Verificación del estado del servicio |
| GET | `/api/v1/packing-modes` | Descripción de modos offline y online |
| GET | `/api/v1/algorithms` | Catálogo de algoritmos (filtrable) |
| GET | `/api/v1/algorithms/{name}` | Metadatos y esquemas de un algoritmo |
| **POST** | **`/api/v1/algorithms/{name}/execute`** | **Ejecución canónica de algoritmo** |
| POST | `/api/v1/online/learned/execute` | Política aprendida RL (PPO); fuerza modo online |
| POST | `/api/v1/online/rl/execute` | Alias explícito de la misma política RL |
| POST | `/api/v1/validate` | Validación independiente de soluciones |
| POST | `/api/v1/benchmark` | Comparación de múltiples motores |
| GET | `/api/v1/benchmark/profiles` | Perfiles de benchmark disponibles |
| POST | `/api/v1/benchmark/joint-single-container` | Experimento conjunto multi-tipo |
| GET/POST | `/api/v1/datasets/bed-bpp/*` | Operaciones con dataset BED-BPP |
| POST | `/api/v1/pack/*` | Endpoints legacy (preferir `/algorithms/{name}/execute`) |
| GET | `/api/v1/services` | Descriptores de servicios (no prioritario) |
| GET | `/api/v1/metadata` | Metadatos globales del servicio |

---

## Estructura del Repositorio

```
packing-services/
├── README.md                 # Este documento
├── docs/                     # Documentación técnica detallada
├── src/packing_services/     # Código fuente principal
│   ├── domain/               # Modelos de dominio y geometría
│   ├── schemas/              # Contratos de la API
│   ├── validation/           # Validador geométrico
│   ├── metrics/              # Cálculo de métricas
│   ├── algorithms/           # Implementaciones de algoritmos
│   ├── adapters/             # Adaptadores a motores externos
│   ├── datasets/             # Conversión de formatos de entrada
│   ├── benchmark/            # Sistema de benchmark
│   ├── services/             # Capa de servicios
│   ├── api/                  # Capa de API REST
│   ├── online/               # Bucle de packing online y políticas
│   └── utils/                # Utilidades comunes
├── online_policy_ml/         # Entrenamiento de políticas (artefactos en artifacts/models/)
├── examples/                 # Archivos JSON de ejemplo (incluye holdout 5_bed-bpp.json)
├── tests/                    # Suite de pruebas
├── notebooks/                # Notebooks de demostración
├── web-demo/                 # Interfaz web
└── scripts/                  # Scripts de utilidad
```

Para detalles sobre la arquitectura interna, consultar [`docs/architecture.md`](docs/architecture.md).

---

## Convenciones Técnicas

### Geometría

- Sistema de coordenadas AABB (Axis-Aligned Bounding Box).
- Mapeo de dimensiones: `length` → eje X, `width` → eje Y, `height` → eje Z.
- Origen de coordenadas: esquina mínima del contenedor `(0, 0, 0)`.

### Orientaciones

- `"all"`: permite las 6 rotaciones ortogonales.
- `"none"`: mantiene la orientación original del ítem.

### Limitaciones Actuales

- Los algoritmos son heurísticos; no se garantiza optimalidad.
- Restricciones avanzadas (estabilidad, fragilidad, centro de gravedad) están pendientes de implementación.
- Los motores externos no se modifican; su integración se realiza mediante adaptadores. Ver [`docs/external_adapters.md`](docs/external_adapters.md).

---

## Scripts de Utilidad

| Script | Función |
|--------|---------|
| `scripts/run_joint_single_container.py` | Ejecuta el benchmark conjunto con datos BED-BPP |
| `scripts/regenerate_algorithm_catalog.py` | Regenera `docs/algorithm_catalog.md` desde el registro |
| `scripts/sync_web_demo_showcase.py` | Sincroniza ejemplos showcase con la interfaz web |
