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


def restrict_to_open_bin(
    options: Sequence[StepOption],
    session: ExtremePointOnlineSession,
) -> list[StepOption]:
    """Disciplina first-fit: agotar los contenedores abiertos antes de abrir otro.

    Devuelve solo las opciones del contenedor abierto de índice más bajo que
    todavía admita algo. Si ninguno de los abiertos admite nada, deja las del
    contenedor disponible más bajo, que es el que toca abrir.
    """

    by_bin: dict[int, list[StepOption]] = {}
    for option in options:
        by_bin.setdefault(option.candidate.bin_index, []).append(option)
    if not by_bin:
        return []

    opened = {index for index, state in enumerate(session.states) if state.placed}
    for index in sorted(by_bin):
        if index in opened:
            return by_bin[index]
    return by_bin[min(by_bin)]


class ConsolidatingPolicy:
    """Impone disciplina de contenedor sobre otra política, sin modificarla.

    El encoder v1 ya expone lo necesario para decidir esto: la ocupación del
    contenedor de cada candidata (``used_height_n``, ``loaded_weight_n``) y el
    total colocado en la sesión (``n_packed_n``). Lo que nunca ocurrió en
    entrenamiento es el caso. Todas las instancias P2O tenían un solo
    contenedor, así que un bin vacío coincidía siempre con el inicio del
    episodio; el modelo aprendió a leer "pallet vacío" como "coloca libremente"
    y con dos pallets disponibles reparte la carga en lugar de consolidar.

    Esta envolvente no toca el modelo, el encoder ni el checkpoint: retira de
    la mesa las candidatas del siguiente contenedor mientras el actual admita
    algo. La política interna sigue eligiendo la pose.
    """

    def __init__(self, inner: PlacementPolicy) -> None:
        self.inner = inner

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
        return self.inner.decide(
            restrict_to_open_bin(options, session),
            preview=preview,
            remaining_count=remaining_count,
            session=session,
            constraints=constraints,
            mask=mask,
        )


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
