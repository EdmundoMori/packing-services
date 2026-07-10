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

    def _implemented_names(self, problem_type: ProblemType) -> list[str]:
        return [
            m.name
            for m in self.registry.list_metadata(
                problem_type=problem_type, status=AlgorithmStatus.IMPLEMENTED
            )
        ]

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
                input_schema="PackRequest",
                output_schema="PackingSolution",
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[
                    "fragility",
                    "load_bearing",
                    "center_of_gravity",
                    "advanced_stability",
                    "unloading_sequence",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/pack/3d-bpp",
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
                input_schema="ContainerLoadingRequest",
                output_schema="PackingSolution",
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=[
                    "center_of_gravity",
                    "advanced_stability",
                    "unloading_sequence",
                    "fragility",
                ],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/pack/container-loading",
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
                input_schema="CartonizationRequest",
                output_schema="CartonizationResponse",
                supported_constraints=_COMMON_CONSTRAINTS,
                unsupported_constraints=["fragility", "load_bearing", "multi_box"],
                metrics=DEFAULT_METRICS,
                execution_endpoint="POST /api/v1/pack/cartonization",
                validation_endpoint="POST /api/v1/validate",
                metadata_endpoint="GET /api/v1/algorithms",
                traceability=_TRACEABILITY,
                limitations=[
                    "Selecciona una sola caja; motor principal futuro: BoxPacker",
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
        ]

        return DataspaceCatalogResponse(
            service_version=SERVICE_VERSION,
            dataspace_ready=True,
            services=services,
            notes=[
                "Servicios preparados para publicación; aún NO integrados en un "
                "espacio de datos real.",
                "Flujo previsto: publicar → descubrir → negociar → ejecutar → "
                "validar → comparar → registrar evidencias.",
                "Los motores externos (skjolber, BoxPacker, 3DContainerPacking, "
                "PackingSolver, D-Wave) se integran vía adaptadores.",
            ],
        )
