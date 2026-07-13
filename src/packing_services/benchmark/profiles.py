"""Perfiles estándar de benchmark por tipo de problema.

Cada perfil define un conjunto de motores comparables (≥2) para el mismo
``problem_type``. Se pueden usar vía el campo ``profile`` de ``BenchmarkRequest``
o mediante los builders de ``notebooks/_shared/loaders.py``.
"""

from __future__ import annotations

from typing import Any

from ..domain.enums import ProblemType
from ..schemas.requests import BenchmarkEngineConfig

# Motores por perfil. Los parámetros se copian tal cual al request.
_PROFILE_ENGINES: dict[tuple[str, str], list[dict[str, Any]]] = {
    # --- 3D Bin Packing ---
    ("3D_BPP", "constructive"): [
        {"name": "heuristic_3d_bpp_v1", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "first_fit_decreasing_3d", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "extreme_points_3d", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "best_fit_decreasing_3d", "parameters": {"sort_strategy": "volume_desc"}},
        {
            "name": "py3dbp_adapter",
            "parameters": {"bigger_first": True, "distribute_items": True},
            "optional": True,
        },
    ],
    ("3D_BPP", "hybrid"): [
        {"name": "best_fit_decreasing_3d", "parameters": {"sort_strategy": "volume_desc"}},
        {
            "name": "solution_compaction",
            "parameters": {"base_algorithm": "best_fit_decreasing_3d", "compaction_passes": 3},
        },
        {
            "name": "constructive_plus_local_search",
            "parameters": {
                "base_algorithm": "best_fit_decreasing_3d",
                "compaction_passes": 3,
                "relocation_pass": True,
            },
        },
    ],
    # --- Container Loading ---
    ("CONTAINER_LOADING", "constructive"): [
        {"name": "single_container_constructive", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "weight_aware_container_loading", "parameters": {"sort_strategy": "weight_desc"}},
        {"name": "extreme_points_3d", "parameters": {"sort_strategy": "volume_desc"}},
    ],
    ("CONTAINER_LOADING", "improvement"): [
        {"name": "weight_aware_container_loading", "parameters": {"sort_strategy": "weight_desc"}},
        {
            "name": "solution_compaction",
            "parameters": {
                "base_algorithm": "weight_aware_container_loading",
                "compaction_passes": 3,
            },
        },
        {
            "name": "constructive_plus_local_search",
            "parameters": {
                "base_algorithm": "weight_aware_container_loading",
                "compaction_passes": 3,
                "relocation_pass": True,
            },
        },
    ],
    # --- Cartonization ---
    ("CARTONIZATION", "box_selection"): [
        {"name": "smallest_feasible_box", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "best_box_volume_utilization", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "first_fit_box", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "largest_feasible_box", "parameters": {"sort_strategy": "volume_desc"}},
    ],
    # --- Single Container Loading ---
    ("SINGLE_CONTAINER_LOADING", "constructive"): [
        {"name": "single_container_constructive", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "best_fit_decreasing_3d", "parameters": {"sort_strategy": "volume_desc"}},
        {"name": "first_fit_decreasing_3d", "parameters": {"sort_strategy": "volume_desc"}},
    ],
}

# Perfil recomendado por defecto si no se especifica otro.
DEFAULT_PROFILE_BY_PROBLEM: dict[str, str] = {
    "3D_BPP": "constructive",
    "CONTAINER_LOADING": "constructive",
    "CARTONIZATION": "box_selection",
    "SINGLE_CONTAINER_LOADING": "constructive",
}


def list_profiles(problem_type: ProblemType | str | None = None) -> list[dict[str, Any]]:
    """Lista perfiles disponibles, opcionalmente filtrados por tipo de problema."""

    pt_filter = problem_type.value if isinstance(problem_type, ProblemType) else problem_type
    profiles: list[dict[str, Any]] = []
    for (pt, name), engines in sorted(_PROFILE_ENGINES.items()):
        if pt_filter and pt != pt_filter:
            continue
        profiles.append(
            {
                "problem_type": pt,
                "profile": name,
                "engines_count": len(engines),
                "engines": [e["name"] for e in engines],
                "is_default": DEFAULT_PROFILE_BY_PROBLEM.get(pt) == name,
            }
        )
    return profiles


def profile_engine_defs(
    problem_type: ProblemType | str,
    profile: str,
) -> list[dict[str, Any]]:
    """Devuelve las definiciones de motores de un perfil."""

    pt = problem_type.value if isinstance(problem_type, ProblemType) else problem_type
    key = (pt, profile)
    if key not in _PROFILE_ENGINES:
        available = sorted({p for p, _ in _PROFILE_ENGINES if p == pt})
        raise ValueError(
            f"Perfil de benchmark desconocido: {pt}/{profile}. "
            f"Perfiles para {pt}: {available}"
        )
    return [dict(e) for e in _PROFILE_ENGINES[key]]


def resolve_profile_engines(
    problem_type: ProblemType | str,
    profile: str | None = None,
    *,
    registry=None,
) -> list[BenchmarkEngineConfig]:
    """Resuelve un perfil a ``BenchmarkEngineConfig``, omitiendo motores opcionales no disponibles."""

    pt = problem_type.value if isinstance(problem_type, ProblemType) else problem_type
    prof = profile or DEFAULT_PROFILE_BY_PROBLEM.get(pt)
    if not prof:
        raise ValueError(f"No hay perfil por defecto para problem_type={pt}")

    if registry is None:
        from ..algorithms.registry import get_default_registry

        registry = get_default_registry()

    configs: list[BenchmarkEngineConfig] = []
    for engine in profile_engine_defs(pt, prof):
        if engine.get("optional") and not registry.is_executable(engine["name"]):
            continue
        meta = registry.get_metadata(engine["name"])
        if ProblemType(pt) not in meta.problem_types:
            continue
        configs.append(
            BenchmarkEngineConfig(
                name=engine["name"],
                parameters=engine.get("parameters", {}),
            )
        )
    if len(configs) < 2:
        raise ValueError(
            f"El perfil {pt}/{prof} debe tener al menos 2 motores ejecutables; "
            f"obtuvo {len(configs)}"
        )
    return configs
