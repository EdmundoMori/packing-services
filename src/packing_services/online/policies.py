"""Políticas enchufables del bucle online.

La heurística greedy elige la candidata de menor ``rank_key`` (EP best-fit/BLB)
y, si hay lookahead, prioriza colocaciones que dejen hueco a los ítems visibles.
La política aprendida implementa el mismo ``decide`` sobre todas las opciones
del buffer; el bucle no vuelve a desempatar con greedy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..domain.models import ConstraintFlags, Item
from .session import ExtremePointOnlineSession
from .types import PlacementCandidate, StepOption


class PlacementPolicy(Protocol):
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
        """Elige un par (ítem, candidata) legal o ``None``."""


class GreedyBestFitPolicy:
    """Política determinista: score EP, desempate por lookahead de la ventana ``p``."""

    def choose(
        self,
        item: Item,
        legal: Sequence[PlacementCandidate],
        *,
        preview: Sequence[Item],
        session: ExtremePointOnlineSession,
        constraints: ConstraintFlags,
        mask,
    ) -> PlacementCandidate | None:
        if not legal:
            return None
        others = [it for it in preview if it.id != item.id]
        best: PlacementCandidate | None = None
        best_key: tuple | None = None
        for candidate in legal:
            look = 0
            if others:
                look = _preview_fit_count(
                    session, candidate, item, others, constraints, mask
                )
            key = (-look, candidate.rank_key)
            if best_key is None or key < best_key:
                best_key = key
                best = candidate
        return best

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
        del remaining_count
        if not options:
            return None
        grouped: dict[str, list[StepOption]] = {}
        order: list[str] = []
        for opt in options:
            if opt.item.id not in grouped:
                grouped[opt.item.id] = []
                order.append(opt.item.id)
            grouped[opt.item.id].append(opt)

        best_opt: StepOption | None = None
        best_key: tuple | None = None
        for item_id in order:
            group = grouped[item_id]
            item = group[0].item
            legal = [g.candidate for g in group]
            chosen = self.choose(
                item,
                legal,
                preview=preview,
                session=session,
                constraints=constraints,
                mask=mask,
            )
            if chosen is None:
                continue
            match = next(g for g in group if g.candidate == chosen)
            others = [it for it in preview if it.id != item.id]
            look = 0
            if others:
                look = _preview_fit_count(
                    session, chosen, item, others, constraints, mask
                )
            key = (-look, chosen.rank_key, match.buffer_index)
            if best_key is None or key < best_key:
                best_key = key
                best_opt = match
        return best_opt


def _preview_fit_count(
    session: ExtremePointOnlineSession,
    candidate: PlacementCandidate,
    item: Item,
    others: Sequence[Item],
    constraints: ConstraintFlags,
    mask,
) -> int:
    """Cuántos ítems de la ventana siguen teniendo al menos una candidata legal."""

    snap = session.snapshot()
    try:
        session.commit(candidate, item)
        count = 0
        for nxt in others:
            legal = [
                cand
                for cand in session.candidates(nxt, constraints)
                if mask.allows(cand, nxt, session, constraints)
            ]
            if legal:
                count += 1
        return count
    finally:
        session.restore(snap)
