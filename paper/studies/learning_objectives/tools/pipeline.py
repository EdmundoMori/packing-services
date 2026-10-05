"""Puntos de llamada de etiquetado, entrenamiento y despliegue.

Todas las rutas importan S desde support_api / candidate_support.
No hay una segunda implementación de la regla.
"""

from __future__ import annotations

from typing import Any, Sequence

from candidate_support import (
    CONTRACT_NAME,
    GeometryRecord,
    SUPPORT_LIMIT,
    build_candidate_support,
    build_candidate_support_from_options,
    select_logit_index,
    select_within_support,
    support_identities,
)
from losses import (
    TIE_COEFFICIENT,
    TIE_EPS,
    classification_loss,
    mean_state_loss,
    preference_loss,
    return_difference_loss,
)
from support_api import build_S, build_S_from_options

# Identidad de la fuente de verdad
SUPPORT_BUILDER = build_candidate_support
SUPPORT_BUILDER_FROM_OPTIONS = build_candidate_support_from_options
assert build_S is build_candidate_support
assert build_S_from_options is build_candidate_support_from_options


def labeling_select_support(options: Sequence[Any], greedy_option: Any, *, limit: int = SUPPORT_LIMIT) -> list[Any]:
    """Única vía de etiquetado para construir S desde opciones legales."""

    return SUPPORT_BUILDER_FROM_OPTIONS(options, greedy_option, limit=limit)


def deployment_select_action(
    options: Sequence[Any],
    greedy_option: Any,
    logits_for_support: Sequence[float],
    *,
    limit: int = SUPPORT_LIMIT,
) -> Any:
    """Única vía de despliegue: S y después argmax en S."""

    support = SUPPORT_BUILDER_FROM_OPTIONS(options, greedy_option, limit=limit)
    if len(support) != len(logits_for_support):
        raise ValueError("logits deben alinearse con S, no con la lista legal completa")
    index = select_logit_index(logits_for_support)
    return support[index]


def training_state_support_ids(labeled_alternatives: Sequence[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """Entrenamiento consume las identidades ya fijadas por el etiquetado con S."""

    return [tuple(row["action"]) for row in labeled_alternatives]


def loss_for_arm(arm: str, logits: Sequence[float], q_hats: Sequence[float]) -> float:
    if arm == "classification":
        return classification_loss(logits, q_hats)
    if arm == "preferences":
        return preference_loss(logits, q_hats, tie_coefficient=TIE_COEFFICIENT)
    if arm == "return_difference":
        return return_difference_loss(logits, q_hats)
    raise ValueError(f"brazo desconocido: {arm}")


__all__ = [
    "CONTRACT_NAME",
    "SUPPORT_LIMIT",
    "SUPPORT_BUILDER",
    "SUPPORT_BUILDER_FROM_OPTIONS",
    "GeometryRecord",
    "labeling_select_support",
    "deployment_select_action",
    "training_state_support_ids",
    "loss_for_arm",
    "mean_state_loss",
    "select_within_support",
    "support_identities",
    "TIE_EPS",
    "TIE_COEFFICIENT",
]
