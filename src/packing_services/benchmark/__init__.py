"""Utilidades de benchmark: perfiles estándar por tipo de problema."""

from .profiles import (
    DEFAULT_PROFILE_BY_PROBLEM,
    list_profiles,
    profile_engine_defs,
    resolve_profile_engines,
)

__all__ = [
    "DEFAULT_PROFILE_BY_PROBLEM",
    "list_profiles",
    "profile_engine_defs",
    "resolve_profile_engines",
]
