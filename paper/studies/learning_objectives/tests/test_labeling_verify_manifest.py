"""Pruebas del verificador basado en manifiesto (staging no oculta fallos)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "tools"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_io import atomic_write_json  # noqa: E402
from labeling_verify import (  # noqa: E402
    VERIFIER_VERSION,
    load_order_result_for_id,
    verify_labeling_output,
)


def _valid_order_payload(order_id: str, *, split: str = "train") -> dict:
    state = {
        "choice_index": 0,
        "support_contract": "greedy_plus_orientation_position_diversity_v1",
        "greedy_in_support": True,
        "support_ids": [[0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]],
        "n_support": 1,
        "alternatives": [
            {
                "action": [0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
                "q_hat": 0.5,
                "recomputed_u_geom": 0.5,
                "capture_saved": True,
                "is_greedy": True,
                "source": "new",
                "features": [0.0] * 17,
                "feature_names": [f"f{i}" for i in range(17)],
            }
        ],
        "complete": True,
        "eligible_for_learning": True,
    }
    return {
        "order_id": order_id,
        "split": split,
        "target": "euro-pallet",
        "selection_hash": "h",
        "signature": "s",
        "status": "ok",
        "selected_indices": [0],
        "states": [state],
        "n_states": 1,
    }


def _write_valid(order_dir: Path, order_id: str) -> None:
    order_dir.mkdir(parents=True, exist_ok=True)
    payload = _valid_order_payload(order_id)
    states = order_dir / "states" / "choice_0"
    states.mkdir(parents=True)
    atomic_write_json(states / "state.json", payload["states"][0])
    atomic_write_json(states / "alt_0_capture.json", {"packed": True}, indent=None)
    atomic_write_json(order_dir / "result.json", payload)


class TestManifestKeyedVerifier(unittest.TestCase):
    def test_missing_expected_not_hidden_by_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "orders" / ".staging_missing1"
            _write_valid(staging, "missing1")
            # destino final ausente
            self.assertFalse((root / "orders" / "missing1" / "result.json").exists())
            entry = load_order_result_for_id(root, "missing1")
            self.assertEqual(entry["load_status"], "missing_expected_result")
            self.assertTrue(entry["staging_present"])
            self.assertIn("staging_exists_but_not_final", entry["issues"])

            manifest = {
                "execution_order": [
                    {
                        "order_id": "missing1",
                        "split": "train",
                        "target": "euro-pallet",
                        "selection_hash": "h",
                        "signature": "s",
                    }
                ]
            }
            summary = {"status": "completed", "pending_order_ids": [], "continuations_reused": 16}
            ver = verify_labeling_output(
                output=root,
                manifest=manifest,
                summary=summary,
                protocol={},
            )
            self.assertEqual(ver["status"], "issues_found")
            self.assertTrue(any("result_missing:missing1" in i for i in ver["issues"]))
            self.assertEqual(ver["n_orders"], 0)
            self.assertFalse(ver["ready_for_training"])

    def test_corrupt_final_not_rescued_by_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            order_dir = root / "orders" / "bad1"
            order_dir.mkdir(parents=True)
            (order_dir / "result.json").write_bytes(b"")
            staging = root / "orders" / ".staging_bad1"
            _write_valid(staging, "bad1")
            entry = load_order_result_for_id(root, "bad1")
            self.assertEqual(entry["load_status"], "corrupt_result")
            self.assertTrue(entry["staging_present"])

            manifest = {
                "execution_order": [
                    {
                        "order_id": "bad1",
                        "split": "train",
                        "target": "euro-pallet",
                        "selection_hash": "h",
                        "signature": "s",
                    }
                ]
            }
            summary = {"status": "completed", "pending_order_ids": [], "continuations_reused": 16}
            ver = verify_labeling_output(
                output=root,
                manifest=manifest,
                summary=summary,
                protocol={},
            )
            self.assertEqual(ver["status"], "issues_found")
            self.assertTrue(any("result_empty:bad1" in i or "corrupt" in i for i in ver["issues"]))
            self.assertFalse(ver["ready_for_training"])

    def test_staging_alone_does_not_count_toward_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid(root / "orders" / "ok1", "ok1")
            _write_valid(root / "orders" / ".staging_extra", "extra")
            manifest = {
                "execution_order": [
                    {
                        "order_id": "ok1",
                        "split": "train",
                        "target": "euro-pallet",
                        "selection_hash": "h",
                        "signature": "s",
                    }
                ]
            }
            # summary incomplete preflight count to avoid other issues dominating
            summary = {"status": "incomplete", "pending_order_ids": ["x"], "continuations_reused": 0}
            ver = verify_labeling_output(output=root, manifest=manifest, summary=summary, protocol={})
            self.assertEqual(ver["n_orders"], 1)
            self.assertEqual(ver["verifier_version"], VERIFIER_VERSION)
            self.assertNotIn("extra", [o["order_id"] for o in ver["coverage"]["by_order"]])


if __name__ == "__main__":
    unittest.main()
