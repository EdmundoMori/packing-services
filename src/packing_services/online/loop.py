"""Bucle de decisión online con presupuesto de información.

Cola en orden de llegada (``arrival_index`` / input). En cada paso:

1. Seleccionables = primeros ``s`` de la cola.
2. Preview = primeros ``p`` (lo que la política puede ver).
3. Candidatas (EP) → máscara (validador) → política.decide → commit irrevocable.
4. Si ninguno de los ``s`` cabe, se rechaza el más antiguo y se sigue.

El resto de ítems no se reordena. Offline no usa este bucle.
La política aprendida elige entre todas las opciones legales; el greedy no la pisa.
"""

from __future__ import annotations

from ..domain.enums import SortStrategy
from ..domain.models import PackedItem, PackingProblem, UnpackedItem
from .budget import InformationBudget
from .mask import ValidatorMask
from .policies import GreedyBestFitPolicy, PlacementPolicy
from .session import ExtremePointOnlineSession
from .types import StepOption


def run_online_loop(
    problem: PackingProblem,
    *,
    budget: InformationBudget | None = None,
    selection: str = "best_fit",
    min_support_ratio: float = 0.0,
    policy: PlacementPolicy | None = None,
) -> tuple[list[PackedItem], list[UnpackedItem]]:
    """Empaqueta ``problem.items`` en régimen online. No reordena fuera de ``s``."""

    from ..algorithms._constructive import order_items

    constraints = problem.constraints
    info = budget or InformationBudget()
    session = ExtremePointOnlineSession(problem.containers, selection=selection)
    mask = ValidatorMask(problem, min_support_ratio=min_support_ratio)
    chooser: PlacementPolicy = policy or GreedyBestFitPolicy()

    remaining = order_items(problem.items, SortStrategy.INPUT_ORDER)
    unpacked: list[UnpackedItem] = []

    while remaining:
        select_s, observe_p = info.window(len(remaining))
        selectable = remaining[:select_s]
        preview = remaining[:observe_p]

        options: list[StepOption] = []
        for buffer_index, item in enumerate(selectable):
            for cand in session.candidates(item, constraints):
                if mask.allows(cand, item, session, constraints):
                    options.append(
                        StepOption(
                            item=item,
                            candidate=cand,
                            buffer_index=buffer_index,
                        )
                    )

        chosen = chooser.decide(
            options,
            preview=preview,
            remaining_count=len(remaining),
            session=session,
            constraints=constraints,
            mask=mask,
        )

        if chosen is None:
            skipped = remaining.pop(0)
            unpacked.append(
                UnpackedItem(
                    item_id=skipped.id,
                    reason="No hay colocación legal con el presupuesto de información actual",
                )
            )
            continue

        session.commit(chosen.candidate, chosen.item)
        remaining = [it for it in remaining if it.id != chosen.item.id]

    return session.packed, unpacked
