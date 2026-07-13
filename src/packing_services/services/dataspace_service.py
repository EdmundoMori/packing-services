"""Servicio de preparación para espacio de datos.

Genera descriptores publicables (activos) por cada servicio operativo, con los
metadatos recomendados por el estado del arte: tipo de problema, algoritmos,
motor, licencia, formatos de entrada/salida, restricciones, métricas, endpoints,
trazabilidad y limitaciones.

El proyecto NO está integrado en un espacio de datos todavía; este servicio deja
todo preparado para el flujo: publicar → descubrir → negociar → ejecutar →
validar → comparar → registrar evidencias.
"""

from __future__ import annotations

from .. import SERVICE_VERSION
from ..algorithms.metadata import DEFAULT_METRICS
from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import AlgorithmStatus, ProblemType
from ..schemas.responses import DataspaceCatalogResponse, ServiceDescriptor
from .algorithm_input_service import (
    CARTONIZATION_INPUT_SCHEMA,
    EXECUTE_OUTPUT_SCHEMA,
    PACK_INPUT_SCHEMA,
    AlgorithmInputService,
)

_TRACEABILITY = [
    "execution_metadata (algoritmo, familia, parámetros, semilla, versión)",
    "validation_report por ejecución",
    "métricas recalculables desde la solución",
    "logs de ejecución estándar",
]

_COMMON_CONSTRAINTS = ["containment", "non_overlap", "max_weight", "orientation"]


