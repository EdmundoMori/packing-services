"""Métricas comunes recalculables desde cualquier solución.

Las métricas se derivan de la solución (ítems empacados/no empacados) y de la
instancia (contenedores/ítems), de modo que cualquier motor externo o interno
produce cifras comparables. Esto ataca directamente la brecha de "comparación
no homogénea" identificada en el estado del arte.
"""

from __future__ import annotations

from ..domain.models import (
    Container,
    Item,
    Metrics,
    PackedItem,
    UnpackedItem,
)


def _orientation_volume(item: PackedItem) -> float:
    o = item.orientation
    return o.length * o.width * o.height


def compute_metrics(
    containers: list[Container],
    items: list[Item],
    packed_items: list[PackedItem],
    unpacked_items: list[UnpackedItem],
    constraint_violations: int = 0,
    execution_time_seconds: float = 0.0,
) -> Metrics:
    """Calcula el conjunto de métricas comunes.

    - ``volume_utilization``: volumen empacado / volumen de contenedores usados.
    - ``waste_volume``: 1 - volume_utilization (fracción de espacio desperdiciado
      en los contenedores efectivamente usados).
    - ``containers_used``: nº de contenedores distintos con al menos un ítem.
    """

    total_item_volume = sum(it.volume for it in items)
    packed_volume = sum(_orientation_volume(p) for p in packed_items)

    used_container_ids = {p.container_id for p in packed_items}
    containers_used = len(used_container_ids)
    used_container_volume = sum(
        c.volume for c in containers if c.id in used_container_ids
    )

    volume_utilization = (
        packed_volume / used_container_volume if used_container_volume > 0 else 0.0
    )
    waste_volume = 1.0 - volume_utilization if used_container_volume > 0 else 0.0

    loaded_weight = sum(p.weight for p in packed_items)
    unpacked_volume = max(0.0, total_item_volume - packed_volume)

    return Metrics(
        volume_utilization=round(volume_utilization, 6),
        waste_volume=round(waste_volume, 6),
        containers_used=containers_used,
        items_packed=len(packed_items),
        items_unpacked=len(unpacked_items),
        packed_volume=round(packed_volume, 6),
        unpacked_volume=round(unpacked_volume, 6),
        total_item_volume=round(total_item_volume, 6),
        loaded_weight=round(loaded_weight, 6),
        execution_time_seconds=round(execution_time_seconds, 6),
        constraint_violations=constraint_violations,
    )
