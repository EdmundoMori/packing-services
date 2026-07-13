"""Tipos de violación y constructores auxiliares.

Centralizar los tipos como constantes evita strings inconsistentes entre el
validador, los tests y los consumidores de la API.
"""

from __future__ import annotations

from ..domain.enums import Severity
from ..domain.models import Violation


class ViolationType:
    """Identificadores canónicos de tipos de violación."""

    CONTAINMENT = "CONTAINMENT"
    OVERLAP = "OVERLAP"
    MAX_WEIGHT = "MAX_WEIGHT"
    INVALID_ORIENTATION = "INVALID_ORIENTATION"
    DUPLICATE_ITEM = "DUPLICATE_ITEM"
    UNKNOWN_ITEM = "UNKNOWN_ITEM"
    UNKNOWN_CONTAINER = "UNKNOWN_CONTAINER"
    UNPACKED_MISMATCH = "UNPACKED_MISMATCH"
    SUPPORT_SURFACE = "SUPPORT_SURFACE"
    LOAD_BEARING = "LOAD_BEARING"


def make_violation(
    type_: str,
    message: str,
    container_id: str | None = None,
    item_ids: list[str] | None = None,
    severity: Severity = Severity.ERROR,
) -> Violation:
    """Constructor breve de ``Violation`` con valores por defecto sensatos."""

    return Violation(
        type=type_,
        message=message,
        container_id=container_id,
        item_ids=item_ids or [],
        severity=severity,
    )
