"""Adaptador para el motor externo ``py3dbp`` (enzoruiz/3dbinpacking).

Motor secundario / baseline para 3D Bin Packing en Python puro. Es el único
adaptador potencialmente ejecutable en esta versión, siempre que la librería
esté instalada (``pip install py3dbp``). Si no lo está, el adaptador declara su
metadata pero ``run`` lanza un error claro con instrucciones de instalación.

No se modifica el repositorio original: se traduce la entrada normalizada al API
de ``py3dbp`` y su salida de vuelta al formato normalizado.
"""

from __future__ import annotations

import importlib.util

from ..algorithms.base import build_solution
from ..algorithms.metadata import DEFAULT_METRICS, AlgorithmMetadata
from ..domain.enums import (
    AlgorithmFamily,
    AlgorithmStatus,
    Constraint,
    ProblemType,
)
from ..domain.models import (
    Orientation,
    PackedItem,
    PackingProblem,
    PackingSolution,
    Point3D,
    UnpackedItem,
)
from ..utils.timing import measure_time
from .base import ExternalAdapter

METADATA = AlgorithmMetadata(
    name="py3dbp_adapter",
    display_name="py3dbp Adapter (enzoruiz/3dbinpacking)",
    problem_types=[ProblemType.THREE_D_BPP, ProblemType.SINGLE_CONTAINER_LOADING],
    algorithm_family=AlgorithmFamily.ADAPTER,
    status=AlgorithmStatus.ADAPTER,
    description=(
        "Adaptador al baseline en Python py3dbp. Traduce la entrada normalizada "
        "a Bin/Item de py3dbp y su salida a posiciones y orientaciones "
        "normalizadas."
    ),
    deterministic=True,
    supports_random_seed=False,
    supports_time_limit=False,
    supports_rotation=True,
    supports_multi_container=True,
    supported_constraints=[
        Constraint.CONTAINMENT,
        Constraint.NON_OVERLAP,
        Constraint.MAX_WEIGHT,
        Constraint.ORIENTATION,
    ],
    unsupported_constraints=[
        Constraint.FRAGILITY,
        Constraint.LOAD_BEARING,
        Constraint.CENTER_OF_GRAVITY,
        Constraint.UNLOADING_SEQUENCE,
        Constraint.ADVANCED_STABILITY,
    ],
    parameters={
        "bigger_first": "Ordenar ítems mayores primero (bool, por defecto True)",
        "distribute_items": "Distribuir ítems entre bins (bool, por defecto True)",
        "number_of_decimals": "Precisión decimal de py3dbp (int, por defecto 3)",
    },
    metrics=DEFAULT_METRICS,
    limitations=[
        "Requiere la dependencia opcional py3dbp",
        "No soporta restricciones logísticas avanzadas",
    ],
    external_engine="py3dbp",
    external_language="Python",
    external_repository="https://github.com/enzoruiz/3dbinpacking",
)


class Py3dbpAdapter(ExternalAdapter):
    """Adaptador ejecutable si ``py3dbp`` está instalado."""

    metadata = METADATA
    unavailable_hint = (
        "La librería 'py3dbp' no está instalada. Instálala con "
        "`pip install py3dbp` (o `pip install .[py3dbp]`) para habilitar este "
        "adaptador."
    )

    def is_available(self) -> bool:
        return importlib.util.find_spec("py3dbp") is not None

    def _run_available(self, problem: PackingProblem) -> PackingSolution:
        from py3dbp import Bin, Item, Packer  # type: ignore

        params = problem.algorithm.parameters
        bigger_first = bool(params.get("bigger_first", True))
        distribute_items = bool(params.get("distribute_items", True))
        number_of_decimals = int(params.get("number_of_decimals", 3))

        packer = Packer()

        # Mapeo de ejes: length->width(x), width->height(y), height->depth(z).
        for container in problem.containers:
            packer.add_bin(
                Bin(
                    container.id,
                    container.length,
                    container.width,
                    container.height,
                    container.max_weight if container.max_weight is not None else 1e9,
                )
            )
        for item in problem.items:
            packer.add_item(
                Item(item.id, item.length, item.width, item.height, item.weight)
            )

        with measure_time() as elapsed:
            packer.pack(
                bigger_first=bigger_first,
                distribute_items=distribute_items,
                number_of_decimals=number_of_decimals,
            )

        packed_items, packed_ids = self._map_packed(packer)
        unpacked_items = self._map_unpacked(problem, packed_ids)

        return build_solution(
            problem=problem,
            metadata=self.metadata,
            packed_items=packed_items,
            unpacked_items=unpacked_items,
            execution_time_seconds=elapsed.seconds,
        )

    def _map_packed(self, packer) -> tuple[list[PackedItem], set[str]]:
        packed_items: list[PackedItem] = []
        packed_ids: set[str] = set()
        for b in packer.bins:
            for it in b.items:
                pos = [float(p) for p in it.position]
                dim = [float(d) for d in it.get_dimension()]
                packed_ids.add(it.name)
                packed_items.append(
                    PackedItem(
                        item_id=it.name,
                        container_id=b.name,
                        position=Point3D(x=pos[0], y=pos[1], z=pos[2]),
                        orientation=Orientation(
                            length=dim[0], width=dim[1], height=dim[2]
                        ),
                        weight=float(it.weight),
                    )
                )
        return packed_items, packed_ids

    def _map_unpacked(
        self, problem: PackingProblem, packed_ids: set[str]
    ) -> list[UnpackedItem]:
        return [
            UnpackedItem(item_id=item.id, reason="No colocado por py3dbp")
            for item in problem.items
            if item.id not in packed_ids
        ]
