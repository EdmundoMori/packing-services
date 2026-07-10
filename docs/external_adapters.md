# Adaptadores a motores externos

## Principio

**No se modifican los repositorios externos.** Cada adaptador traduce entre el
formato normalizado del proyecto y el formato interno del motor:

```
entrada normalizada del servicio
  → adaptador de entrada
  → formato interno del repositorio
  → ejecución del motor algorítmico
  → adaptador de salida
  → salida normalizada comparable
```

Así cada repositorio conserva su lenguaje, licencia, dependencias y forma de
ejecución, mientras el proyecto expone servicios homogéneos y comparables.

## Interfaz común

Todos los adaptadores heredan de `adapters.base.ExternalAdapter`, que comparte
interfaz con los algoritmos locales (`PackingAlgorithm`) pero añade
`is_available()`. Si el motor no está disponible, `run()` lanza
`AdapterUnavailableError` con instrucciones (mapeado a HTTP 503). Esto garantiza
que un motor externo ausente **no rompe** el proyecto.

Todos los adaptadores están registrados y son visibles en
`GET /api/v1/algorithms?status=adapter`.

## Adaptadores disponibles

| Adaptador | Motor | Lenguaje | Rol | Estado |
|-----------|-------|----------|-----|--------|
| `py3dbp_adapter` | enzoruiz/3dbinpacking | Python | Baseline 3D-BPP | Ejecutable si `pip install py3dbp` |
| `skjolber_adapter` | skjolber/3d-bin-container-packing | Java | Motor principal 3D-BPP offline | Stub documentado |
| `boxpacker_adapter` | dvdoug/BoxPacker | PHP | Motor principal Cartonization | Stub documentado |
| `container_packing_adapter` | davidmchapman/3DContainerPacking | C# | Motor principal Container Loading (EB-AFIT) | Stub documentado |
| `packingsolver_adapter` | fontanf/packingsolver | C++ | Motor avanzado / benchmark / stacking / palletization | Stub documentado |
| `dwave_adapter` | dwave-examples/3d-bin-packing | Python | Referencia matemática / benchmark (CQM) | Stub documentado |

## `py3dbp_adapter` (único ejecutable en v0.1)

```bash
pip install py3dbp   # o: pip install .[py3dbp]
```

Mapeo de ejes: `length`→width(x), `width`→height(y), `height`→depth(z) de py3dbp.
La salida (posiciones, orientación tras rotación, ítems no colocados) se traduce
al formato normalizado y pasa por el validador y las métricas del proyecto, igual
que cualquier algoritmo interno.

Parámetros soportados: `bigger_first`, `distribute_items`, `number_of_decimals`.

## Estrategia de integración de los stubs

Cada motor externo se integrará como **microservicio separado** o **wrapper por
proceso**, según su lenguaje:

- **Java (skjolber)**: JVM + wrapper por proceso o microservicio.
- **PHP (BoxPacker)**: microservicio PHP separado.
- **C# (3DContainerPacking)**: runtime .NET + wrapper por proceso.
- **C++/CLI (PackingSolver)**: compilar binario; integración por archivos de
  ítems/bins/parámetros y certificados de salida. **No se inventan comandos**:
  deben verificarse localmente antes de implementar.
- **D-Wave**: referencia avanzada; requiere credenciales del Leap hybrid CQM
  solver, por lo que **no** es un motor operativo inicial.

## Cómo añadir un adaptador nuevo

1. Crear `adapters/<motor>_adapter.py` con su `AlgorithmMetadata` y una clase
   que herede de `ExternalAdapter`.
2. Implementar `is_available()` (p. ej. comprobar binario/dependencia) y
   `_run_available(problem)` (traducción entrada → motor → salida normalizada).
3. Registrarlo en `adapters/__init__.py::build_adapters()`.
4. Reutilizar `algorithms.base.build_solution` para validar y calcular métricas,
   asegurando comparabilidad.
