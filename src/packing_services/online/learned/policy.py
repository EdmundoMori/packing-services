"""Política aprendida: puntúa todas las opciones legales del paso y elige."""

from __future__ import annotations

from collections.abc import Sequence

from ...domain.models import ConstraintFlags, Item
from ..features import encode_option
from ..session import ExtremePointOnlineSession
from ..types import StepOption
from .backends import ScoreBackend, load_backend


class LearnedPlacementPolicy:
    """No reordena fuera del buffer; no pisa la máscara del validador."""

    def __init__(self, backend: ScoreBackend) -> None:
        self.backend = backend

    @classmethod
    def from_path(cls, model_path: object) -> LearnedPlacementPolicy:
        return cls(load_backend(model_path))

    def decide(
        self,
        options: Sequence[StepOption],
        *,
        preview: Sequence[Item],
        remaining_count: int,
        session: ExtremePointOnlineSession,
        constraints: ConstraintFlags,
        mask,
    ) -> StepOption | None:
        if not options:
            return None
        rows = [
            encode_option(
                opt,
                session=session,
                preview=preview,
                remaining_count=remaining_count,
            )
            for opt in options
        ]
        scores = self.backend.score(rows)
        best_i = 0
        best_key = (scores[0], -options[0].buffer_index)
        for i, score in enumerate(scores[1:], start=1):
            key = (score, -options[i].buffer_index)
            if key > best_key:
                best_key = key
                best_i = i
        return options[best_i]
