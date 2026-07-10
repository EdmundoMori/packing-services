"""Catálogo (fases posteriores): heurísticas por capas/paredes y variantes por
grupo de servicio (Container Loading, Cartonization, Palletization, Stacking).

Todas estas fichas quedan registradas como ``future`` para que el roadmap sea
descubrible, sin afirmar que están implementadas.
"""

from __future__ import annotations

from ..domain.enums import AlgorithmFamily, AlgorithmStatus, Constraint, ProblemType
from ._catalog_helpers import catalog_metadata

CATALOG = [
    # --- Heurísticas constructivas 3D adicionales (fase posterior) ---
    catalog_metadata(
        name="bottom_left_back_3d",
        display_name="Bottom-Left-Back Heuristic",
        problem_types=[ProblemType.THREE_D_BPP],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description=(
            "Prioriza posiciones candidatas con menor z, luego y, luego x. Ya "
            "disponible como estrategia interna de otros algoritmos."
        ),
        limitations=["Disponible como estrategia interna, no como servicio propio"],
    ),
    catalog_metadata(
        name="maximal_spaces_3d",
        display_name="Maximal Empty Spaces Heuristic",
        problem_types=[ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description=(
            "Representa los espacios vacíos máximos disponibles y los actualiza "
            "tras cada colocación."
        ),
        limitations=["Más compleja que puntos extremos; fase posterior"],
    ),
    # --- Heurísticas estructurales 3D ---
    catalog_metadata(
        name="layer_based_3d",
        display_name="Layer-based Packing",
        problem_types=[ProblemType.THREE_D_BPP, ProblemType.PALLETIZATION],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Construye capas horizontales dentro del contenedor.",
        limitations=["Útil para palletization y cartonization; fase posterior"],
    ),
    catalog_metadata(
        name="wall_building_3d",
        display_name="Wall-building Heuristic",
        problem_types=[ProblemType.CONTAINER_LOADING],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Construye paredes o bloques verticales dentro del contenedor.",
        limitations=["Orientada a Container Loading; fase futura"],
    ),
    # --- Container Loading ---
    catalog_metadata(
        name="sequence_aware_loading",
        display_name="Sequence-aware Loading",
        problem_types=[ProblemType.CONTAINER_LOADING],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Considera orden de carga/descarga.",
        supported_constraints=[Constraint.UNLOADING_SEQUENCE],
        limitations=["Fase futura salvo soporte verificado en un motor externo"],
    ),
    # --- Cartonization ---
    catalog_metadata(
        name="multi_box_cartonization",
        display_name="Multi-box Cartonization",
        problem_types=[ProblemType.CARTONIZATION],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Permite usar más de una caja para un pedido.",
        limitations=["Fase posterior"],
    ),
    # --- Palletization ---
    catalog_metadata(
        name="layer_based_palletization",
        display_name="Layer-based Palletization",
        problem_types=[ProblemType.PALLETIZATION],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Construye capas sobre el pallet (altura/peso/orientación).",
        limitations=["Extensión natural de layer_based_3d; fase posterior"],
    ),
    catalog_metadata(
        name="stack_based_palletization",
        display_name="Stack-based Palletization",
        problem_types=[ProblemType.PALLETIZATION, ProblemType.STACKING_AWARE],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Organiza cajas en stacks/columnas con soporte y carga máxima.",
        supported_constraints=[Constraint.LOAD_BEARING, Constraint.BASIC_STABILITY],
        limitations=["Fase posterior"],
    ),
    # --- Stacking-aware ---
    catalog_metadata(
        name="basic_support_surface_validation",
        display_name="Basic Support Surface Validation",
        problem_types=[ProblemType.STACKING_AWARE, ProblemType.VALIDATION],
        family=AlgorithmFamily.VALIDATOR,
        status=AlgorithmStatus.FUTURE,
        description=(
            "Valida si un ítem apoyado sobre otros tiene suficiente superficie "
            "de soporte. Base ya disponible en el validador geométrico."
        ),
        supported_constraints=[Constraint.BASIC_STABILITY],
        limitations=["El validador ya incluye la comprobación; falta exponerla como servicio"],
    ),
    catalog_metadata(
        name="load_bearing_validator",
        display_name="Load-bearing Constraint Check",
        problem_types=[ProblemType.STACKING_AWARE, ProblemType.VALIDATION],
        family=AlgorithmFamily.VALIDATOR,
        status=AlgorithmStatus.FUTURE,
        description="Valida el peso máximo soportado por un ítem inferior.",
        supported_constraints=[Constraint.LOAD_BEARING],
        limitations=["Requiere el campo max_load_on_top poblado en los ítems"],
    ),
    catalog_metadata(
        name="stacking_aware_constructive",
        display_name="Stacking-aware Constructive Packing",
        problem_types=[ProblemType.STACKING_AWARE],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Coloca ítems solo si cumplen reglas básicas de soporte.",
        supported_constraints=[Constraint.BASIC_STABILITY, Constraint.LOAD_BEARING],
        limitations=["Fase posterior"],
    ),
]
