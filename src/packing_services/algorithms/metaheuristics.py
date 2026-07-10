"""Catálogo (fases futuras): metaheurísticas, online packing y ML/DRL.

Todas se registran como ``future``. Las metaheurísticas requieren, por
contrato, registrar parámetros, semilla, tiempo máximo, número de iteraciones,
mejor solución y trazabilidad cuando se implementen.
"""

from __future__ import annotations

from ..domain.enums import AlgorithmFamily, AlgorithmStatus, ProblemType
from ._catalog_helpers import catalog_metadata

_PROBLEMS = [ProblemType.THREE_D_BPP]
_META_PARAMS = {
    "random_seed": "Semilla aleatoria para reproducibilidad",
    "time_limit_seconds": "Tiempo máximo de ejecución",
    "iterations": "Número máximo de iteraciones",
}


def _meta(name: str, display: str, description: str):
    return catalog_metadata(
        name,
        display,
        _PROBLEMS,
        AlgorithmFamily.METAHEURISTIC,
        AlgorithmStatus.FUTURE,
        description,
        deterministic=False,
        supports_random_seed=True,
        supports_time_limit=True,
        parameters=_META_PARAMS,
        limitations=["Metaheurística; fase futura, no incluida en la primera versión"],
    )


CATALOG = [
    _meta("genetic_algorithm_3d_bpp", "Genetic Algorithm 3D-BPP",
          "Optimiza orden/orientación/asignación mediante evolución poblacional."),
    _meta("tabu_search_3d_bpp", "Tabu Search 3D-BPP",
          "Explora movimientos locales evitando ciclos con lista tabú."),
    _meta("simulated_annealing_3d_bpp", "Simulated Annealing 3D-BPP",
          "Recocido simulado sobre orden, orientación o asignación."),
    _meta("grasp_3d_bpp", "GRASP 3D-BPP",
          "Construcción aleatorizada + mejora local."),
    _meta("vns_3d_bpp", "Variable Neighborhood Search 3D-BPP",
          "Cambia entre distintos vecindarios de búsqueda."),
    _meta("lns_3d_bpp", "Large Neighborhood Search 3D-BPP",
          "Remueve y recoloca subconjuntos de ítems."),
    _meta("aco_3d_bpp", "Ant Colony Optimization 3D-BPP",
          "Optimización por colonia de hormigas (roadmap)."),
    # --- Online / Machine Learning ---
    catalog_metadata(
        "online_3d_bpp_heuristic",
        "Online 3D-BPP Heuristic",
        _PROBLEMS,
        AlgorithmFamily.CONSTRUCTIVE_HEURISTIC,
        AlgorithmStatus.FUTURE,
        "Los ítems llegan secuencialmente; no se pueden reordenar offline.",
        limitations=["Línea avanzada; fase futura"],
    ),
    catalog_metadata(
        "drl_policy_3d_bpp",
        "Deep Reinforcement Learning Policy",
        _PROBLEMS,
        AlgorithmFamily.MACHINE_LEARNING,
        AlgorithmStatus.FUTURE,
        "Política aprendida para posición/orientación/selección de contenedor.",
        deterministic=False,
        supports_random_seed=True,
        limitations=["Requiere dataset, simulador, modelo entrenado y validación estricta"],
    ),
]
