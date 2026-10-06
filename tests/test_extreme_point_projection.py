"""Pruebas sintéticas C04: cima máxima en franja EPS (motor EP simplificado).

Definición geométrica bajo prueba (no rayo −z):
- Región: franja XY de generación (p. ej. [x1, x1+EPS]×[y0, y1]).
- Intercepta: intersección de huellas XY con área positiva.
- Valor: max(techo) entre interceptores en ``placed``; si ninguno, 0.
- No filtra por altura relativa a z0 del ítem nuevo.
Expectativas calculadas a mano desde esa definición.
"""

from __future__ import annotations

import copy

from packing_services.algorithms._extreme_points import (
    ExtremePointPacker,
    _BinState,
    _generate_extreme_points,
    _support_z,
)
from packing_services.algorithms.extreme_points_3d import ExtremePoints3D
from packing_services.domain.enums import SolutionStatus
from packing_services.domain.geometry import EPS, AABB, Dimensions, Position
from packing_services.domain.models import (
    AlgorithmConfig,
    ConstraintFlags,
    Container,
    Item,
    PackingProblem,
)
from packing_services.online.session import ExtremePointOnlineSession


def _box(x: float, y: float, z: float, l: float, w: float, h: float) -> AABB:
    return AABB(position=Position(x, y, z), dimensions=Dimensions(l, w, h))


# ---------------------------------------------------------------------------
# Defecto mínimo y umbral
# ---------------------------------------------------------------------------


def test_c04_minimal_face_flush_strip_vs_wider_region():
    """AABB (10,0,0)+(10,10,7); franja EPS vs región más ancha (solo contraste)."""
    prev = _box(10.0, 0.0, 0.0, 10.0, 10.0, 7.0)
    x1 = prev.max_corner[0]
    flush = _box(x1, 0.0, 0.0, 10.0, 10.0, 5.0)

    assert _support_z(x1, 0.0, x1 + EPS, 10.0, [flush]) == 5.0
    assert _support_z(x1, 0.0, x1 + 1.0, 10.0, [flush]) == 5.0

    frag_x = 0.1 + 0.3
    frag = _box(frag_x, 0.0, 0.0, 5.0, 10.0, 4.0)
    assert _support_z(frag_x, 0.0, frag_x + EPS, 10.0, [frag]) == 4.0

    # Contacto exacto desde la izquierda (ox=0): no intercepta.
    assert _support_z(x1, 0.0, x1 + EPS, 10.0, [prev]) == 0.0


def test_c04_positive_overlap_below_eps_intercepts_exact_contact_does_not():
    """Solape positivo < EPS intercepta; contacto exacto (ox=0) no."""
    x1 = 20.0
    # Entra EPS/2 en la franja → ox = EPS/2 > 0 → techo 6.
    partial = _box(x1 + EPS / 2.0, 0.0, 0.0, 5.0, 5.0, 6.0)
    assert _support_z(x1, 0.0, x1 + EPS, 10.0, [partial]) == 6.0

    # Termina exactamente en x1 → ox = 0.
    left_touch = _box(10.0, 0.0, 0.0, 10.0, 10.0, 9.0)
    assert abs(left_touch.max_corner[0] - x1) <= 0.0
    assert _support_z(x1, 0.0, x1 + EPS, 10.0, [left_touch]) == 0.0


def test_c04_obstacle_only_inside_eps_strip():
    """Obstáculo cuya huella está contenida en la franja de ancho EPS."""
    x1 = 20.0
    # [20, 20+EPS] × [1, 4], techo 3 — área EPS×3 > 0.
    only_strip = _box(x1, 1.0, 0.0, EPS, 3.0, 3.0)
    assert only_strip.max_corner[0] == x1 + EPS or abs(
        only_strip.max_corner[0] - (x1 + EPS)
    ) < 1e-15
    assert _support_z(x1, 0.0, x1 + EPS, 10.0, [only_strip]) == 3.0


# ---------------------------------------------------------------------------
# Distingue “cima máxima XY” de “rayo descendente desde z0”
# ---------------------------------------------------------------------------


