"""Tests del validador geométrico."""

from __future__ import annotations

from packing_services.domain.models import (
    Container,
    ConstraintFlags,
    Item,
    Orientation,
    PackedItem,
    Point3D,
)
from packing_services.validation.validator import PackingValidator
from packing_services.validation.violations import ViolationType


def _container(max_weight=1000):
    return Container(id="C1", length=100, width=100, height=100, max_weight=max_weight)


def _item(id_, l=40, w=40, h=40, weight=10):
    return Item(id=id_, length=l, width=w, height=h, weight=weight)


def _packed(id_, x, y, z, l=40, w=40, h=40, weight=10, container="C1"):
    return PackedItem(
        item_id=id_,
        container_id=container,
        position=Point3D(x=x, y=y, z=z),
        orientation=Orientation(length=l, width=w, height=h),
        weight=weight,
    )


def test_valid_solution():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1"), _item("I2")],
        packed_items=[_packed("I1", 0, 0, 0), _packed("I2", 40, 0, 0)],
    )
    assert report.is_valid
    assert report.violations == []


def test_overlap_detected():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1"), _item("I2")],
        packed_items=[_packed("I1", 0, 0, 0), _packed("I2", 20, 20, 0)],
    )
    assert not report.is_valid
    assert any(v.type == ViolationType.OVERLAP for v in report.violations)


def test_containment_violation():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1")],
        packed_items=[_packed("I1", 80, 0, 0)],  # 80+40 > 100
    )
    assert not report.is_valid
    assert any(v.type == ViolationType.CONTAINMENT for v in report.violations)


def test_max_weight_violation():
    report = PackingValidator().validate(
        containers=[_container(max_weight=15)],
        items=[_item("I1", weight=10), _item("I2", weight=10)],
        packed_items=[
            _packed("I1", 0, 0, 0, weight=10),
            _packed("I2", 40, 0, 0, weight=10),
        ],
    )
    assert not report.is_valid
    assert any(v.type == ViolationType.MAX_WEIGHT for v in report.violations)


def test_invalid_orientation():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1", l=40, w=40, h=40)],
        packed_items=[_packed("I1", 0, 0, 0, l=50, w=40, h=40)],  # 50 no es dim original
    )
    assert not report.is_valid
    assert any(v.type == ViolationType.INVALID_ORIENTATION for v in report.violations)


def test_duplicate_item():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1")],
        packed_items=[_packed("I1", 0, 0, 0), _packed("I1", 40, 0, 0)],
    )
    assert any(v.type == ViolationType.DUPLICATE_ITEM for v in report.violations)


def test_unpacked_mismatch_missing():
    report = PackingValidator().validate(
        containers=[_container()],
        items=[_item("I1"), _item("I2")],
        packed_items=[_packed("I1", 0, 0, 0)],
        expected_unpacked_ids=[],  # I2 no está ni empacado ni reportado
    )
    assert any(v.type == ViolationType.UNPACKED_MISMATCH for v in report.violations)


def test_rotation_allowed_orientation_is_valid():
    item = Item(id="I1", length=10, width=20, height=30, allowed_orientations="all")
    report = PackingValidator().validate(
        containers=[_container()],
        items=[item],
        packed_items=[_packed("I1", 0, 0, 0, l=30, w=10, h=20)],
        constraints=ConstraintFlags(allow_rotation=True),
    )
    assert report.is_valid
