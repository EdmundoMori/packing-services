"""Adaptadores mínimos sobre ExtremePointOnlineSession (sin modificar src/)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packing_services.domain.geometry import Dimensions
from packing_services.domain.models import ConstraintFlags, Container, Item
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import PlacementCandidate

from geometry_contract import (
    AABBBox,
    AxisTriple,
    OrientedSizes,
    unique_orientation_orders,
)
from info_separation import PolicyObservation, RevealedBox


def constraints_geometry_only(*, allow_rotation: bool) -> ConstraintFlags:
    return ConstraintFlags(
        non_overlap=True,
        containment=True,
        allow_rotation=allow_rotation,
        max_weight=False,
        basic_stability=False,
        load_bearing=False,
        fragility=False,
        unloading_sequence=False,
    )


def build_empty_session(container: AxisTriple) -> ExtremePointOnlineSession:
    c = Container(
        id="bin0",
        length=container.length,
        width=container.width,
        height=container.height,
        max_weight=None,
    )
    return ExtremePointOnlineSession([c], selection="best_fit")


def rebuild_session_from_revealed(
    container: AxisTriple,
    revealed: list[RevealedBox],
    *,
    allow_rotation: bool,
) -> ExtremePointOnlineSession:
    """Reconstruye ocupación con cajas *realizadas* (no envolventes).

    Conserva identidades y poses; no recoloca buscando nuevas candidatas.
    Coste: O(n) commits secuenciales; EP regenerados por el motor al colocar.
    Limitación: el conjunto de extreme points puede diferir del historial online
    incremental si el orden de commits no coincide; aquí el orden es el de revelación.
    """
    session = build_empty_session(container)
    flags = constraints_geometry_only(allow_rotation=allow_rotation)
    for box in revealed:
        item = Item(
            id=box.item_id,
            length=box.realized_oriented_mm.length,
            width=box.realized_oriented_mm.width,
            height=box.realized_oriented_mm.height,
            weight=0.0,
            allowed_orientations="none",
        )
        # Colocación directa vía commit con candidata sintética (sin re-buscar).
        cand = PlacementCandidate(
            item_id=box.item_id,
            bin_index=0,
            container_id="bin0",
            position=_point(box.flb_mm),
            dimensions=Dimensions(*box.realized_oriented_mm.as_tuple()),
            rank_key=(0.0, 0.0, 0.0, 0.0),
            support_ratio=1.0,
        )
        # Verificar que la pose sigue siendo factible en el estado reconstruido.
        if not session.packer._feasible(
            session.states[0], cand.position, cand.dimensions, item, flags
        ):
            raise RuntimeError(
                f"bloqueo: rebuild no puede reinsertar {box.item_id} en FLB {box.flb_mm}; "
                "no se aproxima en silencio"
            )
        session.commit(cand, item)
    return session


def _point(flb: tuple[float, float, float]):
    from packing_services.domain.geometry import Position

    return Position(x=flb[0], y=flb[1], z=flb[2])


@dataclass(frozen=True)
class EnvelopeCandidate:
    flb_mm: tuple[float, float, float]
    orientation_order: tuple[int, int, int]
    nominal_oriented: AxisTriple
    margin_oriented: AxisTriple
    envelope: AxisTriple
    rank_key: tuple


class PolicySessionView:
    """Vista que el chooser puede usar: candidatas con envolvente, sin realizados ocultos."""

    def __init__(
        self,
        session: ExtremePointOnlineSession,
        *,
        allow_rotation: bool,
    ) -> None:
        self._session = session
        self._allow_rotation = allow_rotation
        self._flags = constraints_geometry_only(allow_rotation=allow_rotation)

    def list_envelope_candidates(
        self,
        observation: PolicyObservation,
    ) -> list[EnvelopeCandidate]:
        """Candidatas usando solo nominal + margen de la observación."""
        nominal = observation.current_nominal_mm
        margin = observation.margin_mm
        orders = (
            unique_orientation_orders(nominal)
            if self._allow_rotation
            else [(0, 1, 2)]
        )
        # Ítem auxiliar: dims = nominal (el motor usa `orientations` explícitas = envelopes).
        item = Item(
            id=observation.current_item_id,
            length=nominal.length,
            width=nominal.width,
            height=nominal.height,
            weight=0.0,
            allowed_orientations="all" if self._allow_rotation else "none",
        )
        envelope_dims: list[Dimensions] = []
        order_by_dims: dict[tuple[float, float, float], tuple[int, int, int]] = {}
        sizes_by_order: dict[tuple[int, int, int], OrientedSizes] = {}
        for order in orders:
            sized = OrientedSizes.from_catalogue(nominal, margin, order, realized=None)
            sizes_by_order[order] = sized
            key = sized.envelope.as_tuple()
            if key not in order_by_dims:
                order_by_dims[key] = order
                envelope_dims.append(Dimensions(*key))

        raw = self._session.candidates(item, self._flags, orientations=envelope_dims)
        out: list[EnvelopeCandidate] = []
        for cand in raw:
            env_key = (
                float(cand.dimensions.length),
                float(cand.dimensions.width),
                float(cand.dimensions.height),
            )
            order = order_by_dims[env_key]
            sized = sizes_by_order[order]
            flb = (
                float(cand.position.x),
                float(cand.position.y),
                float(cand.position.z),
            )
            out.append(
                EnvelopeCandidate(
                    flb_mm=flb,
                    orientation_order=order,
                    nominal_oriented=sized.nominal_oriented,
                    margin_oriented=sized.margin_oriented,
                    envelope=sized.envelope,
                    rank_key=tuple(cand.rank_key),
                )
            )
        out.sort(key=lambda c: (c.rank_key, c.flb_mm, c.orientation_order))
        return out


def revealed_to_aabb(revealed: list[RevealedBox]) -> list[AABBBox]:
    return [
        AABBBox(r.flb_mm, r.realized_oriented_mm) for r in revealed
    ]


def commit_realized(
    session: ExtremePointOnlineSession,
    *,
    item_id: str,
    flb_mm: tuple[float, float, float],
    realized_oriented: AxisTriple,
    allow_rotation: bool,
) -> None:
    flags = constraints_geometry_only(allow_rotation=False)
    item = Item(
        id=item_id,
        length=realized_oriented.length,
        width=realized_oriented.width,
        height=realized_oriented.height,
        weight=0.0,
        allowed_orientations="none",
    )
    cand = PlacementCandidate(
        item_id=item_id,
        bin_index=0,
        container_id="bin0",
        position=_point(flb_mm),
        dimensions=Dimensions(*realized_oriented.as_tuple()),
        rank_key=(0.0, 0.0, 0.0, 0.0),
        support_ratio=1.0,
    )
    if not session.packer._feasible(
        session.states[0], cand.position, cand.dimensions, item, flags
    ):
        raise RuntimeError(
            f"bloqueo: no se puede commit del realizado {item_id}; "
            "fallo geométrico debió detectarse antes"
        )
    session.commit(cand, item)


def capture_equivalence(
    session: ExtremePointOnlineSession,
    revealed: list[RevealedBox],
) -> dict[str, Any]:
    """Compara packed de la sesión con la lista revelada (identidad, pose, dims)."""
    packed = session.packed
    if len(packed) != len(revealed):
        return {"matches": False, "reason": "count_mismatch", "n_session": len(packed), "n_revealed": len(revealed)}
    for p, r in zip(packed, revealed):
        if p.item_id != r.item_id:
            return {"matches": False, "reason": "id_mismatch", "session": p.item_id, "revealed": r.item_id}
        flb = (float(p.position.x), float(p.position.y), float(p.position.z))
        if flb != r.flb_mm:
            return {"matches": False, "reason": "flb_mismatch", "session": flb, "revealed": r.flb_mm}
        dims = (
            float(p.orientation.length),
            float(p.orientation.width),
            float(p.orientation.height),
        )
        if dims != r.realized_oriented_mm.as_tuple():
            return {
                "matches": False,
                "reason": "dims_mismatch",
                "session": dims,
                "revealed": r.realized_oriented_mm.as_tuple(),
            }
    return {"matches": True}
