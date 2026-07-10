"""Motor constructivo común para heurísticas 3D-BPP.

Ambas heurísticas iniciales (``heuristic_3d_bpp_v1`` y
``first_fit_decreasing_3d``) comparten esta lógica: ordenar ítems, generar
posiciones candidatas a partir de los ítems ya colocados y validar
contención/solapamiento/peso antes de aceptar una colocación. Solo cambian la
estrategia de ordenamiento y la estrategia de selección de contenedor/posición.

Ninguna de estas heurísticas garantiza optimalidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import SortStrategy
from ..domain.geometry import (
    EPS,
    AABB,
    Dimensions,
    Position,
    fits_within,
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


@dataclass
class _ContainerState:
    """Estado de colocación de un contenedor durante la construcción."""

    container: Container
    placed: list[AABB] = field(default_factory=list)
    candidates: list[Position] = field(default_factory=list)
    loaded_weight: float = 0.0

    def __post_init__(self) -> None:
        if not self.candidates:
            self.candidates = [Position(0.0, 0.0, 0.0)]


def _sort_key(item: Item, strategy: SortStrategy):
    if strategy == SortStrategy.WEIGHT_DESC:
        return (-item.weight, -item.volume)
    if strategy == SortStrategy.LONGEST_DIM_DESC:
        return (-max(item.dimensions.as_tuple()), -item.volume)
    return (-item.volume, -item.weight)  # VOLUME_DESC por defecto


def _blb_key(position: Position) -> tuple[float, float, float]:
    """Orden bottom-left-back: menor z, luego y, luego x."""

    return (position.z, position.y, position.x)


def _generate_candidates(position: Position, dims: Dimensions) -> list[Position]:
    """Nuevas posiciones candidatas a partir de un ítem recién colocado."""

    return [
        Position(position.x + dims.length, position.y, position.z),
        Position(position.x, position.y + dims.width, position.z),
        Position(position.x, position.y, position.z + dims.height),
    ]


def _placement_is_feasible(
    state: _ContainerState,
    position: Position,
    dims: Dimensions,
    item_weight: float,
    check_weight: bool,
    check_overlap: bool,
    check_containment: bool,
) -> bool:
    """Valida contención, no solapamiento y peso para una colocación tentativa."""

    box = AABB(position=position, dimensions=dims)

    if check_containment and not fits_within(box, state.container.dimensions):
        return False

    if (
        check_weight
        and state.container.max_weight is not None
        and state.loaded_weight + item_weight > state.container.max_weight + EPS
    ):
        return False

    if check_overlap:
        for placed in state.placed:
            if overlaps(box, placed):
                return False

    return True


@dataclass
class _Placement:
    container_index: int
    position: Position
    dimensions: Dimensions


class ConstructivePacker:
    """Motor constructivo parametrizable.

    Parámetros:
      - ``sort_strategy``: cómo ordenar los ítems (volumen/peso/dimensión).
      - ``container_selection``: ``"first_fit"`` llena un contenedor antes de
        pasar al siguiente; ``"global_blb"`` elige globalmente la posición más
        bottom-left-back entre todos los contenedores.
    """

    def __init__(
        self,
        sort_strategy: SortStrategy = SortStrategy.VOLUME_DESC,
        container_selection: str = "global_blb",
    ) -> None:
        self.sort_strategy = sort_strategy
        self.container_selection = container_selection

    def pack(
        self, problem: PackingProblem
    ) -> tuple[list[PackedItem], list[UnpackedItem]]:
        constraints = problem.constraints
        allow_rotation = constraints.allow_rotation

        states = [_ContainerState(container=c) for c in problem.containers]
        ordered_items = sorted(
            problem.items, key=lambda it: _sort_key(it, self.sort_strategy)
        )

        packed: list[PackedItem] = []
        unpacked: list[UnpackedItem] = []

        for item in ordered_items:
            placement = self._find_placement(item, states, allow_rotation, constraints)
            if placement is None:
                unpacked.append(
                    UnpackedItem(
                        item_id=item.id,
                        reason="No se encontró posición factible en ningún contenedor",
                    )
                )
                continue

            self._apply_placement(states[placement.container_index], placement, item)
            packed.append(
                PackedItem(
                    item_id=item.id,
                    container_id=states[placement.container_index].container.id,
                    position=Point3D(
                        x=placement.position.x,
                        y=placement.position.y,
                        z=placement.position.z,
                    ),
                    orientation=Orientation(
                        length=placement.dimensions.length,
                        width=placement.dimensions.width,
                        height=placement.dimensions.height,
                    ),
                    weight=item.weight,
                )
            )

        return packed, unpacked

    # ------------------------------------------------------------------ #

    def _find_placement(
        self,
        item: Item,
        states: list[_ContainerState],
        allow_rotation: bool,
        constraints,
    ) -> _Placement | None:
        orientations = unique_orientations(
            item.dimensions, allow_rotation and item.allow_rotation
        )

        if self.container_selection == "first_fit":
            return self._first_fit(item, states, orientations, constraints)
        return self._global_blb(item, states, orientations, constraints)

    def _feasible_in_container(
        self, item: Item, state: _ContainerState, orientations, constraints
    ) -> tuple[Position, Dimensions] | None:
        """Primera posición factible en un contenedor, en orden BLB."""

        for position in sorted(state.candidates, key=_blb_key):
            for dims in orientations:
                if _placement_is_feasible(
                    state,
                    position,
                    dims,
                    item.weight,
                    check_weight=constraints.max_weight,
                    check_overlap=constraints.non_overlap,
                    check_containment=constraints.containment,
                ):
                    return position, dims
        return None

    def _first_fit(
        self, item, states, orientations, constraints
    ) -> _Placement | None:
        for idx, state in enumerate(states):
            found = self._feasible_in_container(item, state, orientations, constraints)
            if found is not None:
                return _Placement(idx, found[0], found[1])
        return None

    def _global_blb(
        self, item, states, orientations, constraints
    ) -> _Placement | None:
        best: _Placement | None = None
        best_key: tuple | None = None
        for idx, state in enumerate(states):
            found = self._feasible_in_container(item, state, orientations, constraints)
            if found is None:
                continue
            position, dims = found
            # Priorizar contenedores ya iniciados y posiciones bottom-left-back.
            key = (0 if state.placed else 1, idx) + _blb_key(position)
            if best_key is None or key < best_key:
                best_key = key
                best = _Placement(idx, position, dims)
        return best

    def _apply_placement(
        self, state: _ContainerState, placement: _Placement, item: Item
    ) -> None:
        box = AABB(position=placement.position, dimensions=placement.dimensions)
        state.placed.append(box)
        state.loaded_weight += item.weight

        # Consumir la candidata usada y añadir las nuevas generadas.
        state.candidates = [
            c
            for c in state.candidates
            if c.as_tuple() != placement.position.as_tuple()
        ]
        for cand in _generate_candidates(placement.position, placement.dimensions):
            if _within_container(cand, state.container) and not _duplicate(
                cand, state.candidates
            ):
                state.candidates.append(cand)


def _within_container(position: Position, container: Container) -> bool:
    return (
        -EPS <= position.x <= container.length + EPS
        and -EPS <= position.y <= container.width + EPS
        and -EPS <= position.z <= container.height + EPS
    )


def _duplicate(position: Position, existing: list[Position]) -> bool:
    return any(position.as_tuple() == e.as_tuple() for e in existing)
