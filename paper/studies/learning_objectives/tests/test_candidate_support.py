"""Pruebas sintéticas del contrato único de S y pérdidas asociadas."""

from __future__ import annotations

import copy
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
TOOLS = HERE / "tools"
if str(TOOLS) in sys.path:
    sys.path.remove(str(TOOLS))
sys.path.insert(0, str(TOOLS))

from candidate_support import (  # noqa: E402
    GeometryRecord,
    build_candidate_support,
    build_candidate_support_from_options,
    select_logit_index,
    support_identities,
)
from losses import (  # noqa: E402
    classification_loss,
    preference_loss,
    return_difference_loss,
)
from support_api import build_S, build_S_from_options  # noqa: E402
from support_metrics import support_regret  # noqa: E402


def _rec(index: int, x: float, y: float, z: float, l: float, w: float, h: float) -> GeometryRecord:
    return GeometryRecord(0, x, y, z, l, w, h, index)


def _option(index: int, x: float, y: float, z: float, l: float, w: float, h: float):
    candidate = SimpleNamespace(
        bin_index=0,
        position=SimpleNamespace(x=x, y=y, z=z),
        dimensions=SimpleNamespace(length=l, width=w, height=h),
    )
    return SimpleNamespace(candidate=candidate, item=f"item-{index}")


class CandidateSupportTests(unittest.TestCase):
    def test_greedy_always_in_s(self) -> None:
        legal = [
            _rec(0, 0, 0, 0, 10, 10, 10),
            _rec(1, 1, 0, 0, 10, 20, 10),
            _rec(2, 2, 0, 0, 30, 10, 10),
            _rec(3, 3, 0, 0, 10, 10, 30),
            _rec(4, 4, 0, 0, 15, 15, 15),
        ]
        greedy = legal[2].geometric_id
        support = build_candidate_support(legal, greedy)
        self.assertEqual(support[0].geometric_id, greedy)
        self.assertIn(greedy, support_identities(support))

    def test_max_four_and_no_duplicates(self) -> None:
        legal = [_rec(i, float(i), 0, 0, 10 + i, 10, 10) for i in range(8)]
        support = build_candidate_support(legal, legal[0].geometric_id)
        self.assertLessEqual(len(support), 4)
        ids = support_identities(support)
        self.assertEqual(len(ids), len(set(ids)))

    def test_distinct_orientations_preserved(self) -> None:
        legal = [
            _rec(0, 0, 0, 0, 10, 20, 30),
            _rec(1, 0, 0, 0, 30, 20, 10),  # misma posición, orientación distinta
            _rec(2, 5, 0, 0, 10, 20, 30),
        ]
        support = build_candidate_support(legal, legal[0].geometric_id, limit=3)
        ids = support_identities(support)
        self.assertIn(legal[0].geometric_id, ids)
        self.assertIn(legal[1].geometric_id, ids)

    def test_geometric_dedup(self) -> None:
        legal = [
            _rec(0, 0, 0, 0, 10, 10, 10),
            _rec(1, 0, 0, 0, 10, 10, 10),  # duplicado
            _rec(2, 1, 0, 0, 20, 10, 10),
            _rec(3, 2, 0, 0, 10, 20, 10),
            _rec(4, 3, 0, 0, 10, 10, 20),
        ]
        support = build_candidate_support(legal, legal[0].geometric_id)
        self.assertEqual(len(support_identities(support)), len(set(support_identities(support))))
        self.assertNotEqual(support_identities(support).count(legal[0].geometric_id), 2)

    def test_determinism_and_no_mutation(self) -> None:
        legal = [_rec(i, float(i), 0, 0, 10 + (i % 3), 12, 14) for i in range(6)]
        original = copy.deepcopy(legal)
        first = support_identities(build_candidate_support(legal, legal[1].geometric_id))
        second = support_identities(build_candidate_support(legal, legal[1].geometric_id))
        self.assertEqual(first, second)
        self.assertEqual(legal, original)

    def test_invariant_to_suffix_and_order_id(self) -> None:
        legal = [_rec(i, float(i), 0, 0, 10, 10, 10 + i) for i in range(5)]
        greedy = legal[0].geometric_id
        # Los argumentos de la función no admiten sufijo ni order_id.
        a = support_identities(build_candidate_support(legal, greedy))
        b = support_identities(build_candidate_support(list(legal), greedy))
        self.assertEqual(a, b)

    def test_same_identity_labeling_and_deployment_api(self) -> None:
        options = [
            _option(0, 0, 0, 0, 10, 10, 10),
            _option(1, 1, 0, 0, 20, 10, 10),
            _option(2, 2, 0, 0, 10, 20, 10),
            _option(3, 3, 0, 0, 10, 10, 20),
            _option(4, 4, 0, 0, 15, 15, 15),
        ]
        greedy = options[0]
        via_options = build_S_from_options(options, greedy)
        records = [
            GeometryRecord(
                0,
                opt.candidate.position.x,
                opt.candidate.position.y,
                opt.candidate.position.z,
                opt.candidate.dimensions.length,
                opt.candidate.dimensions.width,
                opt.candidate.dimensions.height,
                index,
            )
            for index, opt in enumerate(options)
        ]
        via_records = build_S(records, records[0].geometric_id)
        self.assertEqual(
            [record_from_option(opt).geometric_id for opt in via_options],
            support_identities(via_records),
        )
        # build_candidate_support_from_options es el mismo símbolo exportado
        self.assertIs(build_S_from_options, build_candidate_support_from_options)

    def test_logit_tie_keeps_smallest_index(self) -> None:
        self.assertEqual(select_logit_index([1.0, 1.0, 0.5]), 0)
        self.assertEqual(select_logit_index([0.2, 0.9, 0.9]), 1)

    def test_returns_all_when_fewer_than_limit(self) -> None:
        legal = [_rec(0, 0, 0, 0, 10, 10, 10), _rec(1, 1, 0, 0, 20, 10, 10)]
        support = build_candidate_support(legal, legal[0].geometric_id)
        self.assertEqual(len(support), 2)