def test_c04_low_obstacle_contributes_top():
    """Obstáculo bajo (techo 4) en franja → z★=4."""
    low = _box(20.0, 0.0, 0.0, 2.0, 5.0, 4.0)
    assert _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [low]) == 4.0
    new = _box(0.0, 0.0, 0.0, 20.0, 10.0, 3.0)  # z0=0
    assert Position(20.0, 0.0, 4.0) in _generate_extreme_points(new, [low])


def test_c04_tall_obstacle_above_new_item_base_still_contributes():
    """Caja alta (techo 50) con ítem nuevo en z0=10: sigue contribuyendo 50.

    Si fuera rayo −z desde z0=10, techos > 10 no contarían. El motor toma
    max cima XY sin filtrar altura → 50. Documenta el comportamiento real.
    """
    tall = _box(20.0, 0.0, 0.0, 2.0, 5.0, 50.0)
    new = _box(0.0, 0.0, 10.0, 20.0, 10.0, 5.0)  # z0=10 < 50
    assert _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [tall]) == 50.0
    assert Position(20.0, 0.0, 50.0) in _generate_extreme_points(new, [tall])


def test_c04_floating_obstacle_above_also_contributes():
    """Caja ‘flotante’ z∈[40,55] que cruza la franja XY → z★=55 (no se excluye)."""
    floating = _box(20.0, 1.0, 40.0, 2.0, 4.0, 15.0)
    assert floating.min_corner[2] == 40.0
    assert floating.max_corner[2] == 55.0
    assert _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [floating]) == 55.0


def test_c04_multiple_heights_selects_max_among_xy_interceptors():
    low = _box(20.0, 0.0, 0.0, 3.0, 3.0, 2.0)
    mid = _box(20.0, 4.0, 0.0, 3.0, 3.0, 7.0)
    high = _box(20.0, 7.0, 10.0, 3.0, 2.0, 12.0)  # techo 22, aún en y∈[0,10]
    aside = _box(20.0, 12.0, 0.0, 3.0, 3.0, 100.0)  # fuera de la franja en y
    assert _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [low, mid, high, aside]) == 22.0


def test_c04_face_edge_corner_contact():
    """Cara (área>0) intercepta; arista/esquina (área 0) no."""
    x1, y1 = 20.0, 10.0
    assert _support_z(x1, 0.0, x1 + EPS, y1, [_box(x1, 1.0, 0.0, 5.0, 5.0, 6.0)]) == 6.0
    corner = _box(20.0, 10.0, 0.0, 5.0, 5.0, 8.0)
    assert _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [corner]) == 0.0
    assert _support_z(10.0, 10.0, 20.0, 10.0 + EPS, [corner]) == 0.0
    assert _support_z(10.0, 10.0, 20.0, 10.0 + EPS, [_box(12.0, 10.0, 0.0, 6.0, 5.0, 7.0)]) == 7.0


def test_c04_xy_translation_invariance_mm_scales():
    """Misma geometría relativa tras traslación XY en escalas típicas (mm)."""
    base_obs = _box(20.0, 2.0, 0.0, 4.0, 4.0, 8.0)
    base_z = _support_z(20.0, 0.0, 20.0 + EPS, 10.0, [base_obs])
    assert base_z == 8.0
    for dx, dy in [(0.0, 0.0), (100.0, 50.0), (1234.5, 678.25), (1e5, 2e4)]:
        obs = _box(20.0 + dx, 2.0 + dy, 0.0, 4.0, 4.0, 8.0)
        z = _support_z(20.0 + dx, 0.0 + dy, 20.0 + dx + EPS, 10.0 + dy, [obs])
        assert z == 8.0, (dx, dy, z)


