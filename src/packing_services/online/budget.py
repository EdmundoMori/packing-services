"""Presupuesto de información del packing online (continuo p / s).

No es un producto O3DBP: O3DBP-*p*-*s* es un punto de este continuo.

- ``observe_p``: cuántos ítems próximos puede ver la política (incluido el actual).
- ``select_s``: cuántos ítems al frente de la cola puede elegir para colocar ahora.

``p=s=1`` es online estricto (un ítem, irrevocable). ``p=3, s=2`` es el régimen
típico de la cinta / leaderboard BED-BPP.
"""

from __future__ import annotations

from dataclasses import dataclass


def _at_least_one(value: object, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


@dataclass(frozen=True)
class InformationBudget:
    """Ventana de observación ``p`` y buffer de selección ``s``."""

    observe_p: int = 1
    select_s: int = 1

    @classmethod
    def from_parameters(cls, parameters: dict | None) -> InformationBudget:
        params = parameters or {}
        return cls(
            observe_p=_at_least_one(params.get("lookahead_p", 1), 1),
            select_s=_at_least_one(params.get("select_s", 1), 1),
        )

    def window(self, remaining_count: int) -> tuple[int, int]:
        """``(s, p)`` recortados a lo que queda en cola.

        Siempre se observan al menos los ``s`` seleccionables (no se elige a
        ciegas un ítem del buffer). ``p > s`` añade lookahead más allá del buffer.
        """

        n = max(0, remaining_count)
        select_s = min(self.select_s, n)
        observe_p = min(max(self.observe_p, select_s), n)
        return select_s, observe_p
