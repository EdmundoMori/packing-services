"""El preflight real solo acepta los cuatro pedidos del manifiesto."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from preflight_real import allowed_preflight_orders, planned_cases  # noqa: E402


def _manifest() -> dict:
    specs = [
        ("00000001", "euro-pallet", 3, "shortest"),
        ("00000002", "euro-pallet", 9, "longest"),
        ("00000003", "rollcontainer", 4, "shortest"),
        ("00000004", "rollcontainer", 8, "longest"),
    ]
    rows = [
        {"order_id": order_id, "target": target, "n_items": n_items, "role": role}
        for order_id, target, n_items, role in specs
    ]
    selected = {
        "euro-pallet": [{"order_id": "00000001"}, {"order_id": "00000002"}],
        "rollcontainer": [{"order_id": "00000003"}, {"order_id": "00000004"}],
    }
    return {"preflight_orders": rows, "selected": selected}


class PreflightGuardTests(unittest.TestCase):
    def test_allowlist_requires_four_train_orders(self) -> None:
        manifest = _manifest()
        allowed = allowed_preflight_orders(manifest)
        self.assertEqual(len(planned_cases(allowed)), 16)
        manifest["preflight_orders"] = manifest["preflight_orders"][:3]
        with self.assertRaises(ValueError):
            allowed_preflight_orders(manifest)

    def test_order_outside_train_is_rejected(self) -> None:
        manifest = _manifest()
        manifest["preflight_orders"][0]["order_id"] = "99999999"
        with self.assertRaises(ValueError):
            allowed_preflight_orders(manifest)


if __name__ == "__main__":
    unittest.main()
