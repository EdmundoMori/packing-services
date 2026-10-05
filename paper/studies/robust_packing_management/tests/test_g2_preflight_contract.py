"""Pruebas G2: emparejamiento, orientación, fallos, no_candidate, timeout, persistencia, info, hashes."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

from error_model import (  # noqa: E402
    PREFLIGHT_SCENARIO,
    PublicErrorModel,
    SCENARIOS,
    expand_nominal,
    model_public_dict,
)
from geometry_contract import AxisTriple, OrientedSizes, ORIENTATION_ORDERS  # noqa: E402
from info_separation import EpisodeSpec, PolicyObservation  # noqa: E402
from methods_g2 import build_methods  # noqa: E402
from run_g2_episode import persist_episode, run_method_episode  # noqa: E402
from episode import EpisodeResult, StepRecord  # noqa: E402


class TestNoisePairing(unittest.TestCase):
    def test_expand_deterministic_and_positive(self):
        model = PublicErrorModel.for_scenario("sens_mid")
        nom = AxisTriple(100, 50, 20)
        a = expand_nominal(nom, model.alpha)
        b = expand_nominal(nom, model.alpha)
        self.assertEqual(a.as_tuple(), b.as_tuple())
        self.assertTrue(all(x > 0 for x in a.as_tuple()))
        self.assertAlmostEqual(a.length, 100 * 1.05)

    def test_same_realization_across_methods_on_spec(self):
        model = PublicErrorModel.for_scenario(PREFLIGHT_SCENARIO)
        nom = AxisTriple(30, 20, 10)
        real = expand_nominal(nom, model.alpha)
        spec = EpisodeSpec.build((200, 200, 200), [("i1", nom.as_tuple(), real.as_tuple())])
        methods = build_methods(model)
        maps = []
        for mid, fn in methods.items():
            # truth map identical
            maps.append({it.item_id: it.realized_mm.as_tuple() for it in spec.items})
            _ = run_method_episode(spec, fn, method_id=mid, timeout_s=30.0)
        self.assertTrue(all(m == maps[0] for m in maps))


class TestOrientation(unittest.TestCase):
    def test_orientation_permutes_same_realization(self):
        nom = AxisTriple(10, 20, 30)
        margin = AxisTriple(1, 2, 3)
        realized = AxisTriple(11, 22, 33)
        for order in ORIENTATION_ORDERS:
            sized = OrientedSizes.from_catalogue(nom, margin, order, realized=realized)
            self.assertEqual(
                set(sized.realized_oriented.as_tuple()),
                set(realized.as_tuple()),
            )
            # same multiset as permute of realised — not a resample
            self.assertEqual(
                sized.realized_oriented.as_tuple(),
                realized.permute(order).as_tuple(),
            )


class TestFailureMetrics(unittest.TestCase):
    def test_geometric_failure_zeros_JB(self):
        # oversized realized vs tiny container with zero margin → fail
        spec = EpisodeSpec.build((50, 50, 50), [("a", (40, 40, 40), (60, 40, 40))])
        methods = build_methods(PublicErrorModel.for_scenario("sens_mid"))
        res = run_method_episode(spec, methods["M0"], method_id="M0", timeout_s=30.0)
        self.assertTrue(res.geometric_failure)
        self.assertEqual(res.J_B, 0.0)
        self.assertEqual(res.termination, "geometric_failure")
        self.assertIn("geometric_failure", res.events)

    def test_completed_JB_uses_nominal(self):
        spec = EpisodeSpec.build((100, 100, 100), [("a", (10, 10, 10), (10, 10, 10))])
        methods = build_methods(PublicErrorModel.for_scenario("sens_low"))
        res = run_method_episode(spec, methods["M0"], method_id="M0", timeout_s=30.0)
        self.assertEqual(res.termination, "completed")
        self.assertFalse(res.geometric_failure)
        self.assertAlmostEqual(res.J_B, 1000.0 / 1_000_000.0)


class TestNoCandidate(unittest.TestCase):
    def test_large_uniform_margin_no_candidate(self):
        # force M1-like large margin via custom model mid with huge u by using high scenario
        # and a container that barely fits nominal
        model = PublicErrorModel.for_scenario("sens_high")  # u=12
        spec = EpisodeSpec.build((45, 45, 45), [("a", (40, 40, 40), (40, 40, 40))])
        methods = build_methods(model)
        res = run_method_episode(spec, methods["M1"], method_id="M1", timeout_s=30.0)
        self.assertEqual(res.termination, "no_candidate")
        self.assertFalse(res.geometric_failure)


class TestTimeout(unittest.TestCase):
    def test_timeout_terminates_and_counts(self):
        # many items; near-zero timeout forces timeout path
        items = [(f"i{k}", (5, 5, 5), (5, 5, 5)) for k in range(30)]
        spec = EpisodeSpec.build((200, 200, 200), items)
        methods = build_methods(PublicErrorModel.for_scenario("sens_mid"))
        res = run_method_episode(spec, methods["M0"], method_id="M0", timeout_s=-1.0)
        self.assertEqual(res.termination, "timeout")


class TestPersistence(unittest.TestCase):
    def test_atomic_persist_failed_attempt(self):
        steps = [
            StepRecord("a", (0, 0, 0), "placed", flb_mm=(0, 0, 0)),
            StepRecord("b", (0, 0, 0), "geometric_failure", flb_mm=(0, 0, 0)),
        ]
        result = EpisodeResult(
            termination="geometric_failure",
            steps=steps,
            placed_ids=["a"],
            V_nom_mm3=0.0,
            V_nom_before_failure_mm3=0.0,
            container_volume_mm3=1.0,
            J_B=0.0,
            n_envelope_exceeded=0,
            geometric_failure=True,
            events=["placed", "geometric_failure"],
        )
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "case"
            persist_episode(out, meta={"order_id": "x", "realized_by_item": {"a": (1, 1, 1)}}, result=result, wall_s=0.1)
            data = json.loads((out / "result.json").read_text())
            self.assertIsNotNone(data["failed_attempt"])
            self.assertEqual(data["failed_attempt"]["item_id"], "b")
            self.assertEqual(len(data["accepted_placements"]), 1)
            self.assertIsNone(data["physical_stability_verified"])


class TestNoFutureInfo(unittest.TestCase):
    def test_policy_observation_lacks_current_realized(self):
        obs = PolicyObservation(
            container_mm=AxisTriple(1, 1, 1),
            current_item_id="a",
            current_nominal_mm=AxisTriple(1, 1, 1),
            margin_mm=AxisTriple(0, 0, 0),
            revealed=(),
            remaining_count_including_current=1,
        )
        self.assertFalse(hasattr(obs, "current_realized_mm"))
        self.assertNotIn("realized", obs.to_public_dict())


class TestHashConfigReject(unittest.TestCase):
    def test_unknown_scenario_rejected(self):
        with self.assertRaises(KeyError):
            PublicErrorModel.for_scenario("not_a_scenario")

    def test_preflight_scenario_is_mid(self):
        self.assertEqual(PREFLIGHT_SCENARIO, "sens_mid")
        self.assertIn(PREFLIGHT_SCENARIO, SCENARIOS)

    def test_model_public_marks_not_ngram(self):
        d = model_public_dict(PublicErrorModel.for_scenario("sens_mid"))
        self.assertTrue(d["not_bedbpp_ngram_2cm"])
        self.assertFalse(d["probabilistic_calibration"])


if __name__ == "__main__":
    unittest.main()
