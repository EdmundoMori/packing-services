"""Catálogo (fases futuras): métodos exactos, de referencia e híbridos.

Los métodos exactos no son el primer motor operativo, pero se contemplan para
instancias pequeñas, benchmarking y validación. Los enfoques híbridos son la
evolución natural tras heurísticas + validador.
"""

from __future__ import annotations

from ..domain.enums import AlgorithmFamily, AlgorithmStatus, ProblemType
from ._catalog_helpers import catalog_metadata

_PROBLEMS = [ProblemType.THREE_D_BPP]

CATALOG = [
    # --- Métodos exactos / referencia ---
    catalog_metadata(
        "mip_3d_bpp_reference",
        "Mixed Integer Programming (reference)",
        _PROBLEMS,
        AlgorithmFamily.EXACT,
        AlgorithmStatus.FUTURE,
        "Formulación MIP para instancias pequeñas y soluciones de referencia.",
        supports_time_limit=True,
        limitations=["Solo instancias pequeñas; roadmap"],
    ),
    catalog_metadata(
        "cp_sat_3d_bpp_reference",
        "Constraint Programming / CP-SAT (reference)",
        _PROBLEMS,
        AlgorithmFamily.EXACT,
        AlgorithmStatus.FUTURE,
        "Factibilidad en instancias pequeñas, potencialmente con OR-Tools.",
        supports_time_limit=True,
        limitations=["Requiere OR-Tools; fase posterior"],
    ),
    catalog_metadata(
        "branch_and_bound_reference",
        "Branch and Bound (reference)",
        _PROBLEMS,
        AlgorithmFamily.EXACT,
        AlgorithmStatus.FUTURE,
        "Búsqueda exacta con poda.",
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "branch_and_cut_reference",
        "Branch and Cut (reference)",
        _PROBLEMS,
        AlgorithmFamily.EXACT,
        AlgorithmStatus.FUTURE,
        "Branch and bound con planos de corte.",
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "column_generation_cutting_packing",
        "Branch and Price / Column Generation",
        [ProblemType.THREE_D_BPP],
        AlgorithmFamily.EXACT,
        AlgorithmStatus.FUTURE,
        "Generación de columnas para cutting stock o variantes estructuradas.",
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "knapsack_layer_selection",
        "Knapsack-based Layer Selection",
        [ProblemType.THREE_D_BPP, ProblemType.PALLETIZATION],
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "Selección de capas mediante knapsack en enfoques por capas.",
        limitations=["Enfoque híbrido; fase futura"],
    ),
    # --- Enfoques híbridos ---
    catalog_metadata(
        "constructive_plus_local_search",
        "Constructive Heuristic + Local Improvement",
        _PROBLEMS,
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "Heurística constructiva seguida de mejora local.",
        supports_time_limit=True,
        limitations=["Evolución natural tras heurística + validador"],
    ),
    catalog_metadata(
        "extreme_points_plus_sa",
        "Extreme Points + Simulated Annealing",
        _PROBLEMS,
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "Construcción por puntos extremos + recocido simulado.",
        deterministic=False,
        supports_random_seed=True,
        supports_time_limit=True,
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "layer_knapsack_hybrid",
        "Layer Decomposition + Knapsack",
        [ProblemType.THREE_D_BPP, ProblemType.PALLETIZATION],
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "Descomposición por capas combinada con knapsack.",
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "mip_heuristic_hybrid",
        "MIP for Small Subproblems + Heuristic Packing",
        _PROBLEMS,
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "MIP para subproblemas pequeños + empaquetado heurístico.",
        supports_time_limit=True,
        limitations=["Fase futura"],
    ),
    catalog_metadata(
        "packingsolver_plus_internal_validator",
        "PackingSolver Adapter + Local Validation",
        [ProblemType.THREE_D_BPP, ProblemType.STACKING_AWARE, ProblemType.PALLETIZATION],
        AlgorithmFamily.HYBRID,
        AlgorithmStatus.FUTURE,
        "Motor externo PackingSolver validado por el validador interno.",
        external_engine="fontanf/packingsolver",
        external_language="C++",
        external_repository="https://github.com/fontanf/packingsolver",
        limitations=["Depende del adaptador packingsolver_adapter"],
    ),
]
