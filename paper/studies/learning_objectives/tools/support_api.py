"""Puntos de entrada únicos hacia el contrato de S.

Etiquetado, entrenamiento y despliegue deben importar estas funciones y no
reimplementar la selección.
"""

from __future__ import annotations

from candidate_support import (
    CONTRACT_NAME,
    SUPPORT_LIMIT,
    build_candidate_support,
    build_candidate_support_from_options,
    select_logit_index,
    select_within_support,
    support_identities,
)
from losses import (
    classification_loss,
    mean_state_loss,
    preference_loss,
    return_difference_loss,
)
from support_metrics import regret_from_logits, support_regret

# API estable
build_S = build_candidate_support
build_S_from_options = build_candidate_support_from_options
argmax_in_S = select_within_support
logit_tie_break = select_logit_index

__all__ = [
    "CONTRACT_NAME",
    "SUPPORT_LIMIT",
    "build_S",
    "build_S_from_options",
    "argmax_in_S",
    "logit_tie_break",
    "support_identities",
    "classification_loss",
    "preference_loss",
    "return_difference_loss",
    "mean_state_loss",
    "support_regret",
    "regret_from_logits",
]
