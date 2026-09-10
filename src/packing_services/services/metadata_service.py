"""Metadatos globales del servicio."""

from __future__ import annotations

from .. import SERVICE_VERSION
from ..algorithms.registry import AlgorithmRegistry, get_default_registry
from ..domain.enums import AlgorithmStatus
from ..schemas.responses import ServiceMetadataResponse

SERVICE_DESCRIPTION = (
    "Comparar metodologías de Cutting and Packing sobre entradas homogéneas. "
    "Dos modos (mismo input): offline (listo) y online (puerta abierta). "
    "Espacio de datos despriorizado."
)

SUPPORTED_PROBLEM_TYPES = [
    "3D_BPP",
    "SINGLE_CONTAINER_LOADING",
    "CONTAINER_LOADING",
    "CARTONIZATION",
    "PALLETIZATION",
    "STACKING_AWARE",
    "VALIDATION",
    "BENCHMARK",
]

ENDPOINTS = {
    "health": "GET /health",
    "metadata": "GET /api/v1/metadata",
    "services": "GET /api/v1/services",
    "packing_modes": "GET /api/v1/packing-modes",
    "algorithms": "GET /api/v1/algorithms",
    "algorithm_detail": "GET /api/v1/algorithms/{algorithm_name}",
    "algorithm_input_example": "GET /api/v1/algorithms/{algorithm_name}/input-example",
    "algorithm_execute": "POST /api/v1/algorithms/{algorithm_name}/execute",
    "pack_3d_bpp": "POST /api/v1/pack/3d-bpp",
    "pack_container_loading": "POST /api/v1/pack/container-loading",
    "pack_cartonization": "POST /api/v1/pack/cartonization",
    "pack_palletization": "POST /api/v1/pack/palletization",
    "pack_stacking_aware": "POST /api/v1/pack/stacking-aware",
    "validate": "POST /api/v1/validate",
    "benchmark": "POST /api/v1/benchmark",
    "benchmark_profiles": "GET /api/v1/benchmark/profiles",
    "benchmark_joint_single_container": "POST /api/v1/benchmark/joint-single-container",
    "bed_bpp_sample": "GET /api/v1/datasets/bed-bpp/sample",
    "bed_bpp_convert": "POST /api/v1/datasets/bed-bpp/convert",
}

LIMITATIONS = [
    "Los algoritmos son heurísticos; no garantizan optimalidad",
    "Estabilidad física avanzada no soportada en la primera versión",
    "Fragilidad, load-bearing avanzado, centro de gravedad y secuencia de descarga: fases posteriores",
    "Cartonization single-box y multi-box disponibles; motor industrial futuro: BoxPacker",
    "Motores externos se integran mediante adaptadores, sin modificar sus repositorios",
    "Espacio de datos despriorizado: descriptores en /services, sin integración real",
]


class MetadataService:
    """Devuelve metadatos globales del servicio."""

    def __init__(self, registry: AlgorithmRegistry | None = None) -> None:
        self.registry = registry or get_default_registry()

    def get_metadata(self) -> ServiceMetadataResponse:
        implemented = [
            m.name
            for m in self.registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED)
        ]
        return ServiceMetadataResponse(
            service_name="packing-services",
            service_version=SERVICE_VERSION,
            description=SERVICE_DESCRIPTION,
            supported_problem_types=SUPPORTED_PROBLEM_TYPES,
            endpoints=ENDPOINTS,
            implemented_algorithms=implemented,
            limitations=LIMITATIONS,
        )