def test_c04_generation_then_independent_validation():
    """Generación de candidata y validación de factibilidad son pasos distintos."""
    placed = [_box(20.0, 0.0, 0.0, 10.0, 10.0, 5.0)]
    new = _box(0.0, 0.0, 0.0, 20.0, 10.0, 3.0)
    cands = _generate_extreme_points(new, placed)
    projected = Position(20.0, 0.0, 5.0)
    assert projected in cands

    packer = ExtremePointPacker(selection="blb")
    item = Item(id="T", length=10, width=10, height=10, weight=1)
    tight = _BinState(
        container=Container(id="C1", length=25, width=100, height=100, max_weight=1e9),
        placed=list(placed),
        extreme_points=[projected],
    )
    assert not packer._feasible(
        tight, projected, Dimensions(10, 10, 10), item, ConstraintFlags()
    )
    wide = _BinState(
        container=Container(id="C2", length=100, width=100, height=100, max_weight=1e9),
        placed=list(placed),
        extreme_points=[projected],
    )
    assert packer._feasible(
        wide, projected, Dimensions(10, 10, 10), item, ConstraintFlags()
    )


def test_c04_placed_before_excludes_new_box():
    """``placed_before`` no incluye el ítem nuevo: su propio techo no fija z★."""
    new = _box(0.0, 0.0, 0.0, 20.0, 10.0, 30.0)
    # Sin vecinos: cima en franja derecha = 0, no 30.
    cands = _generate_extreme_points(new, [])
    assert Position(20.0, 0.0, 0.0) in cands
    assert Position(20.0, 0.0, 30.0) not in cands


def test_c04_determinism_and_no_mutation_of_input_boxes():
    placed = [_box(20.0, 1.0, 0.0, 4.0, 4.0, 8.0)]
    new = _box(0.0, 0.0, 0.0, 20.0, 10.0, 3.0)
    placed_snap = copy.deepcopy(placed)
    new_snap = copy.deepcopy(new)
    a = _generate_extreme_points(new, placed)
    b = _generate_extreme_points(new, placed)
    assert [(p.x, p.y, p.z) for p in a] == [(p.x, p.y, p.z) for p in b]
    assert placed[0].position.as_tuple() == placed_snap[0].position.as_tuple()
    assert placed[0].dimensions.as_tuple() == placed_snap[0].dimensions.as_tuple()
    assert new.position.as_tuple() == new_snap.position.as_tuple()


def test_c04_numeric_strip_width_documented_not_collapsed_at_mm():
    """En escalas mm razonables x+EPS ≠ x; colapso solo a escalas enormes."""
    for x in (0.0, 1.0, 1e3, 1e5, 1e6):
        assert (x + EPS) != x
        assert (x + EPS) - x > 0.0
    # Límite documentado: no se cambia EPS para ocultarlo.
    assert (1e15 + EPS) == 1e15


def test_c04_front_strip_symmetric():
    placed = [_box(2.0, 10.0, 0.0, 4.0, 4.0, 7.0)]
    assert _support_z(0.0, 10.0, 10.0, 10.0 + EPS, placed) == 7.0
    assert Position(0.0, 10.0, 7.0) in _generate_extreme_points(
        _box(0.0, 0.0, 0.0, 10.0, 10.0, 3.0), placed
    )


def test_c04_extreme_points_3d_still_valid_on_synthetic():
    items = [Item(id=f"I{i}", length=40, width=30, height=20, weight=1) for i in range(4)]
    problem = PackingProblem(
        problem_type="3D_BPP",
        containers=[Container(id="C1", length=100, width=100, height=100, max_weight=1e9)],
        items=items,
        algorithm=AlgorithmConfig(name="extreme_points_3d"),
    )
    solution = ExtremePoints3D().run(problem)
    assert solution.status == SolutionStatus.SUCCESS
    assert solution.validation_report.is_valid


def test_c04_online_session_candidates_deterministic():
    session = ExtremePointOnlineSession(
        [Container(id="C1", length=100, width=100, height=100, max_weight=1e9)],
        selection="blb",
    )
    item = Item(id="A", length=20, width=10, height=7, weight=1)
    c1 = session.candidates(item, ConstraintFlags())
    c2 = session.candidates(item, ConstraintFlags())
    assert [c.position.as_tuple() for c in c1] == [c.position.as_tuple() for c in c2]
    assert len(c1) >= 1
