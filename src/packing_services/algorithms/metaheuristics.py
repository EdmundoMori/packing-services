"""Catálogo (fases futuras): online packing y ML/DRL.

Las metaheurísticas 3D-BPP están implementadas en ``metaheuristic_3d_bpp.py``.
"""

from __future__ import annotations

from ..domain.enums import AlgorithmFamily, AlgorithmStatus, ProblemType
from ._catalog_helpers import catalog_metadata

_PROBLEMS = [ProblemType.THREE_D_BPP]


CATALOG = [
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
