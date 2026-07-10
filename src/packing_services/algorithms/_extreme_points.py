"""Motor de heurística por Puntos Extremos (Extreme Points).

Basado en la idea de Crainic, Perboli y Tadei (2008): en lugar de generar
candidatos solo desde las esquinas del último ítem, se mantiene una **lista
persistente de puntos extremos (EP)** por contenedor. Tras colocar un ítem se
generan nuevos EP proyectando sus caras sobre las superficies existentes, y se
eliminan los EP que quedan cubiertos.

Para colocar un ítem se prueban todos los EP y orientaciones factibles y se
elige según una estrategia:

- ``"blb"``: el EP más bottom-left-back (menor z, y, x). Usado por
  ``extreme_points_3d``.
- ``"best_fit"``: la colocación que maximiza el área de contacto con paredes y
  otras cajas (mejor "encaje"). Usado por ``best_fit_decreasing_3d``.

Esta variante es una simplificación fiel: proyecta en el eje vertical y usa
contacto de caras, pero no implementa todas las proyecciones del algoritmo
original. No garantiza optimalidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import SortStrategy
from ..domain.geometry import (
    EPS,
    AABB,
    Dimensions,
    Position,
    face_contact_area,
    fits_within,
    is_interior_point,
    overlaps,
    unique_orientations,
)
from ..domain.models import (
    Container,
    Item,
    Orientation,
    PackedItem,
    PackingProblem,
    Point3D,
    UnpackedItem,
)
from ._constructive import _sort_key


@dataclass
class _BinState:
    container: Container
    placed: list[AABB] = field(default_factory=list)
    extreme_points: list[Position] = field(default_factory=list)
    loaded_weight: float = 0.0

    def __post_init__(self) -> None:
        if not self.extreme_points:
            self.extreme_points = [Position(0.0, 0.0, 0.0)]


def _support_z(x0: float, y0: float, x1: float, y1: float, placed: list[AABB]) -> float:
    """Altura de apoyo para una huella [x0,x1]x[y0,y1]: mayor techo debajo, o 0."""

    best = 0.0
    for box in placed:
        bx0, by0, _ = box.min_corner
        bx1, by1, bz1 = box.max_corner
        overlap_x = min(x1, bx1) - max(x0, bx0)
        overlap_y = min(y1, by1) - max(y0, by0)
        if overlap_x > EPS and overlap_y > EPS:
            best = max(best, bz1)
    return best


def _generate_extreme_points(box: AABB, placed_before: list[AABB]) -> list[Position]:
    """Genera nuevos EP tras colocar ``box`` (proyectando en vertical)."""

    x0, y0, z0 = box.min_corner
    x1, y1, z1 = box.max_corner

    # Puntos "crudos" a la derecha (+x), al frente (+y) y encima (+z).
    top = Position(x0, y0, z1)

    # Proyección vertical: el vecino a la derecha/al frente reposa sobre la
    # superficie que haya debajo en esa franja (o el suelo, z=0).
    right_z = _support_z(x1, y0, x1 + EPS, y1, placed_before)
    front_z = _support_z(x0, y1, x1, y1 + EPS, placed_before)

    candidates = [
        Position(x1, y0, right_z),  # derecha, proyectado a su apoyo
        Position(x0, y1, front_z),  # frente, proyectado a su apoyo
        Position(x1, y0, z0),       # derecha al mismo nivel base
        Position(x0, y1, z0),       # frente al mismo nivel base
        top,                        # encima del ítem
    ]
    return candidates


class ExtremePointPacker:
    """Empaquetador constructivo basado en puntos extremos."""

    def __init__(
        self,
        sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC,
        selection: str = "blb",
    ) -> None:
        self.sort_strategy = sort_strategy
        self.selection = selection

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation

        states = [_BinState(container=c) for c in problem.containers]
        ordered = sorted(problem.items, key=lambda it: _sort_key(it, self.sort_strategy))

        packed: list[PackedItem] = []
        unpacked: list[UnpackedItem] = []

        for item in ordered:
            orientations = unique_orientations(
                item.dimensions, allow_rotation and item.allow_rotation
            )
            placement = self._best_placement(item, states, orientations, constraints)
            if placement is None:
                unpacked.append(
                    UnpackedItem(
                        item_id=item.id,
                        reason="No se encontró punto extremo factible",
                    )
                )
                continue

            bin_index, position, dims = placement
            self._place(states[bin_index], position, dims, item)
            packed.append(
                PackedItem(
                    item_id=item.id,
                    container_id=states[bin_index].container.id,
                    position=Point3D(x=position.x, y=position.y, z=position.z),
                    orientation=Orientation(
                        length=dims.length, width=dims.width, height=dims.height
                    ),
                    weight=item.weight,
                )
            )

        return packed, unpacked

    # ------------------------------------------------------------------ #

    def _best_placement(self, item, states, orientations, constraints):
        best = None
        best_key = None
        for bin_index, state in enumerate(states):
            for position in state.extreme_points:
                for dims in orientations:
                    if not self._feasible(state, position, dims, item, constraints):
                        continue
                    box = AABB(position=position, dimensions=dims)
                    key = self._score(box, state, constraints)
                    if best_key is None or key < best_key:
                        best_key = key
                        best = (bin_index, position, dims)
        return best

    def _feasible(self, state, position, dims, item, constraints) -> bool:
        box = AABB(position=position, dimensions=dims)
        if constraints.containment and not fits_within(box, state.container.dimensions):
            return False
        if (
            constraints.max_weight
            and state.container.max_weight is not None
            and state.loaded_weight + item.weight > state.container.max_weight + EPS
        ):
            return False
        if constraints.non_overlap:
            for placed in state.placed:
                if overlaps(box, placed):
                    return False
        return True

    def _score(self, box: AABB, state: _BinState, constraints) -> tuple:
        """Clave de selección (menor es mejor)."""

        pos = box.position
        blb = (round(pos.z, 6), round(pos.y, 6), round(pos.x, 6))
        if self.selection == "best_fit":
            contact = self._contact_score(box, state)
            # Mayor contacto es mejor -> negamos para ordenar ascendente.
            return (-round(contact, 6),) + blb
        return blb  # bottom-left-back puro

    def _contact_score(self, box: AABB, state: _BinState) -> float:
        x0, y0, z0 = box.min_corner
        x1, y1, z1 = box.max_corner
        c = state.container.dimensions
        score = 0.0
        # Contacto con paredes y suelo del contenedor.
        if x0 <= EPS:
            score += (y1 - y0) * (z1 - z0)
        if abs(x1 - c.length) <= EPS:
            score += (y1 - y0) * (z1 - z0)
        if y0 <= EPS:
            score += (x1 - x0) * (z1 - z0)
        if abs(y1 - c.width) <= EPS:
            score += (x1 - x0) * (z1 - z0)
        if z0 <= EPS:
            score += (x1 - x0) * (y1 - y0)
        if abs(z1 - c.height) <= EPS:
            score += (x1 - x0) * (y1 - y0)
        # Contacto con cajas ya colocadas.
        for placed in state.placed:
            score += face_contact_area(box, placed)
        return score

    def _place(self, state: _BinState, position: Position, dims: Dimensions, item: Item):
        box = AABB(position=position, dimensions=dims)
        placed_before = list(state.placed)
        state.placed.append(box)
        state.loaded_weight += item.weight

        # Quitar el EP usado.
        state.extreme_points = [
            ep for ep in state.extreme_points if ep.as_tuple() != position.as_tuple()
        ]

        # Añadir nuevos EP válidos (dentro del contenedor y no duplicados).
        for cand in _generate_extreme_points(box, placed_before):
            if self._valid_new_ep(cand, state):
                state.extreme_points.append(cand)

        # Eliminar EP que hayan quedado cubiertos por la nueva caja.
        state.extreme_points = [
            ep
            for ep in state.extreme_points
            if not is_interior_point(ep.as_tuple(), box)
        ]

    def _valid_new_ep(self, cand: Position, state: _BinState) -> bool:
        c = state.container.dimensions
        if not (
            -EPS <= cand.x <= c.length + EPS
            and -EPS <= cand.y <= c.width + EPS
            and -EPS <= cand.z <= c.height + EPS
        ):
            return False
        if any(ep.as_tuple() == cand.as_tuple() for ep in state.extreme_points):
            return False
        if any(is_interior_point(cand.as_tuple(), b) for b in state.placed):
            return False
        return True
