"""Pruebas sintéticas de persistencia atómica, integridad y recuperación."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1] / "tools"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_integrity import audit_labeling_tree, verify_order_artifacts  # noqa: E402
from labeling_io import AtomicWriteError, atomic_write_json, read_json_strict  # noqa: E402
from labeling_recovery import (  # noqa: E402
    REGISTERED_ORDER_WALL_SUM_SECONDS,
    build_recovery_plan,
)


class TestAtomicWrite(unittest.TestCase):
    def test_atomic_write_and_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            atomic_write_json(path, {"a": 1})
            self.assertEqual(read_json_strict(path), {"a": 1})

    def test_interrupt_during_write_preserves_previous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            atomic_write_json(path, {"v": 1})
            previous = path.read_bytes()

            def boom(self):  # noqa: ANN001
                raise OSError("simulated interrupt after temp write")

            with mock.patch("labeling_io.os.replace", side_effect=OSError("killed before replace")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"v": 2})
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(json.loads(previous)["v"], 1)

    def test_empty_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.json"
            path.write_bytes(b"")
            with self.assertRaises(AtomicWriteError):
                read_json_strict(path)


class TestIntegrityProgressNotSoT(unittest.TestCase):
    def _order_tree(self, root: Path, order_id: str, *, ok: bool, empty_result: bool = False) -> None:
        order = root / "orders" / order_id
        states = order / "states" / "choice_0"
        states.mkdir(parents=True)
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
                }
            ],
            "complete": True,
            "eligible_for_learning": True,
        }
        atomic_write_json(states / "state.json", state)
        atomic_write_json(states / "alt_0_capture.json", {"packed": True}, indent=None)
        result = {
            "order_id": order_id,
            "split": "train",
            "target": "euro-pallet",
            "selection_hash": "abc",
            "signature": "def",
            "status": "ok" if ok else "incomplete",
            "selected_indices": [0],
            "states": [state],
            "n_states": 1,
        }
        if empty_result:
            (order / "result.json").write_bytes(b"")
        else:
            atomic_write_json(order / "result.json", result)

    def test_ok_status_with_corrupt_file_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._order_tree(root, "1", ok=True, empty_result=True)
            check = verify_order_artifacts(root / "orders" / "1")
            self.assertEqual(check["classification"], "corrupt")
            self.assertIn("result_empty", check["issues"])

    def test_progress_ok_conflict_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._order_tree(root, "1", ok=True, empty_result=True)
            manifest = {
                "execution_order": [
                    {
                        "order_id": "1",
                        "split": "train",
                        "target": "euro-pallet",
                        "selection_hash": "abc",
                        "signature": "def",
                    },
                    {
                        "order_id": "2",
                        "split": "train",
                        "target": "euro-pallet",
                        "selection_hash": "g",
                        "signature": "h",
                    },
                ]
            }
            progress = {"orders_done": [{"order_id": "1", "status": "ok"}]}
            audit = audit_labeling_tree(root, manifest=manifest, progress=progress)
            self.assertIn("1", audit["by_class"]["corrupt"])
            detail = next(d for d in audit["details"] if d["order_id"] == "1")
            self.assertTrue(detail.get("progress_conflict"))
            self.assertIn("2", audit["by_class"]["never_executed"])

    def test_incomplete_never_marked_reusable_as_ok_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._order_tree(root, "1", ok=False)
            # force status ok in progress sense but missing capture
            order = root / "orders" / "1"
            result = json.loads((order / "result.json").read_text())
            result["status"] = "ok"
            result["states"][0]["alternatives"][0]["capture_saved"] = True
            (order / "states" / "choice_0" / "alt_0_capture.json").unlink()
            atomic_write_json(order / "result.json", result)
            check = verify_order_artifacts(order)
            self.assertNotEqual(check["classification"], "reusable_valid")


class TestRecoveryPlan(unittest.TestCase):
    def test_plan_identifies_pending_and_budget(self) -> None:
        study = Path(__file__).resolve().parents[1]
        interrupted = study / "learning_labels"
        if not (interrupted / "execution_manifest.json").is_file():
            self.skipTest("learning_labels evidence not present")
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_recovery_plan(
                study_dir=study,
                interrupted_output=interrupted,
                recovery_output=Path(tmp) / "recovery",
            )
        self.assertEqual(plan["status"], "designed_not_executed")
        self.assertFalse(plan["authorization"]["executed"])
        self.assertGreaterEqual(len(plan["reusable_order_ids"]), 12)
        self.assertIn("00108806", plan["corrupt_order_ids"])
        self.assertEqual(len(plan["pending_registered_order_ids"]), 59)
        ba = plan["budget_accounting"]
        self.assertEqual(ba["registered_order_wall_sum_seconds"], REGISTERED_ORDER_WALL_SUM_SECONDS)
        self.assertFalse(ba["registered_is_proven_total_wall_bound"])
        self.assertGreater(ba["operational_reserve_seconds"], 0)
        self.assertAlmostEqual(
            ba["remaining_labeling_wall_seconds"],
            13500.0 - ba["prior_wall_accounted_for_deadline_seconds"],
        )
        self.assertEqual(ba["preflight_wall_seconds_separate"], 35.121554053999716)
        self.assertTrue(all(item["split"] != "test" for item in plan["pending_work_in_manifest_order"]))
        self.assertEqual(len(plan["pending_work_in_manifest_order"]), 72)

    def test_hash_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            order = root / "orders" / "1"
            order.mkdir(parents=True)
            atomic_write_json(
                order / "result.json",
                {
                    "order_id": "1",
                    "split": "train",
                    "target": "euro-pallet",
                    "selection_hash": "wrong",
                    "signature": "x",
                    "status": "ok",
                    "selected_indices": [],
                    "states": [],
                    "n_states": 0,
                },
            )
            check = verify_order_artifacts(
                order,
                expected={
                    "order_id": "1",
                    "split": "train",
                    "target": "euro-pallet",
                    "selection_hash": "expected",
                    "signature": "x",
                },
            )
            self.assertIn("mismatch:selection_hash", check["issues"])


class TestSignalHandlersDocumented(unittest.TestCase):
    def test_sigkill_not_installable(self) -> None:
        import signal

        from labeling_io import install_termination_flags, restore_signal_handlers

        flag: dict = {"stop": False}
        prev = install_termination_flags(flag)
        self.assertTrue(hasattr(signal, "SIGKILL"))
        # handlers only for TERM/INT
        restore_signal_handlers(prev)
        self.assertFalse(flag["stop"])


if __name__ == "__main__":
    unittest.main()
