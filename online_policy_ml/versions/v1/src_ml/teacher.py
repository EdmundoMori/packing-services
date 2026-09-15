"""Maestro P2O: elige una candidata YA legal. En producción el modelo no usa esto."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from packing_services.domain.models import ConstraintFlags, Item
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import PlacementCandidate, StepOption

from config import TEACHER_NAME

POSE_TOL_MM = 1.0


def privileged_volume_ep_index(options: Sequence[StepOption]) -> int | None:
    """Ítem de mayor volumen en el buffer; pose EP de menor rank_key."""

    if not options:
        return None
    best_i = 0
    best_key = _option_key(options[0])
    for i, opt in enumerate(options[1:], start=1):
        key = _option_key(opt)
        if key < best_key:
            best_key = key
            best_i = i
    return best_i


def receding_horizon_ep_index(
    options: Sequence[StepOption],
    *,
    remaining: Sequence[Item],
    session: ExtremePointOnlineSession,
    constraints: ConstraintFlags,
    mask: Any,
) -> int | None:
    """Packea el resto con volume_desc y proyecta sobre el buffer. Fallback: volumen."""

    if not options:
        return None
    buffer_ids = {opt.item.id for opt in options}
    snap = session.snapshot()
    lstar: list[tuple[str, PlacementCandidate]] = []
    try:
        leftover = sorted(remaining, key=lambda it: (-float(it.volume), it.id))
        while leftover:
            chosen_item = None
            chosen_cand = None
            for item in leftover:
                legal = [
                    cand
                    for cand in session.candidates(item, constraints)
                    if mask.allows(cand, item, session, constraints)
                ]
                if not legal:
                    continue
                chosen_cand = min(
                    legal,
                    key=lambda c: (c.rank_key, c.bin_index, c.position.as_tuple()),
                )
                chosen_item = item
                break
            if chosen_item is None or chosen_cand is None:
                break
            session.commit(chosen_cand, chosen_item)
            lstar.append((chosen_item.id, chosen_cand))
            leftover = [it for it in leftover if it.id != chosen_item.id]
            if buffer_ids.issubset({iid for iid, _ in lstar}):
                break
    finally:
        session.restore(snap)

    for item_id, cand in lstar:
        matches = [i for i, opt in enumerate(options) if opt.item.id == item_id]
        if not matches:
            continue
        exact = [
            i
            for i in matches
            if _pose_dist(options[i].candidate, cand) <= POSE_TOL_MM
            and options[i].candidate.bin_index == cand.bin_index
            and (
                options[i].candidate.dimensions.length,
                options[i].candidate.dimensions.width,
                options[i].candidate.dimensions.height,
            )
            == (cand.dimensions.length, cand.dimensions.width, cand.dimensions.height)
        ]
        if exact:
            return exact[0]
        return min(matches, key=lambda i: _pose_dist(options[i].candidate, cand))
    return privileged_volume_ep_index(options)


def label_index(
    options: Sequence[StepOption],
    teacher: str = TEACHER_NAME,
    **kwargs: Any,
) -> int | None:
    if teacher == "privileged_volume_ep":
        return privileged_volume_ep_index(options)
    if teacher == "receding_horizon_ep":
        return receding_horizon_ep_index(options, **kwargs)
    raise ValueError(f"maestro no soportado: {teacher}")


def _option_key(opt: StepOption) -> tuple:
    return (-float(opt.item.volume), opt.candidate.rank_key, opt.buffer_index)


def _pose_dist(a: PlacementCandidate, b: PlacementCandidate) -> float:
    return (
        abs(a.position.x - b.position.x)
        + abs(a.position.y - b.position.y)
        + abs(a.position.z - b.position.z)
    )
