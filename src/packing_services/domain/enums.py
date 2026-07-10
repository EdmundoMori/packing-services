"""Enumeraciones comunes del dominio de packing.

Se centralizan aquí para evitar strings mágicos dispersos y para que los
esquemas Pydantic y el registro de algoritmos compartan el mismo vocabulario.
"""

from __future__ import annotations

from enum import Enum


class ProblemType(str, Enum):
    """Tipos de problema soportados o contemplados en el catálogo."""

    THREE_D_BPP = "3D_BPP"
    SINGLE_CONTAINER_LOADING = "SINGLE_CONTAINER_LOADING"
    CONTAINER_LOADING = "CONTAINER_LOADING"
    CARTONIZATION = "CARTONIZATION"
    PALLETIZATION = "PALLETIZATION"
    STACKING_AWARE = "STACKING_AWARE"
    VALIDATION = "VALIDATION"
    BENCHMARK = "BENCHMARK"


class AlgorithmFamily(str, Enum):
    """Familias algorítmicas usadas para clasificar el catálogo."""

    CONSTRUCTIVE_HEURISTIC = "constructive_heuristic"
    IMPROVEMENT_HEURISTIC = "improvement_heuristic"
    METAHEURISTIC = "metaheuristic"
    EXACT = "exact"
    HYBRID = "hybrid"
    MACHINE_LEARNING = "machine_learning"
    ADAPTER = "adapter"
    VALIDATOR = "validator"


class AlgorithmStatus(str, Enum):
    """Estado de implementación de un algoritmo registrado."""

    IMPLEMENTED = "implemented"
    ADAPTER = "adapter"
    STUB = "stub"
    FUTURE = "future"


class Constraint(str, Enum):
    """Vocabulario común de restricciones declarables."""

    CONTAINMENT = "containment"
    NON_OVERLAP = "non_overlap"
    MAX_WEIGHT = "max_weight"
    ORIENTATION = "orientation"
    BASIC_STABILITY = "basic_stability"
    LOAD_BEARING = "load_bearing"
    FRAGILITY = "fragility"
    UNLOADING_SEQUENCE = "unloading_sequence"
    CENTER_OF_GRAVITY = "center_of_gravity"
    ADVANCED_STABILITY = "advanced_stability"
    COMPATIBILITY = "compatibility"


class Severity(str, Enum):
    """Severidad de una violación reportada por el validador."""

    ERROR = "error"
    WARNING = "warning"


class SolutionStatus(str, Enum):
    """Estado de una respuesta de packing."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ERROR = "error"


class SortStrategy(str, Enum):
    """Criterios de ordenamiento de ítems para heurísticas constructivas."""

    VOLUME_DESC = "volume_desc"
    WEIGHT_DESC = "weight_desc"
    LONGEST_DIM_DESC = "longest_dim_desc"


class PositionStrategy(str, Enum):
    """Criterios de ordenamiento de posiciones candidatas."""

    BOTTOM_LEFT_BACK = "bottom_left_back"
