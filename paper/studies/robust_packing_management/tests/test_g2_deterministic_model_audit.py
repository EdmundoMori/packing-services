"""Tests que documentan: modelo v1 determinista; indicador M3 ≠ seguridad geométrica."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from error_model import PublicErrorModel, expand_nominal, axis_margin_from_nominal  # noqa: E402
from geometry_contract import (  # noqa: E402
    AABBBox,
    AxisTriple,
    OrientedSizes,
    certificate_realized_safe_if_subseteq_envelope,
    envelope_exceeded,
    geometric_violation,
)
from methods_g2 import m3_local_analytical  # noqa: E402
from info_separation import PolicyObservation  # noqa: E402
from adapters import PolicySessionView, build_empty_session  # noqa: E402


class TestDeterministicGrowthKnown(unittest.TestCase):
    def test_realized_is_exact_function_of_nominal_and_public_alpha(self):
        model = PublicErrorModel.for_scenario("sens_mid")
        nom = AxisTriple(100.0, 80.0, 60.0)
        r1 = expand_nominal(nom, model.alpha)
        r2 = expand_nominal(nom, model.alpha)
        self.assertEqual(r1.as_tuple(), r2.as_tuple())
        self.assertEqual(
            r1.as_tuple(),
            (100.0 * 1.05, 80.0 * 1.05, 60.0 * 1.05),
        )
        # M2 margin makes envelope == realized in catalogue frame
        m = axis_margin_from_nominal(nom, model.alpha)
        env = AxisTriple(*(n + mm for n, mm in zip(nom.as_tuple(), m.as_tuple())))
        self.assertEqual(env.as_tuple(), r1.as_tuple())

    def test_no_extra_randomness_in_expand(self):
        model = PublicErrorModel.for_scenario("sens_high")
        for _ in range(5):
            self.assertEqual(
                expand_nominal(AxisTriple(10, 20, 30), model.alpha).as_tuple(),
                (11.0, 22.0, 33.0),
            )


class TestM3IndicatorIsNotGeometricRisk(unittest.TestCase):
    def test_m3_prefers_zero_margin_when_candidates_exist_despite_known_growth(self):
        """Under known growth, m=0 leaves R outside envelope; M3 still picks m0 if EP has cands."""
        model = PublicErrorModel.for_scenario("sens_mid")
        container = AxisTriple(500.0, 500.0, 500.0)
        nom = AxisTriple(100.0, 100.0, 100.0)
        session = build_empty_session(container)
        view = PolicySessionView(session, allow_rotation=True)
        obs = PolicyObservation(
            container_mm=container,
            current_item_id="a",
            current_nominal_mm=nom,
            margin_mm=AxisTriple(0, 0, 0),
            revealed=(),
            remaining_count_including_current=1,
        )
        margin, choice = m3_local_analytical(model)(obs, view)
        self.assertEqual(margin.as_tuple(), (0.0, 0.0, 0.0))
        self.assertIsNotNone(choice)
        realized = expand_nominal(nom, model.alpha)
        sized = OrientedSizes.from_catalogue(
            nom, margin, choice.orientation_order, realized=realized
        )
        self.assertTrue(envelope_exceeded(sized.realized_oriented, sized.envelope))
        # Validator: realized may still fit in empty large container
        gv = geometric_violation(
            AABBBox(choice.flb_mm, sized.realized_oriented), container, []
        )
        # Indicator said "safe" (risk 0) via candidates, but envelope does not cover realized
        self.assertFalse(sized.realized_oriented.as_tuple() == sized.envelope.as_tuple())
        # Certificate does not apply when realized not subseteq envelope
        cert = certificate_realized_safe_if_subseteq_envelope(
            flb=choice.flb_mm,
            envelope=sized.envelope,
            realized_oriented=sized.realized_oriented,
            container=container,
            occupied_revealed=[],
        )
        self.assertFalse(cert["realized_subseteq_envelope"])
        self.assertFalse(cert["applies"])
        # No contradiction: geometric failure can be false while envelope exceeded
        self.assertFalse(gv["geometric_failure"] and not envelope_exceeded(sized.realized_oriented, sized.envelope))


if __name__ == "__main__":
    unittest.main()
