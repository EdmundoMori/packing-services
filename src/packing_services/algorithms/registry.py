"""Registro homogéneo de algoritmos (``AlgorithmRegistry``).

Permite listar, describir, filtrar y ejecutar algoritmos por nombre de forma
uniforme, sin importar si son implementaciones locales, adaptadores externos,
stubs o entradas futuras del roadmap.
"""

from __future__ import annotations

from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    PackingMode,
    ProblemType,
)
from ..domain.models import PackingProblem, PackingSolution
from ..utils.errors import (
    AlgorithmNotExecutableError,
    AlgorithmNotFoundError,
    InvalidInputError,
)
from .base import PackingAlgorithm
from .metadata import AlgorithmMetadata


class AlgorithmRegistry:
    """Contenedor central de algoritmos y sus metadatos."""

    def __init__(self) -> None:
        self._executables: dict[str, PackingAlgorithm] = {}
        self._metadata: dict[str, AlgorithmMetadata] = {}

    # ------------------------------------------------------------------ #
    # Registro
    # ------------------------------------------------------------------ #

    def register_algorithm(self, algorithm: PackingAlgorithm) -> None:
        """Registra un algoritmo ejecutable (implementación o adaptador)."""

        name = algorithm.metadata.name
        if name in self._metadata:
            raise ValueError(f"Algoritmo duplicado en el registro: {name}")
        self._executables[name] = algorithm
        self._metadata[name] = algorithm.metadata

    def register_metadata(self, metadata: AlgorithmMetadata) -> None:
        """Registra metadatos de un algoritmo no ejecutable (stub/future)."""

        if metadata.name in self._metadata:
            raise ValueError(f"Algoritmo duplicado en el registro: {metadata.name}")
        self._metadata[metadata.name] = metadata

    def register_many_metadata(self, items: list[AlgorithmMetadata]) -> None:
        for meta in items:
            self.register_metadata(meta)

    # ------------------------------------------------------------------ #
    # Consulta
    # ------------------------------------------------------------------ #

    def has(self, name: str) -> bool:
        return name in self._metadata

    def is_executable(self, name: str) -> bool:
        return name in self._executables

    def get_metadata(self, name: str) -> AlgorithmMetadata:
        if name not in self._metadata:
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {name}")
        return self._metadata[name]

    def list_metadata(
        self,
        problem_type: ProblemType | None = None,
        family: AlgorithmFamily | None = None,
        status: AlgorithmStatus | None = None,
        supported_constraint: Constraint | None = None,
        packing_mode: PackingMode | None = None,
    ) -> list[AlgorithmMetadata]:
        """Lista los metadatos, con filtros opcionales combinables."""

        result = list(self._metadata.values())
        if problem_type is not None:
            result = [m for m in result if problem_type in m.problem_types]
        if family is not None:
            result = [m for m in result if m.algorithm_family == family]
        if status is not None:
            result = [m for m in result if m.status == status]
        if supported_constraint is not None:
            result = [
                m for m in result if supported_constraint in m.supported_constraints
            ]
        if packing_mode is not None:
            result = [m for m in result if packing_mode in m.packing_modes]
        return sorted(result, key=lambda m: (m.status.value, m.name))

    def list_names(self) -> list[str]:
        return sorted(self._metadata.keys())

    # ------------------------------------------------------------------ #
    # Ejecución
    # ------------------------------------------------------------------ #

    def execute(self, name: str, problem: PackingProblem) -> PackingSolution:
        """Ejecuta un algoritmo por nombre sobre una instancia normalizada."""

        if name not in self._metadata:
            raise AlgorithmNotFoundError(f"Algoritmo no encontrado: {name}")
        if name not in self._executables:
            status = self._metadata[name].status.value
            raise AlgorithmNotExecutableError(
                f"El algoritmo '{name}' no es ejecutable en esta versión "
                f"(estado: {status})."
            )
        meta = self._metadata[name]
        if problem.problem_type not in meta.problem_types:
            raise InvalidInputError(
                f"El algoritmo '{name}' no soporta problem_type="
                f"{problem.problem_type.value}. "
                f"Tipos compatibles: {[p.value for p in meta.problem_types]}"
            )
        return self._executables[name].run(problem)


