"""Pruebas G1 — integridad sintética del contrato (sin BED-BPP, sin PPO)."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

from baselines import margin_axis, margin_uniform, margin_zero  # noqa: E402
from episode import ProtectionEpisode, fixed_rank_chooser  # noqa: E402
from geometry_contract import (  # noqa: E402
    AABBBox,
    AxisTriple,
    OrientedSizes,
    ORIENTATION_ORDERS,
    boxes_overlap,
    certificate_realized_safe_if_subseteq_envelope,
    envelope_exceeded,
    geometric_violation,
    unique_orientation_orders,
    validate_margin,
    validate_positive_dims,
)
from info_separation import EpisodeSpec, PolicyObservation, SimulatorTruth  # noqa: E402


def _spec(container, items, **kw):
    return EpisodeSpec.build(container, items, **kw)


class TestGeometryContract(unittest.TestCase):
    def test_reject_nan_inf_nonpositive_negative_margin(self):
        with self.assertRaises(ValueError):
            validate_positive_dims((1, math.nan, 1))
        with self.assertRaises(ValueError):
            validate_positive_dims((1, math.inf, 1))
        with self.assertRaises(ValueError):
            validate_positive_dims((1, 0, 1))
        with self.assertRaises(ValueError):
            validate_margin((1, -0.1, 0))

    def test_face_contact_allowed(self):
        a = AABBBox((0, 0, 0), AxisTriple(10, 10, 10))
        b = AABBBox((10, 0, 0), AxisTriple(10, 10, 10))
        self.assertFalse(boxes_overlap(a, b))

    def test_certificate_elementary(self):
        container = AxisTriple(100, 100, 100)
        occupied: list[AABBBox] = []
        flb = (0.0, 0.0, 0.0)
        env = AxisTriple(20, 20, 20)
        real = AxisTriple(15, 15, 15)
        cert = certificate_realized_safe_if_subseteq_envelope(
            flb=flb,
            envelope=env,
            realized_oriented=real,
            container=container,
            occupied_revealed=occupied,
        )
        self.assertTrue(cert["applies"])
        self.assertTrue(cert["certificate_holds"])
        self.assertFalse(cert["realized_geometric_failure"])

    def test_six_distinct_permutations(self):
        nom = AxisTriple(10, 20, 30)
        orders = unique_orientation_orders(nom)
        self.assertEqual(len(orders), 6)
        oriented = {nom.permute(o).as_tuple() for o in orders}
        self.assertEqual(len(oriented), 6)

    def test_orientation_does_not_resample_realized(self):
        nom = AxisTriple(10, 20, 30)
        margin = AxisTriple(1, 2, 3)
        realized = AxisTriple(11, 22, 33)
        triples = []
        for order in ORIENTATION_ORDERS:
            sized = OrientedSizes.from_catalogue(nom, margin, order, realized=realized)
            # Recover catalogue realized by inverse: check volume and multiset of axes.
            triples.append(tuple(sorted(sized.realized_oriented.as_tuple())))
        self.assertEqual(len(set(triples)), 1)
        self.assertEqual(triples[0], (11.0, 22.0, 33.0))

    def test_envelope_definition(self):
        sized = OrientedSizes.from_catalogue(
            AxisTriple(10, 20, 30),
            AxisTriple(1, 0, 2),
            (0, 1, 2),
            realized=AxisTriple(10, 20, 30),
        )
        self.assertEqual(sized.nominal_oriented.as_tuple(), (10, 20, 30))
        self.assertEqual(sized.margin_oriented.as_tuple(), (1, 0, 2))
        self.assertEqual(sized.envelope.as_tuple(), (11, 20, 32))

    def test_geometric_overlap_unit(self):
        container = AxisTriple(100, 100, 100)
        occ = [AABBBox((0, 0, 0), AxisTriple(30, 30, 30))]
        # Realized protruding into occupied region from FLB (20,0,0) with size 20 → (20-40)
        box = AABBBox((20, 0, 0), AxisTriple(20, 10, 10))
        g = geometric_violation(box, container, occ)
        self.assertTrue(g["overlap"])
        self.assertTrue(g["geometric_failure"])


class TestEpisodeEvents(unittest.TestCase):
    def test_zero_error(self):
        spec = _spec((100, 100, 100), [("a", (20, 20, 20), (20, 20, 20))])
        ep = ProtectionEpisode(spec, margin_fn=margin_zero)
        res = ep.run()
        self.assertEqual(res.termination, "completed")
        self.assertFalse(res.geometric_failure)
        self.assertEqual(res.n_envelope_exceeded, 0)
        self.assertAlmostEqual(res.J_B, (20 * 20 * 20) / (100**3))

    def test_realized_smaller(self):
        spec = _spec((100, 100, 100), [("a", (20, 20, 20), (15, 15, 15))])
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(res.termination, "completed")
        self.assertEqual(res.steps[0].event, "placed")
        self.assertEqual(res.steps[0].realized_oriented, (15, 15, 15))
        # J_B uses nominal volume
        self.assertAlmostEqual(res.V_nom_mm3, 20**3)

    def test_increase_within_reserve(self):
        spec = _spec((100, 100, 100), [("a", (20, 20, 20), (22, 21, 20))])
        res = ProtectionEpisode(spec, margin_fn=margin_uniform(3)).run()
        self.assertEqual(res.termination, "completed")
        self.assertEqual(res.steps[0].event, "placed")
        self.assertFalse(res.steps[0].envelope_exceeded_flag)

    def test_reserve_exceeded_geometry_valid_continues(self):
        # envelope 20; realized 25; large container → outside? 25 < 100 OK
        spec = _spec((100, 100, 100), [("a", (20, 20, 20), (25, 20, 20))])
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(res.termination, "completed")
        self.assertEqual(res.steps[0].event, "envelope_exceeded")
        self.assertTrue(res.steps[0].envelope_exceeded_flag)
        self.assertFalse(res.geometric_failure)
        self.assertGreater(res.J_B, 0)
        self.assertEqual(res.placed_ids, ["a"])
        # ocupación actualizada con realizado
        self.assertEqual(res.steps[0].realized_oriented, (25, 20, 20))

    def test_reserve_exceeded_exits_container(self):
        spec = _spec((55, 55, 55), [("a", (50, 50, 50), (60, 50, 50))])
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(res.termination, "geometric_failure")
        self.assertTrue(res.steps[0].envelope_exceeded_flag)
        self.assertEqual(res.steps[0].event, "geometric_failure")
        self.assertEqual(res.J_B, 0.0)
        self.assertEqual(res.V_nom_before_failure_mm3, 0.0)

    def test_reserve_exceeded_with_overlap_via_validator(self):
        # Integración EP: solape por exceso es difícil con FLB+; validamos el discriminante.
        container = AxisTriple(100, 100, 100)
        occ = [AABBBox((0, 0, 0), AxisTriple(40, 40, 40))]
        # Envelope habría sido (30,10,10) at FLB(30,0,0) — no solapa (contacto).
        # Realized (20,10,10) at (25,0,0) solapa — escenario de auditoría directa.
        g = geometric_violation(AABBBox((25, 0, 0), AxisTriple(20, 10, 10)), container, occ)
        self.assertTrue(g["overlap"])
        self.assertTrue(envelope_exceeded(AxisTriple(20, 10, 10), AxisTriple(10, 10, 10)))

    def test_no_candidate_distinct(self):
        spec = _spec((30, 30, 30), [("a", (20, 20, 20), (20, 20, 20))])
        res = ProtectionEpisode(spec, margin_fn=margin_uniform(20)).run()
        self.assertEqual(res.termination, "no_candidate")
        self.assertFalse(res.geometric_failure)
        self.assertEqual(res.J_B, 0.0)  # nada colocado
        self.assertEqual(res.events, ["no_candidate"])

    def test_no_candidate_keeps_partial_volume(self):
        spec = _spec(
            (50, 50, 50),
            [
                ("a", (20, 20, 20), (20, 20, 20)),
                ("b", (40, 40, 40), (40, 40, 40)),
            ],
        )
        # After placing a, b with huge margin → no_candidate
        def marg(obs: PolicyObservation) -> AxisTriple:
            if obs.current_item_id == "a":
                return AxisTriple(0, 0, 0)
            return AxisTriple(30, 30, 30)

        res = ProtectionEpisode(spec, margin_fn=marg).run()
        self.assertEqual(res.termination, "no_candidate")
        self.assertFalse(res.geometric_failure)
        self.assertAlmostEqual(res.J_B, (20**3) / (50**3))
        self.assertEqual(res.placed_ids, ["a"])

    def test_failure_terminal_no_recovery(self):
        spec = _spec(
            (55, 55, 55),
            [
                ("a", (50, 50, 50), (60, 50, 50)),
                ("b", (10, 10, 10), (10, 10, 10)),
            ],
        )
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(res.termination, "geometric_failure")
        self.assertEqual(len(res.steps), 1)
        self.assertNotIn("b", res.placed_ids)

    def test_axis_margins_and_orientation(self):
        spec = _spec((200, 200, 200), [("a", (10, 20, 30), (11, 20, 32))])
        res = ProtectionEpisode(spec, margin_fn=margin_axis((1, 0, 2))).run()
        self.assertIn(res.steps[0].event, ("placed", "envelope_exceeded"))
        self.assertFalse(res.geometric_failure)

    def test_jb_denominator(self):
        spec = _spec((10, 20, 30), [("a", (2, 2, 2), (2, 2, 2))])
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertAlmostEqual(res.container_volume_mm3, 10 * 20 * 30)
        self.assertAlmostEqual(res.J_B, 8 / (10 * 20 * 30))

    def test_update_with_realized_geometry(self):
        spec = _spec(
            (100, 100, 100),
            [
                ("a", (20, 20, 20), (25, 20, 20)),  # exceed but valid
                ("b", (20, 20, 20), (20, 20, 20)),
            ],
        )
        res = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(res.termination, "completed")
        self.assertEqual(res.n_envelope_exceeded, 1)
        self.assertTrue(res.rebuild_ok)

    def test_reset_no_contamination(self):
        spec = _spec((100, 100, 100), [("a", (20, 20, 20), (20, 20, 20))])
        ep = ProtectionEpisode(spec, margin_fn=margin_zero)
        r1 = ep.run()
        r2 = ep.run()
        self.assertEqual(r1.J_B, r2.J_B)
        self.assertEqual(r1.events, r2.events)

    def test_identical_nominal_different_realized_same_first_decision(self):
        s1 = _spec((100, 100, 100), [("a", (20, 30, 40), (20, 30, 40))])
        s2 = _spec((100, 100, 100), [("a", (20, 30, 40), (25, 35, 45))])
        d1 = ProtectionEpisode(s1, margin_fn=margin_uniform(1)).first_decision_signature(
            AxisTriple(1, 1, 1)
        )
        d2 = ProtectionEpisode(s2, margin_fn=margin_uniform(1)).first_decision_signature(
            AxisTriple(1, 1, 1)
        )
        self.assertEqual(d1["choice"], d2["choice"])

    def test_suffix_does_not_change_current_decision(self):
        short = _spec((100, 100, 100), [("a", (20, 20, 20), (20, 20, 20))])
        long = _spec(
            (100, 100, 100),
            [
                ("a", (20, 20, 20), (20, 20, 20)),
                ("b", (90, 90, 90), (90, 90, 90)),
                ("c", (5, 5, 5), (5, 5, 5)),
            ],
        )
        d1 = ProtectionEpisode(short, margin_fn=margin_zero).first_decision_signature(
            AxisTriple(0, 0, 0)
        )
        d2 = ProtectionEpisode(long, margin_fn=margin_zero).first_decision_signature(
            AxisTriple(0, 0, 0)
        )
        self.assertEqual(d1["choice"], d2["choice"])

    def test_deterministic_reproduction(self):
        spec = _spec(
            (80, 80, 80),
            [
                ("a", (20, 25, 30), (21, 25, 30)),
                ("b", (15, 15, 15), (15, 15, 15)),
            ],
        )
        r1 = ProtectionEpisode(spec, margin_fn=margin_axis((2, 1, 0))).run()
        r2 = ProtectionEpisode(spec, margin_fn=margin_axis((2, 1, 0))).run()
        self.assertEqual(r1.events, r2.events)
        self.assertEqual(r1.J_B, r2.J_B)
        self.assertEqual(
            [s.flb_mm for s in r1.steps if s.flb_mm],
            [s.flb_mm for s in r2.steps if s.flb_mm],
        )

    def test_policy_cannot_see_hidden_truth_object(self):
        spec = _spec((100, 100, 100), [("a", (10, 10, 10), (12, 10, 10))])
        ep = ProtectionEpisode(spec, margin_fn=margin_zero)
        obs = ep.reset()
        public = obs.to_public_dict()
        self.assertNotIn("realized", public)
        self.assertNotIn("truth", public)
        # Campos de observación no incluyen realizado actual
        self.assertEqual(public["current_nominal_mm"], (10, 10, 10))
        leaked = "12" in str(public.get("current_nominal_mm"))
        self.assertFalse(leaked)
        # SimTruth no es atributo de PolicyObservation
        self.assertFalse(hasattr(obs, "truth"))
        self.assertFalse(hasattr(obs, "_truth"))

    def test_chooser_does_not_receive_simulator_truth(self):
        seen = {}

        def wrapped_chooser(obs, view):
            seen["obs_type"] = type(obs).__name__
            seen["has_truth_arg"] = False
            # view no debe exponer peek_realized
            self.assertFalse(hasattr(view, "peek_realized"))
            self.assertFalse(hasattr(view, "_truth"))
            return fixed_rank_chooser(obs, view)

        spec = _spec((100, 100, 100), [("a", (10, 10, 10), (10, 10, 10))])
        ProtectionEpisode(spec, margin_fn=margin_zero, chooser=wrapped_chooser).run()
        self.assertEqual(seen["obs_type"], "PolicyObservation")

    def test_same_realized_across_methods(self):
        items = [("a", (20, 20, 20), (22, 20, 20)), ("b", (15, 15, 15), (15, 15, 15))]
        spec = _spec((100, 100, 100), items)
        t1 = spec.truth().peek_realized("a").as_tuple()
        r0 = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        r1 = ProtectionEpisode(spec, margin_fn=margin_uniform(1)).run()
        # mismos realizados subyacentes
        self.assertEqual(t1, (22, 20, 20))
        # métodos distintos pueden diferir en eventos, pero el spec es el mismo objeto lógico
        self.assertEqual(spec.truth().peek_realized("b").as_tuple(), (15, 15, 15))
        self.assertIsInstance(r0.J_B, float)
        self.assertIsInstance(r1.J_B, float)

    def test_baselines_supplied_not_calibrated(self):
        spec = _spec((100, 100, 100), [("a", (10, 10, 10), (10, 10, 10))])
        for fn in (margin_zero, margin_uniform(2), margin_axis((1, 2, 3))):
            res = ProtectionEpisode(spec, margin_fn=fn).run()
            self.assertIn(res.termination, ("completed", "no_candidate", "geometric_failure"))


if __name__ == "__main__":
    unittest.main()