def record_from_option(option) -> GeometryRecord:
    c = option.candidate
    return GeometryRecord(0, c.position.x, c.position.y, c.position.z, c.dimensions.length, c.dimensions.width, c.dimensions.height, 0)


class LossAndRegretTests(unittest.TestCase):
    def test_classification_prefers_better_max(self) -> None:
        q = [0.1, 0.5, 0.2]
        better = classification_loss([0.0, 2.0, 0.0], q)
        worse = classification_loss([2.0, 0.0, 0.0], q)
        self.assertLess(better, worse)

    def test_preference_sign(self) -> None:
        q = [0.1, 0.4]
        aligned = preference_loss([0.0, 1.0], q)
        reversed_scores = preference_loss([1.0, 0.0], q)
        self.assertLess(aligned, reversed_scores)

    def test_return_difference_sign(self) -> None:
        q = [0.1, 0.4]
        aligned = return_difference_loss([0.1, 0.4], q)
        reversed_scores = return_difference_loss([0.4, 0.1], q)
        self.assertLess(aligned, reversed_scores)
        self.assertTrue(math.isclose(aligned, 0.0, abs_tol=1e-15))

    def test_all_tied_returns(self) -> None:
        q = [0.3, 0.3, 0.3]
        self.assertTrue(math.isclose(preference_loss([1.0, 0.0, -1.0], q), ((1.0 - 0.0) ** 2 + (1.0 - -1.0) ** 2 + (0.0 - -1.0) ** 2) / 3.0))
        self.assertEqual(return_difference_loss([1.0, 0.0, -1.0], q), 0.0)
        # clasificación: masa uniforme
        loss = classification_loss([0.0, 0.0, 0.0], q)
        self.assertGreater(loss, 0.0)

    def test_support_regret(self) -> None:
        q = [0.2, 0.5, 0.1]
        self.assertEqual(support_regret(q, 1), 0.0)
        self.assertGreater(support_regret(q, 0), 0.0)
        self.assertTrue(math.isclose(support_regret(q, 0), 0.3, abs_tol=1e-15))


if __name__ == "__main__":
    unittest.main()
