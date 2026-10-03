"""El contrato de captura de OnlineBPH atraviesa invoke_worker y evaluate_outcome."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compact_study import COMPACT_FLAGS, SUFFIX_REASON, TERMINAL_REASON, capture_online_bph  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402
from pilot_metrics import evaluate_outcome  # noqa: E402


WORKER = r"""
import json
import sys
from pathlib import Path

argv = sys.argv
job = json.loads(Path(argv[argv.index("--job") + 1]).read_text(encoding="utf-8"))
destination = Path(argv[argv.index("--result") + 1])
destination.write_text(json.dumps(job["payload"], ensure_ascii=False), encoding="utf-8")
if job.get("exit_code"):
    raise SystemExit(int(job["exit_code"]))
"""


def _item(item_id: str, length: float, width: float, height: float) -> dict:
    return {
        "item_id": item_id,
        "length_mm": length,
        "width_mm": width,
        "height_mm": height,
        "weight_kg": 1.0,
        "allowed_orientations": "all",
        "volume_mm3": length * width * height,
    }


def _snapshot(items: list[dict]) -> dict:
    return {
        "lookahead_p": 1,
        "select_s": 1,
        "selection": "online_bph_first_feasible_ems",
        "sort_strategy": "input_order",
        "problem_type": "3D_BPP",
        "algorithm": "online_bph",
        "n_containers": 1,
        "consolidate_effective": False,
        "min_support_ratio_effective": 0.0,
        "constraints": dict(COMPACT_FLAGS),
        "items": items,
        "containers": [
            {
                "id": "bin-1",
                "length_mm": 1200.0,
                "width_mm": 800.0,
                "height_mm": 2000.0,
                "volume_mm3": 1200.0 * 800.0 * 2000.0,
                "max_weight_kg": 1500.0,
            }
        ],
    }


def _episode(snapshot: dict, placed: list[dict]) -> dict:
    container = snapshot["containers"][0]
    return {
        "placed": placed,
        "sentinel_lwh_mm": [
            container["length_mm"] + 1.0,
            container["width_mm"] + 1.0,
            container["height_mm"] + 1.0,
        ],
        "setting": 2,
        "orientation": 6,
        "generator": "ems_online_bph",
    }


def _place(item: dict, flb: list[float], oriented: list[float]) -> dict:
    return {"flb_mm": flb, "oriented_lwh_mm": oriented, "item_hint": item["item_id"]}


def _payload(capture: dict | None, *, status: str = "ok") -> dict:
    return {
        "status": status,
        "error": None,
        "attempts": 1,
        "timeout_seconds": 300,
        "capture": capture,
        "returncode": 0,
    }


def _run(job: dict) -> dict:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        script = root / "synthetic_worker.py"
        script.write_text(WORKER, encoding="utf-8")
        return invoke_worker(
            job,
            case_dir=root / "case",
            timeout_s=30,
            command=[sys.executable, str(script), "--job", str(root / "case" / "job.json"), "--result", str(root / "case" / "worker_result.partial")],
        )


def _score(outcome: dict, snapshot: dict) -> dict:
    volume = float(snapshot["containers"][0]["volume_mm3"])
    return evaluate_outcome(
        outcome,
        order_id="case-1",
        method="online_bph",
        target="euro_pallet",
        container_volume_mm3=volume,
        run_id="16a-contract",
        snapshot=snapshot,
    )


class OnlineBphCaptureContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.items = [
            _item("a", 30.0, 40.0, 50.0),
            _item("b", 20.0, 20.0, 20.0),
            _item("c", 10.0, 10.0, 10.0),
        ]
        self.snapshot = _snapshot(self.items)
        placed = [
            _place(self.items[0], [0.0, 0.0, 0.0], [50.0, 30.0, 40.0]),
        ]
        episode = _episode(self.snapshot, placed)
        episode["placed"].append(
            {
                "flb_mm": [0.0, 0.0, 0.0],
                "oriented_lwh_mm": episode["sentinel_lwh_mm"],
            }
        )
        self.capture = capture_online_bph(
            self.snapshot,
            episode,
            order_id="case-1",
            dataset="/tmp/orders.json",
            dataset_sha256="abc",
        )

    def test_valid_capture_survives_worker_and_audit(self) -> None:
        outcome = _run({"payload": _payload(self.capture)})
        self.assertEqual(outcome["status"], "ok")
        self.assertIsInstance(outcome["capture"], dict)
        self.assertEqual(outcome["capture"]["placements"][0]["oriented_lwh_mm"], [50.0, 30.0, 40.0])
        self.assertIsNone(outcome["capture"]["physical_stability_verified"])
        scored = _score(outcome, self.snapshot)
        self.assertEqual(scored["failure_types"], [])
        self.assertGreater(scored["effective_u_geom"], 0.0)
        self.assertFalse(scored["input_mismatch"])
        self.assertFalse(scored["geometry_invalid"])

    def test_missing_capture_is_still_rejected(self) -> None:
        outcome = _run({"payload": _payload(None)})
        self.assertNotEqual(outcome["status"], "ok")
        self.assertIsNone(outcome["capture"])
        self.assertIn("sin captura", outcome["error"])
        scored = _score(outcome, self.snapshot)
        self.assertEqual(scored["effective_u_geom"], 0.0)
        self.assertIn("method_failure", scored["failure_types"])

    def test_capture_incompatible_with_snapshot_is_rejected(self) -> None:
        foreign = json.loads(json.dumps(self.snapshot))
        foreign["items"][0]["length_mm"] = 31.0
        outcome = _run({"payload": _payload(self.capture)})
        scored = _score(outcome, foreign)
        self.assertTrue(scored["input_mismatch"])
        self.assertEqual(scored["effective_u_geom"], 0.0)
        self.assertIn("input_mismatch", scored["failure_types"])

    def test_oriented_height_change_sentinel_and_suffix_are_preserved(self) -> None:
        outcome = _run({"payload": _payload(self.capture)})
        capture = outcome["capture"]
        placement = capture["placements"][0]
        self.assertEqual(placement["original_lwh_mm"], [30.0, 40.0, 50.0])
        self.assertEqual(placement["oriented_lwh_mm"][2], 40.0)
        self.assertNotEqual(placement["oriented_lwh_mm"][2], placement["original_lwh_mm"][2])
        identities = [row["item_id"] for row in capture["input_items"]]
        self.assertEqual(identities, ["a", "b", "c"])
        self.assertEqual(len(capture["placements"]), 1)
        blob = json.dumps(capture)
        self.assertNotIn("1201.0", blob)
        self.assertEqual(capture["unpacked"][0]["reason"], TERMINAL_REASON)
        self.assertEqual(capture["unpacked"][1]["reason"], SUFFIX_REASON)
        self.assertEqual(capture["recipe"]["algorithm"], "online_bph")
        self.assertNotIn("PCT", capture["recipe"]["algorithm"])
        scored = _score(outcome, self.snapshot)
        self.assertEqual(scored["n_packed"], 1)
        self.assertEqual(scored["n_unpacked"], 2)
        self.assertEqual(scored["failure_types"], [])

    def test_invalid_geometry_scores_zero(self) -> None:
        placed = [
            _place(self.items[0], [0.0, 0.0, 0.0], [30.0, 40.0, 50.0]),
            _place(self.items[1], [0.0, 0.0, 0.0], [20.0, 20.0, 20.0]),
        ]
        capture = capture_online_bph(
            self.snapshot,
            _episode(self.snapshot, placed),
            order_id="case-1",
            dataset="/tmp/orders.json",
            dataset_sha256="abc",
        )
        outcome = _run({"payload": _payload(capture)})
        scored = _score(outcome, self.snapshot)
        self.assertTrue(scored["geometry_invalid"])
        self.assertEqual(scored["effective_u_geom"], 0.0)
        self.assertIn("geometry_invalid", scored["failure_types"])

    def test_nonzero_exit_is_not_scored_even_with_capture(self) -> None:
        outcome = _run({"payload": _payload(self.capture), "exit_code": 3})
        self.assertNotEqual(outcome["status"], "ok")
        self.assertIsNone(outcome["capture"])
        self.assertEqual(outcome["worker_failure"], "nonzero_exit")
        scored = _score(outcome, self.snapshot)
        self.assertEqual(scored["effective_u_geom"], 0.0)
        self.assertIn("method_failure", scored["failure_types"])


if __name__ == "__main__":
    unittest.main()
