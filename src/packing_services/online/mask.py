"""Máscara de legalidad: validador propio + umbral de soporte opcional.

Las candidatas geométricas (EP) se filtran con las mismas comprobaciones de
error que ``PackingValidator`` (contención, solape, peso, orientación,
load-bearing). El soporte básico es filtro duro solo si se pide umbral > 0.
"""

from __future__ import annotations

from ..domain.geometry import EPS
from ..domain.models import ConstraintFlags, Item, PackingProblem
from ..validation.validator import PackingValidator
from .session import ExtremePointOnlineSession
from .types import PlacementCandidate


class ValidatorMask:
    """Decide si una candidata es legal *ahora* sobre el layout actual."""

    def __init__(
        self,
        problem: PackingProblem,
        *,
        min_support_ratio: float = 0.0,
        validator: PackingValidator | None = None,
    ) -> None:
        self.problem = problem
        self.min_support_ratio = max(0.0, float(min_support_ratio))
        self.validator = validator or PackingValidator(
            support_surface_ratio=self.min_support_ratio or 0.6
        )

    def allows(
        self,
        candidate: PlacementCandidate,
        item: Item,
        session: ExtremePointOnlineSession,
        constraints: ConstraintFlags,
    ) -> bool:
        if self.min_support_ratio > EPS and candidate.support_ratio + EPS < self.min_support_ratio:
            return False
        trial = list(session.packed) + [session.as_packed_item(candidate, item)]
        return not self.validator.rejects_trial(
            containers=self.problem.containers,
            items=self.problem.items,
            packed_items=trial,
            constraints=constraints,
        )