def _build_default_registry() -> AlgorithmRegistry:
    """Construye el registro por defecto con el catálogo completo."""

    # Imports locales para evitar ciclos y mantener el import de paquete ligero.
    from . import (
        exact_reference,
        improvement,
        layer_based_3d,
        metaheuristics,
    )
    from .best_fit_decreasing_3d import BestFitDecreasing3D
    from .bin_reduction import BinReduction
    from .cartonization import (
        BestBoxVolumeUtilization,
        FirstFitBox,
        LargestFeasibleBox,
        SmallestFeasibleBox,
    )
    from .constructive_plus_local_search import ConstructivePlusLocalSearch
    from .extreme_points_3d import ExtremePoints3D
    from .first_fit_decreasing_3d import FirstFitDecreasing3D
    from .heuristic_3d_bpp import Heuristic3DBPPv1
    from .layer_based_palletization import LayerBasedPalletization
    from .maximal_spaces_3d import MaximalSpaces3D
    from .metaheuristic_3d_bpp import METAHEURISTIC_ALGORITHMS
    from .multi_box_cartonization import MultiBoxCartonization
    from .orientation_improvement import OrientationImprovement
    from .relocation_improvement import RelocationImprovement
    from .single_container import SingleContainerConstructive
    from .solution_compaction import SolutionCompaction
    from .stack_based_palletization import StackBasedPalletization
    from .stacking_aware_constructive import StackingAwareConstructive
    from .swap_improvement import SwapImprovement
    from .wall_building_3d import WallBuilding3D
    from .weight_aware_container_loading import WeightAwareContainerLoading

    registry = AlgorithmRegistry()

    # Algoritmos implementados y ejecutables.
    # 3D Bin Packing offline.
    registry.register_algorithm(Heuristic3DBPPv1())
    registry.register_algorithm(FirstFitDecreasing3D())
    registry.register_algorithm(ExtremePoints3D())
    registry.register_algorithm(BestFitDecreasing3D())
    registry.register_algorithm(MaximalSpaces3D())
    registry.register_algorithm(SolutionCompaction())
    registry.register_algorithm(ConstructivePlusLocalSearch())
    registry.register_algorithm(RelocationImprovement())
    registry.register_algorithm(SwapImprovement())
    registry.register_algorithm(OrientationImprovement())
    registry.register_algorithm(BinReduction())
    for algorithm in METAHEURISTIC_ALGORITHMS:
        registry.register_algorithm(algorithm)
    # Container Loading.
    registry.register_algorithm(SingleContainerConstructive())
    registry.register_algorithm(WeightAwareContainerLoading())
    registry.register_algorithm(WallBuilding3D())
    # Cartonization / Order Packing.
    registry.register_algorithm(SmallestFeasibleBox())
    registry.register_algorithm(BestBoxVolumeUtilization())
    registry.register_algorithm(FirstFitBox())
    registry.register_algorithm(LargestFeasibleBox())
    registry.register_algorithm(MultiBoxCartonization())
    # Palletization.
    registry.register_algorithm(LayerBasedPalletization())
    registry.register_algorithm(StackBasedPalletization())
    # Stacking-aware.
    registry.register_algorithm(StackingAwareConstructive())

    # Adaptadores a motores externos (registran su metadata; ejecutan solo si la
    # dependencia está disponible).
    from ..adapters import build_adapters

    for adapter in build_adapters():
        registry.register_algorithm(adapter)

    # Catálogo de algoritmos futuros / stubs (solo metadatos).
    for module in (
        layer_based_3d,
        improvement,
        exact_reference,
        metaheuristics,
    ):
        registry.register_many_metadata(module.CATALOG)

    return registry


default_registry = _build_default_registry()


def get_default_registry() -> AlgorithmRegistry:
    """Devuelve el registro por defecto (singleton a nivel de módulo)."""

    return default_registry
