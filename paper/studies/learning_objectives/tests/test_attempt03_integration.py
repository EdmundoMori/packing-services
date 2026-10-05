"""Integración: runctl + worker real attempt03 con evidencia sintética (sin packing real)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "tools"
STUDY = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
PY = str((REPO / ".venv" / "bin" / "python").resolve())
RUNCTL = str((HERE / "labeling_runctl.py").resolve())
WORKER = str((HERE / "run_learning_labels_attempt03.py").resolve())
TOKEN = "run_learning_labels_attempt03.py"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_budget import budget_ledger  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
from labeling_runctl import status  # noqa: E402


def _write_valid_order(order_dir: Path, *, order_id: str, split: str, target: str, selection_hash: str, signature: str) -> None:
    order_dir.mkdir(parents=True, exist_ok=True)
    states = order_dir / "states" / "choice_0"
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
                "source": "synthetic_reusable",
            }
        ],
        "complete": True,
        "eligible_for_learning": True,
    }
    atomic_write_json(states / "state.json", state)
    atomic_write_json(states / "alt_0_capture.json", {"packed": True}, indent=None)
    atomic_write_json(
        order_dir / "result.json",
        {
            "order_id": order_id,
            "split": split,
            "target": target,
            "selection_hash": selection_hash,
            "signature": signature,
            "status": "ok",
            "selected_indices": [0],
            "states": [state],
            "n_states": 1,
            "wall_seconds": 0.02,
        },
    )


class TestAttempt03Integration(unittest.TestCase):
    def test_runctl_wires_real_worker_with_synthetic_evidence(self) -> None:
        ledger = budget_ledger()
        manifest = json.loads((STUDY / "learning_labels_recovery" / "execution_manifest.json").read_text(encoding="utf-8"))
        by_id = {row["order_id"]: row for row in manifest["execution_order"]}
        reusable_id = "00100464"
        pending_id = "00109078"
        self.assertIn(reusable_id, by_id)
        self.assertIn(pending_id, by_id)
        self.assertEqual(by_id[pending_id]["split"], "train")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "synthetic_attempt02"
            out = root / "attempt03_out"
            run_dir = root / "run"
            plan_path = root / "plan.json"
            _write_valid_order(
                source / "orders" / reusable_id,
                order_id=reusable_id,
                split=by_id[reusable_id]["split"],
                target=by_id[reusable_id]["target"],
                selection_hash=by_id[reusable_id]["selection_hash"],
                signature=by_id[reusable_id]["signature"],
            )
            plan = {
                "kind": "attempt_03_plan",
                "n_reusable": 1,
                "n_pending": 1,
                "reusable_content_verified_order_ids": [reusable_id],
                "pending_in_manifest_order": [pending_id],
                "source_attempt_02_dir": str(source),
                "budget": ledger,
            }
            atomic_write_json(plan_path, plan)

            launched = subprocess.run(
                [
                    PY,
                    RUNCTL,
                    "start",
                    "--run-dir",
                    str(run_dir),
                    "--run-id",
                    "integration_attempt03",
                    "--attempt-id",
                    "attempt_03_integration",
                    "--identity-token",
                    TOKEN,
                    "--workdir",
                    str(REPO),
                    "--",
                    PY,
                    "-u",
                    WORKER,
                    "--study-dir",
                    str(STUDY),
                    "--plan",
                    str(plan_path),
                    "--output",
                    str(out),
                    "--mock-packing",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(REPO),
            )
            launch_msg = json.loads(launched.stdout.strip().splitlines()[-1])
            self.assertEqual(launch_msg["status"], "launched")
            worker_pid = launch_msg["worker_pid"]

            # Lanzador ya salió; el worker debe seguir o haber completado
            mid = status(run_dir, identity_token=TOKEN)
            self.assertIn(mid.get("detected"), {"running", "not_running", "dead_without_clean_close"})

            # Duplicado bloqueado mientras viva
            if mid.get("detected") == "running":
                dup = subprocess.run(
                    [
                        PY,
                        RUNCTL,
                        "start",
                        "--run-dir",
                        str(run_dir),
                        "--run-id",
                        "dup",
                        "--attempt-id",
                        "attempt_03_integration",
                        "--identity-token",
                        TOKEN,
                        "--",
                        PY,
                        "-u",
                        WORKER,
                        "--study-dir",
                        str(STUDY),
                        "--plan",
                        str(plan_path),
                        "--output",
                        str(root / "dup_out"),
                        "--mock-packing",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(REPO),
                )
                dup_msg = json.loads(dup.stdout.strip().splitlines()[-1])
                self.assertEqual(dup_msg["status"], "refused")

            deadline = time.time() + 120.0
            final = {}
            while time.time() < deadline:
                final = status(run_dir, identity_token=TOKEN)
                st = (final.get("state") or {}).get("status")
                if st in {"completed", "exited_nonzero", "interrupted_signal", "refused_output_exists"}:
                    break
                if final.get("detected") == "dead_without_clean_close":
                    break
                time.sleep(0.2)

            self.assertEqual((final.get("state") or {}).get("status"), "completed", msg=final)
            self.assertEqual((final.get("state") or {}).get("exit_code"), 0)
            self.assertTrue((run_dir / "heartbeat.json").is_file())
            self.assertTrue((run_dir / "stdout.log").exists())
            self.assertTrue((out / "orders" / reusable_id / "result.json").is_symlink() or (out / "orders" / reusable_id / "provenance.json").is_file())
            self.assertTrue((out / "orders" / pending_id / "result.json").is_file())
            summary = json.loads((out / "labeling_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["referenced_order_ids"], [reusable_id])
            self.assertEqual(summary["newly_executed_order_ids"], [pending_id])
            self.assertAlmostEqual(
                float(summary["prior_wall_accounted_seconds"]),
                float(ledger["prior_wall_accounted_for_next_deadline_seconds"]),
            )
            self.assertFalse(summary["test_executed"])
            self.assertFalse(summary.get("provisional_normalization_used"))
            # PID del lanzamiento no debe ser el del test actual
            self.assertNotEqual(worker_pid, os.getpid())

    def test_rejects_test_split(self) -> None:
        from labeling_campaign_safe import run_attempt03_recovery
        from labeling_reuse import PreflightReuseIndex
        from unittest import mock

        ledger = budget_ledger()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            out = root / "out"
            reusable_id = "r1"
            _write_valid_order(
                source / "orders" / reusable_id,
                order_id=reusable_id,
                split="train",
                target="euro-pallet",
                selection_hash="h",
                signature="s",
            )
            plan = {
                "kind": "attempt_03_plan",
                "n_reusable": 1,
                "n_pending": 1,
                "reusable_content_verified_order_ids": [reusable_id],
                "pending_in_manifest_order": ["t1"],
                "budget": ledger,
            }
            ordered = [
                {
                    "order_id": reusable_id,
                    "split": "train",
                    "target": "euro-pallet",
                    "selection_hash": "h",
                    "signature": "s",
                },
                {
                    "order_id": "t1",
                    "split": "test",
                    "target": "euro-pallet",
                    "selection_hash": "h2",
                    "signature": "s2",
                },
            ]
            protocol = {"labeling_wall_seconds": 13500.0, "code_hashes": {}}
            reuse = mock.Mock()
            reuse.reused = 0
            reuse.summary.return_value = {}
            # LabelBudget needs protocol keys — use a thin stub via mock packing that never runs for test
            with mock.patch("labeling_campaign_safe.LabelBudget") as LB:
                inst = LB.return_value
                inst.wall_seconds = 13500.0
                inst.states_used = 0
                inst.continuations_new = 0
                inst.continuations_reused = 0
                inst.continuations_unknown = 0
                inst.pending_continuations = 0
                summary = run_attempt03_recovery(
                    protocol=protocol,
                    ordered=ordered,
                    orders_blob={},
                    dataset="x",
                    dataset_sha256="y",
                    output=out,
                    reuse=reuse,
                    plan=plan,
                    source_attempt02_dir=source,
                    execution_manifest={"execution_order": ordered},
                    label_order_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("should_not_pack")),
                )
            self.assertEqual(summary["status"], "refused_test_split")
            self.assertFalse(summary["test_executed"])


if __name__ == "__main__":
    unittest.main()
