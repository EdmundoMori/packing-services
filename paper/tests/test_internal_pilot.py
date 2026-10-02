"""Evaluador del piloto con pedidos sintéticos y workers simulados."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from pilot_common import NO_CANDIDATE_REASON, TIMEOUT_SECONDS, sha256_file
from pilot_execute import execute_pilot, invoke_worker
from pilot_metrics import aggregate, audit_weight, evaluate_outcome
from pilot_preflight import preflight
from pilot_problems import build_problem, capture_document, shared_config
from pilot_common import PilotError

REPO = Path(__file__).resolve().parents[2]
SPECS = {
    "euro-pallet": ("EURO_PALLET", 1200.0, 800.0, 2000.0, 1920000000.0),
    "rollcontainer": ("ROLLCONTAINER", 800.0, 700.0, 2000.0, 1120000000.0),
}


def _order(order_id: str, target: str, items: list[tuple[float, float, float, float]]) -> dict:
    sequence = {}
    for index, (length, width, height, weight) in enumerate(items, start=1):
        sequence[str(index)] = {
            "sequence": index,
            "id": f"ART{index}",
            "length/mm": length,
            "width/mm": width,
            "height/mm": height,
            "weight/kg": weight,
        }
    return {"item_sequence": sequence, "properties": {"id": order_id, "target": target}}


def _protocol(order_rows: list[dict], hashes: dict, checkpoint_sha: str) -> dict:
    return {
        "amendment": "03A",
        "pilot_executed": False,
        "methods": {"A": {"sha256": checkpoint_sha}},
        "common_conditions": [
            {"id": "p_s", "value": {"lookahead_p": 1, "select_s": 1}},
            {"id": "arrival_order", "value": "input_order"},
            {
                "id": "constraints",
                "value": {
                    "non_overlap": True,
                    "containment": True,
                    "allow_rotation": True,
                    "max_weight": True,
                    "max_weight_kg": 1500.0,
                    "basic_stability": False,
                    "load_bearing": False,
                    "fragility": False,
                    "unloading_sequence": False,
                },
            },
        ],
        "orders": {
            "n": 20,
            "n_euro_pallet": 7,
            "n_rollcontainer": 13,
            "hashes": hashes,
            "items": order_rows,
        },
    }


def _write_world(root: Path) -> dict[str, Path]:
    targets = ["rollcontainer"] * 13 + ["euro-pallet"] * 7
    order_ids = [f"{90000000 + index:08d}" for index in range(20)]
    source = {order_id: _order(order_id, target, [(100.0, 100.0, 100.0, 1.0)]) for order_id, target in zip(order_ids, targets)}
    source["90000099"] = _order("90000099", "euro-pallet", [(50.0, 50.0, 50.0, 1.0)])
    subset = {order_id: source[order_id] for order_id in order_ids}
    rows = []
    for index, (order_id, target) in enumerate(zip(order_ids, targets)):
        container_id, length, width, height, volume = SPECS[target]
        rows.append(
            {
                "position": index,
                "order_id": order_id,
                "target": target,
                "target_subset": target,
                "target_source": target,
                "targets_match": True,
                "container_id": container_id,
                "container_length_mm": length,
                "container_width_mm": width,
                "container_height_mm": height,
                "container_volume_mm3": volume,
                "max_weight_kg": 1500.0,
            }
        )
    dataset = root / "source.json"
    subset_path = root / "subset.json"
    manifest = root / "manifest.json"
    checkpoint = root / "checkpoint.bin"
    protocol_path = root / "protocol.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")
    subset_path.write_text(json.dumps(subset), encoding="utf-8")
    manifest.write_text(json.dumps(order_ids), encoding="utf-8")
    checkpoint.write_bytes(b"not-a-torch-checkpoint\n")
    protocol = _protocol(
        rows,
        {
            "source_dataset": sha256_file(dataset),
            "scale_val_orders": sha256_file(subset_path),
            "scale_val_manifest": sha256_file(manifest),
        },
        sha256_file(checkpoint),
    )
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    return {
        "dataset": dataset,
        "subset": subset_path,
        "manifest": manifest,
        "checkpoint": checkpoint,
        "protocol": protocol_path,
        "fail_id": order_ids[0],
    }


def _empty_capture(snapshot: dict) -> dict:
    return {
        "recipe": {"constraints": snapshot["constraints"], "method": snapshot["algorithm"]},
        "containers": snapshot["containers"],
        "input_items": snapshot["items"],
        "placements": [],
        "unpacked": [
            {"item_id": item["item_id"], "reason": NO_CANDIDATE_REASON}
            for item in snapshot["items"]
        ],
        "physical_stability_verified": None,
    }


def _placed_capture(snapshot: dict) -> dict:
    item = snapshot["items"][0]
    document = _empty_capture(snapshot)
    document["placements"] = [
        {
            "item_id": item["item_id"],
            "container_id": snapshot["containers"][0]["id"],
            "flb_mm": [0, 0, 0],
            "original_lwh_mm": [item["length_mm"], item["width_mm"], item["height_mm"]],
            "oriented_lwh_mm": [item["length_mm"], item["width_mm"], item["height_mm"]],
            "weight_kg": item["weight_kg"],
        }
    ]
    document["unpacked"] = []
    return document


class InternalPilotTests(unittest.TestCase):
    def test_orientation_partial_weight_and_feasible_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            order_id = "90000000"
            orders = {
                order_id: _order(
                    order_id,
                    "euro-pallet",
                    [(10.0, 20.0, 30.0, 1.0), (10.0, 10.0, 10.0, 1.0)],
                )
            }
            problem = build_problem(
                orders,
                order_id,
                "heuristic",
                root / "absent.pt",
                lookahead_p=1,
                select_s=1,
            )
            first, second = problem.items
            packed = SimpleNamespace(
                item_id=first.id,
                container_id=problem.containers[0].id,
                position=SimpleNamespace(x=0, y=0, z=0),
                orientation=SimpleNamespace(length=10, width=30, height=20),
                weight=first.weight,
            )
            unpacked = SimpleNamespace(item_id=second.id, reason=NO_CANDIDATE_REASON)
            solution = SimpleNamespace(packed_items=[packed], unpacked_items=[unpacked])
            document = capture_document(
                problem,
                solution,
                method="heuristic",
                order_id=order_id,
                orders_path=root / "orders.json",
                orders_sha256="abc",
                checkpoint_path=root / "absent.pt",
            )
            self.assertEqual(document["placements"][0]["original_lwh_mm"], [10, 20, 30])
            self.assertEqual(document["placements"][0]["oriented_lwh_mm"], [10, 30, 20])
            self.assertNotIn("orientation", document["placements"][0])
            document["physical_stability_verified"] = True
            document["validation_report"] = {"feasible": False}
            row = evaluate_outcome(
                {"status": "ok", "capture": document, "duration_seconds": 0.1},
                order_id=order_id,
                method="heuristic",
                target="euro-pallet",
                container_volume_mm3=1920000000.0,
                run_id="r",
            )
            self.assertFalse(row["method_failure"])
            self.assertFalse(row["geometry_invalid"])
            self.assertFalse(row["weight_violation"])
            self.assertEqual(row["failure_types"], [])
            self.assertEqual(row["max_height_mm"], 20)
            self.assertGreater(row["effective_u_geom"], 0)
            self.assertEqual(row["n_unpacked_no_candidate"], 1)
            self.assertIsNone(row["physical_stability_verified"])

            altered = json.loads(json.dumps(document))
            altered["placements"][0]["weight_kg"] = 6
            altered_row = evaluate_outcome(
                {"status": "ok", "capture": altered, "duration_seconds": 0.1},
                order_id=order_id,
                method="heuristic",
                target="euro-pallet",
                container_volume_mm3=1920000000.0,
                run_id="r",
            )
            self.assertTrue(altered_row["weight_violation"])
            self.assertFalse(altered_row["geometry_invalid"])
            self.assertFalse(altered_row["method_failure"])
            self.assertEqual(altered_row["effective_u_geom"], 0)
            self.assertGreater(altered_row["raw_u_geom"], 0)

            heavy_orders = {
                order_id: _order(order_id, "euro-pallet", [(100.0, 100.0, 100.0, 800.0), (100.0, 100.0, 100.0, 800.0)])
            }
            heavy = build_problem(
                heavy_orders,
                order_id,
                "heuristic",
                root / "absent.pt",
                lookahead_p=1,
                select_s=1,
            )
            placed = []
            for index, item in enumerate(heavy.items):
                placed.append(
                    SimpleNamespace(
                        item_id=item.id,
                        container_id=heavy.containers[0].id,
                        position=SimpleNamespace(x=index * 100, y=0, z=0),
                        orientation=SimpleNamespace(length=item.length, width=item.width, height=item.height),
                        weight=item.weight,
                    )
                )
            heavy_document = capture_document(
                heavy,
                SimpleNamespace(packed_items=placed, unpacked_items=[]),
                method="heuristic",
                order_id=order_id,
                orders_path=root / "orders.json",
                orders_sha256="abc",
                checkpoint_path=root / "absent.pt",
            )
            heavy_row = evaluate_outcome(
                {"status": "ok", "capture": heavy_document, "duration_seconds": 0.1},
                order_id=order_id,
                method="actor",
                target="euro-pallet",
                container_volume_mm3=1920000000.0,
                run_id="r",
            )
            self.assertTrue(heavy_row["weight_violation"])
            self.assertFalse(heavy_row["geometry_invalid"])
            self.assertEqual(heavy_row["effective_u_geom"], 0)
            self.assertGreater(heavy_row["raw_u_geom"], 0)

            overlap = json.loads(json.dumps(heavy_document))
            overlap["validation_report"] = {"feasible": True}
            for placement, item in zip(overlap["placements"], overlap["input_items"]):
                placement["weight_kg"] = 1
                item["weight_kg"] = 1
                placement["flb_mm"] = [0, 0, 0]
            overlap_row = evaluate_outcome(
                {"status": "ok", "capture": overlap, "duration_seconds": 0.1},
                order_id=order_id,
                method="actor",
                target="euro-pallet",
                container_volume_mm3=1920000000.0,
                run_id="r",
            )
            self.assertTrue(overlap["validation_report"]["feasible"])
            self.assertTrue(overlap_row["geometry_invalid"])
            self.assertFalse(overlap_row["weight_violation"])
            self.assertEqual(overlap_row["effective_u_geom"], 0)

            broken = json.loads(json.dumps(document))
            broken["placements"][0]["weight_kg"] = True
            self.assertFalse(audit_weight(broken)["weight_valid"])
            broken["placements"][0]["weight_kg"] = float("nan")
            self.assertFalse(audit_weight(broken)["weight_valid"])
            broken["placements"][0]["weight_kg"] = -1
            self.assertFalse(audit_weight(broken)["weight_valid"])

    def test_aggregate_keeps_failures_ties_and_targets(self) -> None:
        pairs = []
        for index in range(7):
            pairs.append(
                {
                    "order_id": f"e{index}",
                    "target": "euro-pallet",
                    "container_volume_mm3": 1920000000.0,
                    "delta": 0.2,
                    "actor_failure": False,
                    "heuristic_failure": False,
                }
            )
        for index in range(11):
            pairs.append(
                {
                    "order_id": f"r{index}",
                    "target": "rollcontainer",
                    "container_volume_mm3": 1120000000.0,
                    "delta": 0.0,
                    "actor_failure": False,
                    "heuristic_failure": False,
                }
            )
        pairs.append(
            {
                "order_id": "tie",
                "target": "rollcontainer",
                "container_volume_mm3": 1120000000.0,
                "delta": 1e-9,
                "actor_failure": False,
                "heuristic_failure": False,
            }
        )
        pairs.append(
            {
                "order_id": "loss",
                "target": "rollcontainer",
                "container_volume_mm3": 1120000000.0,
                "delta": -0.4,
                "actor_failure": True,
                "heuristic_failure": False,
            }
        )
        stats = aggregate(pairs)
        expected = (7 * 0.2 + 1e-9 - 0.4) / 20
        self.assertEqual(stats["n"], 20)
        self.assertAlmostEqual(stats["mean_delta"], expected)
        self.assertEqual(stats["wins"], 7)
        self.assertEqual(stats["ties"], 12)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["median_delta"], 0)
        self.assertEqual(stats["actor_failures"], 1)
        self.assertEqual(stats["by_target"]["euro-pallet"]["n"], 7)
        self.assertEqual(stats["by_target"]["euro-pallet"]["wins"], 7)
        self.assertEqual(stats["by_target"]["rollcontainer"]["n"], 13)
        self.assertEqual(stats["by_target"]["rollcontainer"]["actor_failures"], 1)
        self.assertEqual(stats["by_target"]["rollcontainer"]["losses"], 1)
        weighted = sum(pair["delta"] * pair["container_volume_mm3"] for pair in pairs) / sum(
            pair["container_volume_mm3"] for pair in pairs
        )
        self.assertNotAlmostEqual(stats["mean_delta"], weighted)
        hi = math.nextafter(1e-9, 1.0)
        self.assertEqual(aggregate([{**pairs[0], "delta": 1e-9}])["ties"], 1)
        self.assertEqual(aggregate([{**pairs[0], "delta": hi}])["wins"], 1)
        self.assertEqual(aggregate([{**pairs[0], "delta": -hi}])["losses"], 1)

    def test_hash_or_target_aborts_before_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            world = _write_world(root)
            calls: list[int] = []
            original = __import__("pilot_preflight").build_problem

            def wrapped(*args, **kwargs):
                calls.append(1)
                return original(*args, **kwargs)

            import pilot_preflight

            pilot_preflight.build_problem = wrapped
            try:
                protocol = json.loads(world["protocol"].read_text(encoding="utf-8"))
                protocol["orders"]["hashes"]["source_dataset"] = "0" * 64
                world["protocol"].write_text(json.dumps(protocol), encoding="utf-8")
                missing = root / "unused-preflight"
                with self.assertRaises(PilotError) as caught:
                    execute_pilot(
                        protocol_path=world["protocol"],
                        dataset_path=world["dataset"],
                        checkpoint_path=world["checkpoint"],
                        output_dir=missing,
                        preflight_only=True,
                        manifest_path=world["manifest"],
                        subset_path=world["subset"],
                        worker=lambda job: calls.append(2),
                    )
                self.assertEqual(caught.exception.code, "preflight")
                self.assertFalse(missing.exists())
                self.assertTrue(any("dataset fuente" in error for error in caught.exception.details["errors"]))
                output = root / "failed-run"
                with self.assertRaises(PilotError):
                    execute_pilot(
                        protocol_path=world["protocol"],
                        dataset_path=world["dataset"],
                        checkpoint_path=world["checkpoint"],
                        output_dir=output,
                        manifest_path=world["manifest"],
                        subset_path=world["subset"],
                        worker=lambda job: calls.append(2),
                    )
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "preflight_failed")
                self.assertFalse(manifest["complete"])
                self.assertFalse((output / "results.json").exists())

                target_root = root / "target"
                target_root.mkdir()
                world = _write_world(target_root)
                protocol = json.loads(world["protocol"].read_text(encoding="utf-8"))
                protocol["orders"]["items"][0]["target"] = "euro-pallet"
                world["protocol"].write_text(json.dumps(protocol), encoding="utf-8")
                with self.assertRaises(PilotError) as target_caught:
                    preflight(
                        protocol_path=world["protocol"],
                        dataset_path=world["dataset"],
                        checkpoint_path=world["checkpoint"],
                        manifest_path=world["manifest"],
                        subset_path=world["subset"],
                    )
                self.assertTrue(any("target" in error for error in target_caught.exception.details["errors"]))

                same_root = root / "same"
                same_root.mkdir()
                world = _write_world(same_root)
                with self.assertRaises(PilotError) as same_caught:
                    preflight(
                        protocol_path=world["protocol"],
                        dataset_path=world["subset"],
                        checkpoint_path=world["checkpoint"],
                        manifest_path=world["manifest"],
                        subset_path=world["subset"],
                    )
                joined = " ".join(same_caught.exception.details["errors"])
                self.assertIn("subconjunto", joined)
                self.assertIn("fuente", joined)
            finally:
                pilot_preflight.build_problem = original
            self.assertEqual(calls, [])

    def test_existing_directory_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "run"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            calls: list[int] = []
            with self.assertRaises(PilotError) as caught:
                execute_pilot(
                    protocol_path=Path("/tmp/absent-protocol.json"),
                    dataset_path=Path("/tmp/absent-dataset.json"),
                    checkpoint_path=Path("/tmp/absent-checkpoint.bin"),
                    output_dir=output,
                    worker=lambda job: calls.append(1) or {},
                )
            self.assertEqual(caught.exception.code, "output_exists")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertEqual(calls, [])

    def test_paired_run_from_other_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            world = _write_world(root)
            output = root / "run"
            calls: list[tuple[str, str]] = []

            def worker(job: dict) -> dict:
                calls.append((job["order_id"], job["method"]))
                if job["order_id"] == world["fail_id"] and job["method"] == "actor":
                    return {"status": "crash", "error": "boom", "duration_seconds": 0.2, "attempts": 1, "capture": None}
                if job["order_id"] == "90000001" and job["method"] == "actor":
                    raise subprocess.TimeoutExpired(cmd="worker", timeout=300)
                snapshot = json.loads((output / "cases" / job["order_id"] / job["method"] / "input.json").read_text(encoding="utf-8"))
                if job["order_id"] == world["fail_id"] and job["method"] == "heuristic":
                    return {"status": "ok", "duration_seconds": 0.01, "attempts": 1, "capture": _placed_capture(snapshot)}
                return {"status": "ok", "duration_seconds": 0.01, "attempts": 1, "capture": _empty_capture(snapshot)}

            sibling = root / "previous"
            sibling.mkdir()
            (sibling / "results.json").write_text(json.dumps({"rows": [{"order_id": "NOT-IN-RUN"}]}), encoding="utf-8")
            result = execute_pilot(
                protocol_path=world["protocol"],
                dataset_path=world["dataset"],
                checkpoint_path=world["checkpoint"],
                output_dir=output,
                manifest_path=world["manifest"],
                subset_path=world["subset"],
                worker=worker,
            )
            self.assertEqual(result["public"]["n_rows"], 40)
            self.assertEqual(result["public"]["n_pairs"], 20)
            self.assertEqual(len(calls), 40)
            self.assertEqual(calls[0], (world["fail_id"], "actor"))
            self.assertEqual(calls[1], (world["fail_id"], "heuristic"))
            actor_input = json.loads((output / "cases" / world["fail_id"] / "actor" / "input.json").read_text(encoding="utf-8"))
            heuristic_input = json.loads((output / "cases" / world["fail_id"] / "heuristic" / "input.json").read_text(encoding="utf-8"))
            self.assertEqual(shared_config(actor_input), shared_config(heuristic_input))
            self.assertIsNone(heuristic_input["model_path"])
            self.assertTrue(str(actor_input["model_path"]).endswith("checkpoint.bin"))
            results = json.loads((output / "results.json").read_text(encoding="utf-8"))
            paired = json.loads((output / "paired_results.json").read_text(encoding="utf-8"))
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(results["n_rows"], 40)
            self.assertEqual(paired["n_pairs"], 20)
            self.assertEqual(summary["n"], 20)
            self.assertTrue(summary["complete"])
            self.assertEqual({row["run_id"] for row in results["rows"]}, {summary["run_id"]})
            self.assertNotIn("NOT-IN-RUN", json.dumps(results))
            self.assertEqual(summary["actor_failures"], 2)
            self.assertEqual(summary["heuristic_failures"], 0)
            self.assertEqual(summary["n"], 20)
            self.assertEqual(summary["losses"], 1)
            self.assertAlmostEqual(summary["mean_delta"], -(1_000_000 / 1_120_000_000) / 20)
            self.assertEqual(list(Path(output).rglob("*.partial")), [])
            text = (output / "summary.md").read_text(encoding="utf-8")
            self.assertIn("El tiempo es diagnóstico", text)
            self.assertNotIn("Superamos a PCT", text)
            before = (output / "summary.json").read_bytes()
            with self.assertRaises(PilotError) as caught:
                execute_pilot(
                    protocol_path=world["protocol"],
                    dataset_path=world["dataset"],
                    checkpoint_path=world["checkpoint"],
                    output_dir=output,
                    manifest_path=world["manifest"],
                    subset_path=world["subset"],
                    worker=worker,
                )
            self.assertEqual(caught.exception.code, "output_exists")
            self.assertEqual((output / "summary.json").read_bytes(), before)

            cli_output = root / "cli-output"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO / "paper" / "tools" / "run_internal_pilot.py"),
                    "--protocol",
                    str(world["protocol"]),
                    "--dataset",
                    str(world["dataset"]),
                    "--checkpoint",
                    str(world["checkpoint"]),
                    "--manifest",
                    str(world["manifest"]),
                    "--subset",
                    str(world["subset"]),
                    "--output-dir",
                    str(cli_output),
                    "--preflight-only",
                ],
                cwd="/tmp",
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["equivalent_configs"])
            self.assertFalse(payload["checkpoint_loaded"])
            self.assertFalse(payload["workers_started"])
            self.assertNotEqual(payload["files"]["source_dataset"]["path"], payload["files"]["scale_val_orders"]["path"])
            self.assertFalse(cli_output.exists())

    def test_subprocess_timeout_and_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp)
            timed = invoke_worker(
                {},
                case_dir=case / "timeout",
                timeout_s=0.2,
                command=[sys.executable, "-c", "import time; time.sleep(5)"],
            )
            crashed = invoke_worker(
                {},
                case_dir=case / "crash",
                timeout_s=5,
                command=[sys.executable, "-c", "import sys; sys.exit(3)"],
            )
            self.assertEqual(timed["status"], "timeout")
            self.assertIsNone(timed["capture"])
            self.assertEqual(crashed["status"], "crash")
            self.assertIsNone(crashed["capture"])
            self.assertEqual(TIMEOUT_SECONDS, 300)

    def test_sources_do_not_load_the_checkpoint_or_old_block(self) -> None:
        for name in (
            "pilot_preflight.py",
            "pilot_execute.py",
            "pilot_metrics.py",
            "pilot_problems.py",
            "pilot_worker.py",
            "run_internal_pilot.py",
        ):
            text = (TOOLS / name).read_text(encoding="utf-8")
            self.assertNotIn("torch.load", text)
            self.assertNotIn("pilot_orders", text)
        protocol = json.loads((REPO / "paper" / "protocols" / "03_internal_pilot.json").read_text(encoding="utf-8"))
        self.assertFalse(protocol["pilot_executed"])
        self.assertEqual(protocol["amendment"], "03A")
        self.assertFalse(protocol["summary"]["executed"])


if __name__ == "__main__":
    unittest.main()
