"""Pruebas del analizador exploratorio. No cargan modelos reales."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TOOLS = HERE / "tools"
if str(TOOLS) in sys.path:
    sys.path.remove(str(TOOLS))
sys.path.insert(0, str(TOOLS))

from pilot_analysis import (  # noqa: E402
    analyze_pilot,
    leave_one_order_out,
    order_level_deltas,
    stratified_order_bootstrap,
)
from pilot_reader import PilotIntegrityError, case_key, index_pilot  # noqa: E402


def _row(order_id: str, target: str, arm: str, seed: int | None, u: float) -> dict:
    return {
        "key": case_key(order_id, arm, seed),
        "order_id": order_id,
        "target": target,
        "arm": arm,
        "seed": seed,
        "effective_u_geom": u,
        "in_denominator": True,
    }


def _synthetic_pilot() -> list[dict]:
    """Seis euro y seis roll. Preferencias = clasificación + 0.03 en todas las semillas."""

    rows = []
    euro = [f"E{i:02d}" for i in range(6)]
    roll = [f"R{i:02d}" for i in range(6)]
    for order_id in euro:
        rows.append(_row(order_id, "euro-pallet", "greedy", None, 0.60))
        for seed in (11, 23, 37):
            rows.append(_row(order_id, "euro-pallet", "classification", seed, 0.50))
            rows.append(_row(order_id, "euro-pallet", "preferences", seed, 0.53))
    for order_id in roll:
        rows.append(_row(order_id, "rollcontainer", "greedy", None, 0.70))
        for seed in (11, 23, 37):
            rows.append(_row(order_id, "rollcontainer", "classification", seed, 0.40))
            rows.append(_row(order_id, "rollcontainer", "preferences", seed, 0.43))
    return rows


class PilotAnalysisTests(unittest.TestCase):
    def test_pairing_and_seed_retention(self) -> None:
        pilot = index_pilot(_synthetic_pilot())
        orders = order_level_deltas(pilot)
        self.assertEqual(len(orders), 12)
        for order in orders:
            self.assertEqual(len(order["by_seed"]), 3)
            self.assertEqual([item["seed"] for item in order["by_seed"]], [11, 23, 37])
            self.assertTrue(
                math.isclose(order["d_preferences_minus_classification"], 0.03, abs_tol=1e-15)
            )

    def test_rejects_duplicate_keys(self) -> None:
        rows = _synthetic_pilot()
        rows.append(rows[0].copy())
        with self.assertRaises(PilotIntegrityError):
            index_pilot(rows)

    def test_rejects_missing_keys(self) -> None:
        rows = _synthetic_pilot()[:-1]
        with self.assertRaises(PilotIntegrityError):
            index_pilot(rows)

    def test_rejects_non_finite(self) -> None:
        rows = _synthetic_pilot()
        rows[0]["effective_u_geom"] = float("nan")
        with self.assertRaises(PilotIntegrityError):
            index_pilot(rows)

    def test_bootstrap_quotas(self) -> None:
        pilot = index_pilot(_synthetic_pilot())
        orders = order_level_deltas(pilot)
        boot = stratified_order_bootstrap(orders, replicas=200, seed=20261004)
        self.assertEqual(boot["quotas"], {"euro-pallet": 6, "rollcontainer": 6})
        self.assertTrue(boot["seeds_kept_together"])
        self.assertEqual(boot["replicas"], 200)
        low, high = boot["interval_95"]
        self.assertLessEqual(low, 0.03)
        self.assertGreaterEqual(high, 0.03)

    def test_leave_one_order_out_known_flip(self) -> None:
        pilot = index_pilot(_synthetic_pilot())
        orders = order_level_deltas(pilot)
        # Un pedido con diferencia grande negativa puede voltear una media pequeña.
        orders[0]["d_preferences_minus_classification"] = -0.40
        for item in orders[0]["by_seed"]:
            item["preferences_minus_classification"] = -0.40
        report = leave_one_order_out(orders)
        self.assertIn("E00", report["orders_that_flip_sign_when_held_out"])
        self.assertEqual(len(report["rows"]), 12)

    def test_known_aggregate(self) -> None:
        report = analyze_pilot(index_pilot(_synthetic_pilot()))
        self.assertTrue(
            math.isclose(
                report["aggregate_equal_weight_per_seed"]["preferences_minus_classification"],
                0.03,
                abs_tol=1e-15,
            )
        )
        self.assertEqual(
            report["contrasts"]["preferences_minus_classification"]["sign_counts"],
            {"positive": 12, "zero": 0, "negative": 0},
        )


if __name__ == "__main__":
    unittest.main()
