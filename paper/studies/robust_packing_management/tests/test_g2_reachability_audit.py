"""Tests sintéticos justificados por la auditoría de alcanzabilidad G2 (rev 03)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from baselines import margin_zero, margin_uniform  # noqa: E402
from episode import ProtectionEpisode  # noqa: E402
from geometry_contract import (  # noqa: E402
    AABBBox,
    AxisTriple,
    envelope_exceeded,
    geometric_violation,
)
from info_separation import EpisodeSpec  # noqa: E402


class TestReachabilityAudit(unittest.TestCase):
    def test_abstract_shell_overlap_without_envelope_overlap(self):
        """Cáscara R\\E puede solapar un B que no solapa E (abstracto, no EP)."""
        flb = (0.0, 0.0, 0.0)
        env = AxisTriple(10, 10, 10)
        real = AxisTriple(15, 10, 10)
        occ = [AABBBox((12.0, 2.0, 2.0), AxisTriple(3, 4, 4))]
        container = AxisTriple(100, 100, 100)
        self.assertTrue(envelope_exceeded(real, env))
        self.assertFalse(
            geometric_violation(AABBBox(flb, env), container, occ)["geometric_failure"]
        )
        self.assertTrue(
            geometric_violation(AABBBox(flb, real), container, occ)["overlap"]
        )

    def test_large_margin_no_candidate_but_zero_margin_valid(self):
        spec = EpisodeSpec.build((45, 45, 45), [("a", (40, 40, 40), (40, 40, 40))])
        r_m = ProtectionEpisode(spec, margin_fn=margin_uniform(10)).run()
        r0 = ProtectionEpisode(spec, margin_fn=margin_zero).run()
        self.assertEqual(r_m.termination, "no_candidate")
        self.assertEqual(r0.termination, "completed")
        self.assertFalse(r0.geometric_failure)


if __name__ == "__main__":
    unittest.main()
