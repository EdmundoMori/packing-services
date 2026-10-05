"""Pruebas del lanzador persistente y presupuesto acumulado (sin packing)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1] / "tools"
REPO = Path(__file__).resolve().parents[4]
PY = str((REPO / ".venv" / "bin" / "python").absolute())
RUNCTL = str((HERE / "labeling_runctl.py").absolute())
WORKER = str((HERE / "synthetic_labeling_worker.py").absolute())
TOKEN = "synthetic_labeling_worker.py"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_budget import budget_ledger  # noqa: E402
from labeling_io import atomic_write_json  # noqa: E402
from labeling_runctl import request_stop, status  # noqa: E402


def _start(run_dir: Path, *, sleep: str, mode: str) -> dict:
    env = {**os.environ, "SYNTH_SLEEP": sleep, "SYNTH_MODE": mode}
    proc = subprocess.run(
        [
            PY,
            RUNCTL,
            "start",
            "--run-dir",
            str(run_dir),
            "--run-id",
            "test",
            "--attempt-id",
            "synthetic",
            "--identity-token",
            TOKEN,
            "--",
            PY,
            "-u",
            WORKER,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _wait_status(run_dir: Path, predicate, timeout: float = 4.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = status(run_dir, identity_token=TOKEN)
        if predicate(last):
            return last
        time.sleep(0.05)
    return last


class TestBudgetLedger(unittest.TestCase):
    def test_no_reset_and_preflight_separate(self) -> None:
        led = budget_ledger()
        self.assertFalse(led["clock_resets_on_new_process"])
        self.assertTrue(led["preflight_already_accounted_once"])
        self.assertEqual(led["preflight_wall_seconds_separate"], 35.121554053999716)
        self.assertLess(led["remaining_labeling_wall_seconds"], 13500.0)
        self.assertGreater(led["prior_wall_accounted_for_next_deadline_seconds"], 1200.0)


class TestPersistentLauncher(unittest.TestCase):
    def test_survives_launcher_exit_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            launched = _start(run_dir, sleep="0.6", mode="ok")
            self.assertEqual(launched["status"], "launched")
            self.assertGreater(launched["worker_pid"], 0)
            mid = _wait_status(
                run_dir,
                lambda st: st.get("detected") == "running" or st.get("state", {}).get("status") == "completed",
                timeout=2.0,
            )
            self.assertIn(mid.get("detected"), {"running", "not_running"})
            final = _wait_status(
                run_dir,
                lambda st: st.get("state", {}).get("status") == "completed",
                timeout=3.0,
            )
            self.assertEqual(final["state"]["status"], "completed")
            self.assertTrue((run_dir / "synthetic_result.json").is_file())
            self.assertTrue((run_dir / "stdout.log").exists())
            self.assertTrue((run_dir / "heartbeat.json").is_file())

    def test_duplicate_blocked_while_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            _start(run_dir, sleep="1.5", mode="ok")
            time.sleep(0.15)
            proc = subprocess.run(
                [
                    PY,
                    RUNCTL,
                    "start",
                    "--run-dir",
                    str(run_dir),
                    "--run-id",
                    "dup",
                    "--attempt-id",
                    "synthetic",
                    "--identity-token",
                    TOKEN,
                    "--",
                    PY,
                    "-u",
                    WORKER,
                ],
                capture_output=True,
                text=True,
                cwd=str(REPO),
                env={**os.environ, "SYNTH_SLEEP": "0.2", "SYNTH_MODE": "ok"},
            )
            self.assertNotEqual(proc.returncode, 0)
            request_stop(run_dir, identity_token=TOKEN)
            time.sleep(0.25)

    def test_stale_pid_file_allows_new_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "worker.pid").write_text("999999\n", encoding="utf-8")
            atomic_write_json(
                run_dir / "run_state.json",
                {"status": "running", "identity_token": TOKEN, "pid": 999999},
            )
            launched = _start(run_dir, sleep="0.4", mode="ok")
            self.assertEqual(launched["status"], "launched")
            _wait_status(run_dir, lambda st: st.get("state", {}).get("status") == "completed")
            request_stop(run_dir, identity_token=TOKEN)

    def test_nonzero_exit_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            _start(run_dir, sleep="0.2", mode="fail")
            st = _wait_status(run_dir, lambda s: s.get("state", {}).get("status") == "exited_nonzero")
            self.assertEqual(st["state"]["status"], "exited_nonzero")

    def test_sigterm_interrupt_capturable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            _start(run_dir, sleep="2.5", mode="ok")
            time.sleep(0.2)
            stopped = request_stop(run_dir, identity_token=TOKEN)
            self.assertIn(stopped["status"], {"stopped", "still_alive_after_sigterm"})
            st = _wait_status(
                run_dir,
                lambda s: s.get("state", {}).get("status")
                in {"interrupted_signal", "stopped_by_signal", "completed"},
            )
            self.assertIn(st.get("state", {}).get("status"), {"interrupted_signal", "stopped_by_signal", "completed"})

    def test_dead_without_close_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "worker.pid").write_text("999998\n", encoding="utf-8")
            atomic_write_json(
                run_dir / "run_state.json",
                {"status": "running", "identity_token": TOKEN, "pid": 999998},
            )
            st = status(run_dir, identity_token=TOKEN)
            self.assertEqual(st["detected"], "dead_without_clean_close")


class TestAtomicProgressContract(unittest.TestCase):
    def test_interrupt_preserves_previous_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.json"
            atomic_write_json(path, {"v": 1})
            prev = path.read_bytes()
            with mock.patch("labeling_io.os.replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"v": 2})
            self.assertEqual(path.read_bytes(), prev)


class TestAttempt03PlanExcludesTest(unittest.TestCase):
    def test_plan_pending_no_test(self) -> None:
        study = Path(__file__).resolve().parents[1]
        plan_path = study / "attempt_03_plan.json"
        if not plan_path.is_file():
            self.skipTest("attempt_03_plan missing")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["n_reusable"], 46)
        self.assertEqual(plan["n_pending"], 26)
        self.assertEqual(plan["pending_train"], 2)
        self.assertEqual(plan["pending_development"], 24)
        self.assertFalse(plan["authorization"]["executed"])


if __name__ == "__main__":
    unittest.main()