class DataspaceService:
    """Construye el catálogo de servicios listo para publicación."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()
        self._input = AlgorithmInputService(self.registry)

    def _implemented_names(self, problem_type: ProblemType) -> list[str]:
        return [
            m.name
            for m in self.registry.list_metadata(
                problem_type=problem_type, status=AlgorithmStatus.IMPLEMENTED
            )
        ]

    def _algorithm_service_descriptors(self) -> list[ServiceDescriptor]:
        """Un descriptor publicable por algoritmo ejecutable."""

        descriptors: list[ServiceDescriptor] = []
        for meta in self.registry.list_metadata():
            if not meta.is_executable:
                continue
            primary_type = meta.problem_types[0].value
            descriptors.append(
                ServiceDescriptor(
                    service_name=f"{meta.display_name} Algorithm Service",
                    service_version=SERVICE_VERSION,
                    problem_type=primary_type,
                    description=meta.description or meta.display_name,
                    algorithms=[meta.name],
                    engine=(
                        f"external ({meta.external_engine})"
                        if meta.external_engine
                        else f"internal ({meta.algorithm_family.value})"
                    ),
                    license="MIT",
                    input_schema=self._input.input_schema_for(meta),
                    output_schema=EXECUTE_OUTPUT_SCHEMA,
                    supported_constraints=_COMMON_CONSTRAINTS,
                    unsupported_constraints=[
                        c.value for c in meta.unsupported_constraints
                    ],
                    metrics=meta.metrics or DEFAULT_METRICS,
                    execution_endpoint=self._input.execution_endpoint(meta.name),
                    validation_endpoint="POST /api/v1/validate",
                    metadata_endpoint=f"GET /api/v1/algorithms/{meta.name}",
                    traceability=_TRACEABILITY,
                    limitations=meta.limitations
                    or ["Heurístico; ver catálogo para limitaciones específicas"],
                )
            )
        return descriptors

    def catalog(self) -> DataspaceCatalogResponse:
        services = [
            ServiceDescriptor(
                service_name="3D Bin Packing Offline Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.THREE_D_BPP.value,
                description="Empaqueta ítems 3D en uno o varios contenedores.",
                algorithms=self._implemented_names(ProblemType.THREE_D_BPP),
                engine="internal (constructive heuristics)",
                license="MIT",
                input_schema=PACK_INPUT_SCHEMA,
                output_schema=EXECUTE_OUTPUT_SCHEMA,
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[
                    "fragility",
                    "load_bearing",
                    "center_of_gravity",
                    "advanced_stability",
                    "unloading_sequence",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/algorithms/{algorithm_name}/execute",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=["Heurístico, no óptimo; sin estabilidad avanzada"],
            ),
            ServiceDescriptor(
                service_name="Container Loading Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.CONTAINER_LOADING.value,
                description="Carga mercancía en contenedores/camiones (weight-aware).",
                algorithms=self._implemented_names(ProblemType.CONTAINER_LOADING),
                engine="internal (weight-aware / single-container)",
                license="MIT",
                input_schema=PACK_INPUT_SCHEMA,
                output_schema=EXECUTE_OUTPUT_SCHEMA,
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[
                    "center_of_gravity",
                    "advanced_stability",
                    "unloading_sequence",
                    "fragility",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/algorithms/{algorithm_name}/execute",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=[
                    "Baseline local; motor principal futuro: 3DContainerPacking (EB-AFIT)",
                ],
            ),
            ServiceDescriptor(
                service_name="Cartonization Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.CARTONIZATION.value,
                description="Selecciona la mejor caja del catálogo para un pedido.",
                algorithms=self._implemented_names(ProblemType.CARTONIZATION),
                engine="internal (box selection + extreme points)",
                license="MIT",
                input_schema=CARTONIZATION_INPUT_SCHEMA,
                output_schema=EXECUTE_OUTPUT_SCHEMA,
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=["fragility", "load_bearing", "multi_box"],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/algorithms/{algorithm_name}/execute",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=[
                    "Selecciona una sola caja en algoritmos single-box; multi_box disponible",
                ],
            ),
            ServiceDescriptor(
                service_name="Palletization Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.PALLETIZATION.value,
                description="Empaqueta ítems en pallets (capas o columnas).",
                algorithms=self._implemented_names(ProblemType.PALLETIZATION),
                engine="internal (layer-based / stack-based)",
                license="MIT",
                input_schema=PACK_INPUT_SCHEMA,
                output_schema=EXECUTE_OUTPUT_SCHEMA,
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[
                    "basic_stability",
                    "load_bearing",
                    "center_of_gravity",
                    "advanced_stability",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/algorithms/{algorithm_name}/execute",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=[
                    "Baseline local; motor avanzado futuro: PackingSolver boxstacks",
                ],
            ),
            ServiceDescriptor(
                service_name="Stacking-aware Packing Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.STACKING_AWARE.value,
                description="Empaqueta con reglas de soporte y carga máxima soportada.",
                algorithms=self._implemented_names(ProblemType.STACKING_AWARE),
                engine="internal (stacking-aware constructive)",
                license="MIT",
                input_schema=PACK_INPUT_SCHEMA,
                output_schema=EXECUTE_OUTPUT_SCHEMA,
                supported_constraints=_COMMON_CONSTRAINTS
                + ["basic_stability", "load_bearing"],
                unsupported_constraints=[
                    "center_of_gravity",
                    "advanced_stability",
                    "fragility",
                    "unloading_sequence",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/algorithms/{algorithm_name}/execute",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=[
                    "Requiere max_load_on_top en ítems para load_bearing efectivo",
                ],
            ),
            ServiceDescriptor(
                service_name="Packing Validation Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.VALIDATION.value,
                description="Valida soluciones de packing de cualquier motor.",
                algorithms=["internal_geometric_validator"],
                engine="internal (own validator)",
                license="MIT",
                input_schema="ValidateRequest",
                output_schema="ValidateResponse",
                supported_constraints=_COMMON_CONSTRAINTS + ["basic_stability"],
                unsupported_constraints=["advanced_stability", "center_of_gravity"],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/validate",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/metadata",
                traceability=_TRACEABILITY,
                limitations=["Estabilidad avanzada y load-bearing: fase posterior"],
            ),
            ServiceDescriptor(
                service_name="Packing Benchmark / Comparison Service",
                service_version=SERVICE_VERSION,
                problem_type=ProblemType.BENCHMARK.value,
                description="Compara varios motores sobre la misma instancia con ranking.",
                algorithms=self._implemented_names(ProblemType.THREE_D_BPP),
                engine="internal (comparison + ranking)",
                license="MIT",
                input_schema="BenchmarkRequest",
                output_schema="BenchmarkResponse",
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/benchmark",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=["Integra motores externos solo cuando estén disponibles"],
            ),
            *self._algorithm_service_descriptors(),
        ]

        return DataspaceCatalogResponse(
            service_version=SERVICE_VERSION,
            dataspace_ready=True,
            services=services,
            notes=[
                "Servicios preparados para publicación; aún NO integrados en un "
                "espacio de datos real.",
                "Cada algoritmo implementado expone su propio endpoint: "
                "POST /api/v1/algorithms/{algorithm_name}/execute.",
                "Entrada homogénea: PackAlgorithmInput o CartonizationAlgorithmInput. "
                "Salida homogénea: AlgorithmExecuteResponse.",
                "Flujo previsto: publicar → descubrir → negociar → ejecutar → "
                "validar → comparar → registrar evidencias.",
                "Los motores externos (skjolber, BoxPacker, 3DContainerPacking, "
                "PackingSolver, D-Wave) se integran vía adaptadores.",
            ],
        )
