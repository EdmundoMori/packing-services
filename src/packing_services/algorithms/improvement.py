"""Catálogo (fase posterior): heurísticas de mejora.

Estas técnicas operan como segunda capa sobre una solución inicial válida. No
deben implementarse antes de tener una solución base validable, por lo que
quedan registradas como ``future``.
"""

from __future__ import annotations

from ..domain.enums import AlgorithmFamily, AlgorithmStatus, ProblemType
from ._catalog_helpers import catalog_metadata

_PROBLEMS = [ProblemType.THREE_D_BPP, ProblemType.CONTAINER_LOADING]

CATALOG = [
    catalog_metadata(
        "relocation_improvement",
        "Relocation Improvement",
        _PROBLEMS,
        AlgorithmFamily.IMPROVEMENT_HEURISTIC,
        AlgorithmStatus.FUTURE,
        "Mueve ítems para mejorar utilización o reducir huecos.",
        limitations=["Requiere una solución inicial válida"],
    ),
    catalog_metadata(
        "orientation_improvement",
        "Orientation Improvement",
        _PROBLEMS,
        AlgorithmFamily.IMPROVEMENT_HEURISTIC,
        AlgorithmStatus.FUTURE,
        "Cambia la orientación de ítems ya colocados.",
        limitations=["Requiere una solución inicial válida"],
    ),
    catalog_metadata(
        "swap_improvement",
        "Swap Improvement",
        _PROBLEMS,
        AlgorithmFamily.IMPROVEMENT_HEURISTIC,
        AlgorithmStatus.FUTURE,
        "Intercambia ítems entre posiciones o contenedores.",
        limitations=["Requiere una solución inicial válida"],
    ),
    catalog_metadata(
        "bin_reduction",
        "Bin Reduction",
        _PROBLEMS,
        AlgorithmFamily.IMPROVEMENT_HEURISTIC,
        AlgorithmStatus.FUTURE,
        "Intenta vaciar contenedores moviendo ítems a otros.",
        limitations=["Requiere una solución inicial válida"],
    ),
]
