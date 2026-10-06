"""Puente C07: metadato ``actor_eval_mode`` sin tocar ``episode_worker.py`` hasheado.

Uso futuro (no ejecuta packing aquí)::

    from capture_actor_eval_metadata_v1 import attach_from_policy
    document = capture_document(...)  # histórico
    attach_from_policy(document, chooser, is_actor_arm=(arm != "greedy"))
"""

from __future__ import annotations

from typing import Any

from capture_actor_eval_metadata_v1 import attach_from_policy, attach_actor_eval_mode


def finalize_capture_recipe_metadata(
    document: dict[str, Any],
    *,
    arm: str,
    chooser: Any,
) -> dict[str, Any]:
    """Asigna actor_eval_mode de forma explícita tras ``capture_document``."""

    return attach_from_policy(document, chooser, is_actor_arm=(arm != "greedy"))


__all__ = [
    "finalize_capture_recipe_metadata",
    "attach_from_policy",
    "attach_actor_eval_mode",
]
