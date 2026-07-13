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
        name="layer_based_3d",
        display_name="Layer-based Packing",
        problem_types=[ProblemType.THREE_D_BPP, ProblemType.PALLETIZATION],
        family=AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        status=AlgorithmStatus.FUTURE,
        description="Construye capas horizontales dentro del contenedor.",
        limitations=["Útil para palletization y cartonization; fase posterior"],
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
    # --- Cartonization (multi-caja implementado en multi_box_cartonization.py) ---
    # --- Palletization (implementado en módulos dedicados) ---
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
    # --- Stacking-aware (constructivo implementado en stacking_aware_constructive.py) ---
]
