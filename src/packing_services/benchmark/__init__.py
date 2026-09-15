"""Utilidades de benchmark: perfiles estándar por tipo de problema."""

from .holdout_offline_online import (
    HOLDOUT_ENGINES,
    HOLDOUT_ORDER_IDS,
    run_holdout_offline_online,
    run_holdout_order,
    summarize_holdout,
)
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
    "HOLDOUT_ENGINES",
    "HOLDOUT_ORDER_IDS",
    "JOINT_ENGINES",
    "JOINT_PROBLEM_TYPES",
    "list_profiles",
    "profile_engine_defs",
    "resolve_profile_engines",
    "run_holdout_offline_online",
    "run_holdout_order",
    "run_joint_single_container",
    "summarize_holdout",
]
