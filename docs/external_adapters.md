# Adaptadores a Motores Externos

Documento complementario de [`../README.md`](../README.md). Para el índice de documentación técnica, consultar [`README.md`](README.md).

## Contexto

La activación de adaptadores externos es parte del objetivo 4 (Mejoras de Calidad) según la hoja de ruta del proyecto. Los objetivos 1–3 (homogeneización de entradas, benchmark de metodologías, packing online) ya están operativos.

Para más información sobre las prioridades, consultar [`roadmap.md`](roadmap.md) §4.

---

## Principio de Diseño

**Los repositorios externos no se modifican.** Cada adaptador actúa como traductor entre el formato normalizado del proyecto y el formato interno del motor externo:

```
Entrada normalizada del servicio
    │
    ▼
Adaptador de entrada
    │
    ▼
Formato interno del repositorio
    │
    ▼
Ejecución del motor algorítmico
    │
    ▼
Adaptador de salida
    │
    ▼
Salida normalizada comparable
```

Este diseño permite que cada repositorio externo conserve su lenguaje, licencia, dependencias y forma de ejecución, mientras el proyecto expone servicios homogéneos y comparables.

---

## Interfaz Común

Todos los adaptadores heredan de `adapters.base.ExternalAdapter`, que comparte interfaz con los algoritmos locales (`PackingAlgorithm`) pero añade el método `is_available()`.

### Comportamiento ante Motor No Disponible

Si el motor externo no está disponible, el método `run()` lanza `AdapterUnavailableError` con instrucciones de instalación. Este error se mapea a HTTP 503.

Este diseño garantiza que la **ausencia de un motor externo no rompe el proyecto**.

### Descubrimiento

Todos los adaptadores registrados son visibles mediante:

```bash
GET /api/v1/algorithms?status=adapter
```

---

## Adaptadores Disponibles

| Adaptador | Motor | Lenguaje | Rol | Estado |
|-----------|-------|----------|-----|--------|
| `py3dbp_adapter` | enzoruiz/3dbinpacking | Python | Baseline 3D-BPP | **Ejecutable** si `pip install py3dbp` |
| `skjolber_adapter` | skjolber/3d-bin-container-packing | Java | Motor principal 3D-BPP offline | Stub documentado |
| `boxpacker_adapter` | dvdoug/BoxPacker | PHP | Motor principal Cartonization | Stub documentado |
| `container_packing_adapter` | davidmchapman/3DContainerPacking | C# | Motor principal Container Loading (EB-AFIT) | Stub documentado |
| `packingsolver_adapter` | fontanf/packingsolver | C++ | Motor avanzado / benchmark / stacking / palletization | Stub documentado |
| `dwave_adapter` | dwave-examples/3d-bin-packing | Python | Referencia matemática / benchmark (CQM) | Stub documentado |

---

## `py3dbp_adapter` (Único Ejecutable en v0.1)

### Instalación

```bash
pip install py3dbp
# Alternativa:
pip install .[py3dbp]
```

### Mapeo de Ejes

El adaptador traduce entre los sistemas de coordenadas:

| packing-services | py3dbp |
|------------------|--------|
| `length` | width (x) |
| `width` | height (y) |
| `height` | depth (z) |

### Procesamiento de Salida

La salida del motor (posiciones, orientación tras rotación, ítems no colocados) se traduce al formato normalizado y pasa por el validador y las métricas del proyecto, de forma idéntica a cualquier algoritmo interno.

### Parámetros Soportados

- `bigger_first`
- `distribute_items`
- `number_of_decimals`

---

## Estrategia de Integración para Stubs

Cada motor externo se integrará como **microservicio separado** o **wrapper por proceso**, según su lenguaje de implementación:

| Motor | Lenguaje | Estrategia de Integración |
|-------|----------|---------------------------|
| skjolber | Java | JVM + wrapper por proceso o microservicio |
| BoxPacker | PHP | Microservicio PHP separado |
| 3DContainerPacking | C# | Runtime .NET + wrapper por proceso |
| PackingSolver | C++/CLI | Compilar binario; integración por archivos de ítems/bins/parámetros y certificados de salida |
| D-Wave | Python | Referencia avanzada; requiere credenciales del Leap hybrid CQM solver |

> **Importante:** Los comandos de integración para PackingSolver deben verificarse localmente antes de implementar. No se inventan comandos.

> **Nota sobre D-Wave:** Dado que requiere credenciales externas, no es un motor operativo inicial.

---

## Guía para Añadir un Adaptador Nuevo

### Paso 1: Crear el Adaptador

Crear el archivo `adapters/<motor>_adapter.py` con:
- `AlgorithmMetadata` describiendo el algoritmo
- Clase que herede de `ExternalAdapter`

### Paso 2: Implementar Métodos Requeridos

```python
def is_available(self) -> bool:
    """Verificar si el binario o dependencia está disponible."""
    ...

def _run_available(self, problem: PackingProblem) -> PackingSolution:
    """Traducir entrada → motor → salida normalizada."""
    ...
```

### Paso 3: Registrar el Adaptador

Añadir al archivo `adapters/__init__.py` en la función `build_adapters()`.

### Paso 4: Garantizar Comparabilidad

Reutilizar `algorithms.base.build_solution` para validar y calcular métricas. Esto asegura que la salida sea directamente comparable con cualquier otro algoritmo del sistema.
