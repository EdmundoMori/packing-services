"""Tests de las primitivas geométricas."""

from __future__ import annotations

from packing_services.domain.geometry import (
    AABB,
    Dimensions,
    Position,
    face_contact_area,
    fits_within,
    is_interior_point,
    is_same_box,
    overlaps,
    supported_area_ratio,
    unique_orientations,
)


def _box(x, y, z, l, w, h) -> AABB:
    return AABB(Position(x, y, z), Dimensions(l, w, h))


def test_fits_within_true():
    assert fits_within(_box(0, 0, 0, 10, 10, 10), Dimensions(10, 10, 10))


def test_fits_within_false_when_exceeds():
    assert not fits_within(_box(5, 0, 0, 10, 10, 10), Dimensions(10, 10, 10))


def test_touching_faces_do_not_overlap():
    a = _box(0, 0, 0, 10, 10, 10)
    b = _box(10, 0, 0, 10, 10, 10)  # comparten la cara x=10
    assert not overlaps(a, b)


def test_overlapping_boxes_detected():
    a = _box(0, 0, 0, 10, 10, 10)
    b = _box(5, 5, 5, 10, 10, 10)
    assert overlaps(a, b)


def test_unique_orientations_cube_is_single():
    orientations = unique_orientations(Dimensions(5, 5, 5), allow_rotation=True)
    assert len(orientations) == 1


def test_unique_orientations_distinct_dims_is_six():
    orientations = unique_orientations(Dimensions(1, 2, 3), allow_rotation=True)
    assert len(orientations) == 6


def test_unique_orientations_no_rotation():
    orientations = unique_orientations(Dimensions(1, 2, 3), allow_rotation=False)
    assert orientations == [Dimensions(1, 2, 3)]


def test_is_same_box_permutation():
    assert is_same_box(Dimensions(1, 2, 3), Dimensions(3, 1, 2))
    assert not is_same_box(Dimensions(1, 2, 3), Dimensions(1, 2, 4))


def test_support_ratio_on_floor_is_full():
    item = _box(0, 0, 0, 10, 10, 10)
    assert supported_area_ratio(item, []) == 1.0


def test_support_ratio_fully_supported_by_below():
    below = _box(0, 0, 0, 10, 10, 10)
    item = _box(0, 0, 10, 10, 10, 10)
    assert supported_area_ratio(item, [below]) == 1.0


def test_support_ratio_partial():
    below = _box(0, 0, 0, 5, 10, 10)  # cubre la mitad en x
    item = _box(0, 0, 10, 10, 10, 10)
    assert abs(supported_area_ratio(item, [below]) - 0.5) < 1e-9


def test_face_contact_area_touching():
    a = _box(0, 0, 0, 10, 10, 10)
    b = _box(10, 0, 0, 10, 10, 10)  # comparten la cara x=10
    assert face_contact_area(a, b) == 100.0


def test_face_contact_area_partial_overlap():
    a = _box(0, 0, 0, 10, 10, 10)
    b = _box(10, 5, 0, 10, 10, 10)  # tocan en x=10 pero solapan media cara en y
    assert face_contact_area(a, b) == 50.0


def test_face_contact_area_not_touching():
    a = _box(0, 0, 0, 10, 10, 10)
    b = _box(20, 0, 0, 10, 10, 10)
    assert face_contact_area(a, b) == 0.0


def test_is_interior_point():
    box = _box(0, 0, 0, 10, 10, 10)
    assert is_interior_point((5, 5, 5), box)
    assert not is_interior_point((0, 5, 5), box)   # sobre la cara, no interior
    assert not is_interior_point((15, 5, 5), box)
