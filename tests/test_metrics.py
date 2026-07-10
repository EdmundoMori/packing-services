"""Tests del cálculo de métricas comunes."""

from __future__ import annotations

from packing_services.domain.models import (
    Container,
    Item,
    Orientation,
    PackedItem,
    Point3D,
    UnpackedItem,
)
from packing_services.metrics.metrics import compute_metrics


def test_full_utilization():
    container = Container(id="C1", length=10, width=10, height=10)
    items = [Item(id="I1", length=10, width=10, height=10, weight=5)]
    packed = [
        PackedItem(
            item_id="I1",
            container_id="C1",
            position=Point3D(x=0, y=0, z=0),
            orientation=Orientation(length=10, width=10, height=10),
            weight=5,
        )
    ]
    metrics = compute_metrics([container], items, packed, [])
    assert metrics.volume_utilization == 1.0
    assert metrics.waste_volume == 0.0
    assert metrics.containers_used == 1
    assert metrics.items_packed == 1
    assert metrics.loaded_weight == 5


def test_partial_and_unpacked():
    container = Container(id="C1", length=10, width=10, height=10)
    items = [
        Item(id="I1", length=10, width=10, height=5, weight=5),
        Item(id="I2", length=10, width=10, height=5, weight=5),
    ]
    packed = [
        PackedItem(
            item_id="I1",
            container_id="C1",
            position=Point3D(x=0, y=0, z=0),
            orientation=Orientation(length=10, width=10, height=5),
            weight=5,
        )
    ]
    unpacked = [UnpackedItem(item_id="I2")]
    metrics = compute_metrics([container], items, packed, unpacked)
    assert metrics.volume_utilization == 0.5
    assert metrics.items_packed == 1
    assert metrics.items_unpacked == 1
    assert metrics.packed_volume == 500
    assert metrics.total_item_volume == 1000


def test_no_containers_used_when_nothing_packed():
    container = Container(id="C1", length=10, width=10, height=10)
    items = [Item(id="I1", length=10, width=10, height=10)]
    metrics = compute_metrics([container], items, [], [UnpackedItem(item_id="I1")])
    assert metrics.containers_used == 0
    assert metrics.volume_utilization == 0.0
