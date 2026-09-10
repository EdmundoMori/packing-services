"""Utilidades de benchmark: perfiles estándar por tipo de problema."""

from .joint_single_container import (
    JOINT_ENGINES,
    JOINT_PROBLEM_TYPES,
    run_joint_single_container,
)
from .profiles import (
    DEFAULT_PROFILE_BY_PROBLEM,
    list_profiles,
    profile_engine_defs,
    resolve_profile_engines,
)

__all__ = [
    "DEFAULT_PROFILE_BY_PROBLEM",
    "JOINT_ENGINES",
    "JOINT_PROBLEM_TYPES",
    "list_profiles",
    "profile_engine_defs",
    "resolve_profile_engines",
    "run_joint_single_container",
]
