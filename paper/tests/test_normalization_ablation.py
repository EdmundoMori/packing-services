"""Pruebas sintéticas de la normalización y de la muestra de desarrollo."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from freeze_normalization_sample import (  # noqa: E402
    SelectionStopped,
    pools_after_exclusion,
    select_development,
)
from normalization_features import (  # noqa: E402
    FEATURE_NAMES,
    STD_EPS,
    constant_names,
    fit_standardizer,
    transform_rows,
)
from packing_services.online.features import FEATURE_NAMES as SOURCE_FEATURES


def _matrix(columns: dict[int, list[float]], rows: int = 4) -> np.ndarray:
    values = np.arange(rows * len(FEATURE_NAMES), dtype=np.float64).reshape(rows, len(FEATURE_NAMES))
    for index, column in columns.items():
        values[:, index] = column
    return values


class StandardizerTests(unittest.TestCase):
    def test_names_match_the_encoder_order(self):
        self.assertEqual(FEATURE_NAMES, SOURCE_FEATURES)

    def test_statistics_use_only_train_rows(self):
        train = _matrix({0: [1.0, 3.0, 5.0, 7.0]})
        val = _matrix({0: [100.0, 100.0, 100.0, 100.0]})
        stats = fit_standardizer(train)
        self.assertEqual(stats["mean"][0], 4.0)
        self.assertAlmostEqual(stats["population_std"][0], float(np.std([1, 3, 5, 7], ddof=0)))
        transformed_val = transform_rows(val, stats, arm="normalized")
        leaked = fit_standardizer(np.concatenate([train, val], axis=0))
        self.assertNotEqual(stats["mean"][0], leaked["mean"][0])
        self.assertAlmostEqual(transformed_val[0, 0], (100.0 - 4.0) / stats["denominator"][0])

    def test_constant_column_stays_finite_and_keeps_its_place(self):
        train = _matrix({0: [2.0, 2.0, 2.0, 2.0], 1: [0.0, 2.0, 4.0, 6.0]})
        stats = fit_standardizer(train)
        self.assertLessEqual(stats["population_std"][0], STD_EPS)
        self.assertEqual(stats["denominator"][0], 1.0)
        self.assertEqual(constant_names(train), [FEATURE_NAMES[0]])
        transformed = transform_rows(train, stats, arm="normalized")
        self.assertEqual(transformed.shape, train.shape)
        self.assertTrue(np.isfinite(transformed).all())
        self.assertTrue(np.allclose(transformed[:, 0], 0.0))
        self.assertEqual(stats["feature_names"], list(FEATURE_NAMES))

    def test_identity_and_normalized_share_the_saved_transform(self):
        train = _matrix({2: [1.0, 2.0, 3.0, 4.0]})
        stats = fit_standardizer(train)
        fresh = _matrix({2: [8.0, 8.0]}, rows=2)
        raw = transform_rows(fresh, stats, arm="raw")
        scored = transform_rows(fresh, stats, arm="normalized")
        trained = transform_rows(train, stats, arm="normalized")
        self.assertTrue(np.allclose(raw, fresh))
        self.assertTrue(np.allclose(scored[:, 2], (8.0 - stats["mean"][2]) / stats["denominator"][2]))
        self.assertTrue(np.allclose(trained[:, 2], (train[:, 2] - stats["mean"][2]) / stats["denominator"][2]))


class DevelopmentSelectionTests(unittest.TestCase):
    def test_selection_is_deterministic_and_keeps_exclusions_out(self):
        pools = {
            "euro-pallet": [f"E{index:04d}" for index in range(40)],
            "rollcontainer": [f"R{index:04d}" for index in range(40)],
        }
        excluded = {"E0001", "R0002"}
        kept = pools_after_exclusion(
            {target: list(ids) for target, ids in pools.items()},
            excluded,
        )
        self.assertNotIn("E0001", kept["euro-pallet"])
        first = select_development(kept)
        second = select_development({target: list(reversed(ids)) for target, ids in kept.items()})
        self.assertEqual(first["frozen_list_sha256"], second["frozen_list_sha256"])
        self.assertEqual(
            [row["order_id"] for row in first["execution_items"]],
            sorted(row["order_id"] for row in first["execution_items"]),
        )
        self.assertEqual(sum(1 for row in first["execution_items"] if row["target"] == "euro-pallet"), 25)
        self.assertTrue(first["confirmatory"] is False)

    def test_short_pool_stops_without_a_substitute(self):
        with self.assertRaises(SelectionStopped):
            pools_after_exclusion(
                {"euro-pallet": ["E1"], "rollcontainer": [f"R{index}" for index in range(30)]},
                set(),
            )


if __name__ == "__main__":
    unittest.main()
