"""Contrato del packing de la ablación. Datos sintéticos; no abre los diez modelos publicados."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ablation_aggregate import aggregate_development, expected_case_keys  # noqa: E402
from ablation_contract import AblationError, load_contract, sha256_file  # noqa: E402
from ablation_pack import (  # noqa: E402
    TIMEOUT_SECONDS,
    assert_geometric_equivalence,
    build_order_snapshots,
    execute_packing_cases,
    packing_provenance,
    preflight_packing,
    row_from_outcome,
    verify_research_artifacts,
)
from ablation_train import research_checkpoint, save_research_checkpoint  # noqa: E402
from pilot_execute import invoke_worker  # noqa: E402

PROTOCOL = Path("/home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json")
FREEZE = Path("/home/edmundo/packing-services/paper/results/10_normalization_freeze.json")
REAL_RUN = Path("/home/edmundo/packing-services/paper/results/11_normalization_ablation")
TRAINING_PACK_HASH = "9d18a8eac4b11d20f0c6e20582c3d3186964fd35772dce6741ebb9727628eac6"


def _orders() -> dict:
    return {
        "SYN1": {
            "properties": {"target": "euro-pallet"},
            "item_sequence": {
                "1": {
                    "sequence": 1,
                    "id": "caja-a",
                    "length/mm": 200,
                    "width/mm": 150,
                    "height/mm": 100,
                    "weight/kg": 1,
                },
                "2": {
                    "sequence": 2,
                    "id": "caja-b",
                    "length/mm": 180,
                    "width/mm": 120,
                    "height/mm": 80,
                    "weight/kg": 1,
                },
            },
        }
    }


def _statistics() -> tuple[dict, str]:
    import hashlib

    from normalization_features import FEATURE_NAMES

    statistics = {
        "feature_names": list(FEATURE_NAMES),
        "mean": [0.0] * len(FEATURE_NAMES),
        "std": [1.0] * len(FEATURE_NAMES),
        "denominator": [1.0] * len(FEATURE_NAMES),
    }
    canonical = json.dumps(statistics, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return statistics, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _save_artifact(path: Path, arm: str, seed: int, statistics: dict) -> str:
    import torch

    state = {
        "0.weight": torch.zeros(64, 35),
        "0.bias": torch.zeros(64),
        "2.weight": torch.zeros(1, 64),
        "2.bias": torch.zeros(1),
    }
    document = research_checkpoint(
        arm=arm,
        seed=seed,
        fitted={
            "state_dict": state,
            "hidden_size": 64,
            "history": [{"epoch": 1, "val_loss": 1.0}],
            "best_epoch": 1,
            "best_val_loss": 1.0,
            "select_best": "val_loss",
        },
        statistics=statistics,
        initial_state_sha256_value="synthetic",
        permutation_hash="synthetic",
        permutation_indices=[[0]],
        data_sha256={"source": "synthetic"},
        protocol_sha256="synthetic",
        freeze_sha256="synthetic",
        code_hash={},
    )
    save_research_checkpoint(path, document)
    return sha256_file(path)


def _case(order_id: str, role: str = "heuristic", seed: int | None = None) -> dict:
    return {
        "role": role,
        "arm": None if role == "heuristic" else role,
        "seed": seed,
        "order_id": order_id,
        "target": "euro-pallet",
        "dataset": "/tmp/synthetic-orders.json",
        "checkpoint": None if role == "heuristic" else "/tmp/synthetic.pt",
        "standardizer_sha256": None,
    }


def _snapshots(order_id: str) -> dict:
    volume = {"containers": [{"volume_mm3": 1920000000.0}], "model_path": None, "algorithm": "online_3d_bpp_heuristic"}
    return {order_id: {"heuristic": volume, "actor": dict(volume)}}


class PackingContractTests(unittest.TestCase):
    def test_timeout_and_later_failures_continue(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            timeout = invoke_worker(
                {},
                case_dir=root / "sleep",
                timeout_s=0.4,
                command=[sys.executable, "-c", "import time; time.sleep(5)"],
            )
            nonzero = invoke_worker(
                {},
                case_dir=root / "code",
                timeout_s=5,
                command=[sys.executable, "-c", "import sys; sys.exit(2)"],
            )
            unreadable = invoke_worker(
                {},
                case_dir=root / "json",
                timeout_s=5,
                command=[
                    sys.executable,
                    "-c",
                    f"import pathlib; pathlib.Path({str(root / 'json' / 'worker_result.partial')!r}).write_text('{{', encoding='utf-8')",
                ],
            )
            self.assertEqual(timeout["worker_failure"], "timeout")
            self.assertEqual(nonzero["worker_failure"], "nonzero_exit")
            self.assertEqual(unreadable["worker_failure"], "unreadable_json")
            queued = [timeout, nonzero, unreadable]

            def worker(job):
                if job["order_id"] == "CRASH":
                    raise RuntimeError("proceso caído")
                return queued.pop(0)

            cases = [
                _case("T"),
                _case("N"),
                _case("U"),
                _case("CRASH"),
            ]
            snapshots = {}
            for case in cases:
                snapshots.update(_snapshots(case["order_id"]))
            rows = execute_packing_cases(cases, snapshots, root / "out", timeout_s=0.4, worker=worker)
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["effective_u_geom"] == 0.0 for row in rows))
            self.assertEqual(rows[3]["worker_status"], "crash")
            for case in cases:
                result = root / "out" / "cases" / f"heuristic__{case['order_id']}" / "result.json"
                self.assertTrue(result.is_file())

    def test_discrepant_snapshot_zeros_utility_and_keeps_capture(self):
        orders = _orders()
        snapshots = build_order_snapshots(orders, "SYN1", "euro-pallet", Path("/tmp/actor.pt"))
        assert_geometric_equivalence(snapshots["actor"], snapshots["heuristic"])
        capture = {
            "order_id": "SYN1",
            "method": "heuristic",
            "recipe": {
                "method": "heuristic",
                "lookahead_p": snapshots["heuristic"]["lookahead_p"],
                "select_s": snapshots["heuristic"]["select_s"],
                "selection": snapshots["heuristic"]["selection"],
                "sort_strategy": snapshots["heuristic"]["sort_strategy"],
                "problem_type": snapshots["heuristic"]["problem_type"],
                "algorithm": snapshots["heuristic"]["algorithm"],
                "n_containers": snapshots["heuristic"]["n_containers"],
                "consolidate_effective": snapshots["heuristic"]["consolidate_effective"],
                "min_support_ratio_effective": snapshots["heuristic"]["min_support_ratio_effective"],
                "checkpoint_path": None,
                "constraints": snapshots["heuristic"]["constraints"],
            },
            "containers": snapshots["heuristic"]["containers"],
            "input_items": json.loads(json.dumps(snapshots["heuristic"]["items"])),
            "placements": [],
            "unpacked": [],
            "physical_stability_verified": None,
        }
        capture["input_items"][0]["length_mm"] = 1
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)

            def worker(job):
                return {"status": "ok", "attempts": 1, "capture": capture, "duration_seconds": 0.01}

            rows = execute_packing_cases(
                [_case("SYN1")],
                {"SYN1": snapshots},
                root,
                worker=worker,
            )
            self.assertEqual(rows[0]["effective_u_geom"], 0.0)
            self.assertIn("input_mismatch", rows[0]["failure_types"])
            stored = json.loads((root / "cases" / "heuristic__SYN1" / "capture.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, capture)
            self.assertIsNone(stored["physical_stability_verified"])
            for name in ("input.json", "worker.json", "capture.json", "audit.json", "result.json"):
                self.assertTrue((root / "cases" / "heuristic__SYN1" / name).is_file())

    def test_worker_process_preserves_the_full_capture(self):
        statistics, digest = _statistics()
        orders = _orders()
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            dataset = root / "orders.json"
            dataset.write_text(json.dumps(orders), encoding="utf-8")
            checkpoint = root / "raw_seed42.pt"
            _save_artifact(checkpoint, "raw", 42, statistics)
            snapshots = build_order_snapshots(orders, "SYN1", "euro-pallet", checkpoint)
            case = _case("SYN1", role="raw", seed=42)
            case["dataset"] = str(dataset)
            case["checkpoint"] = str(checkpoint.resolve())
            case["standardizer_sha256"] = digest
            rows = execute_packing_cases(
                [case],
                {"SYN1": snapshots},
                root / "packing",
                timeout_s=60,
                worker=None,
            )
            case_dir = root / "packing" / "cases" / "raw__seed42__SYN1"
            stored = json.loads((case_dir / "capture.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["order_id"], "SYN1")
            self.assertEqual(stored["method"], "actor")
            self.assertIsNone(stored["physical_stability_verified"])
            self.assertEqual(
                [item["item_id"] for item in stored["input_items"]],
                [item["item_id"] for item in snapshots["actor"]["items"]],
            )
            self.assertIn("oriented_lwh_mm", stored["placements"][0])
            self.assertNotIn("input_mismatch", rows[0]["failure_types"])
            self.assertIsNone(rows[0]["physical_stability_verified"])
            self.assertFalse((REAL_RUN / "packing").exists())

    def test_artifact_hash_arm_and_seed_come_from_content(self):
        statistics, digest = _statistics()
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            models = []
            for seed in (42, 43, 44, 45, 46):
                for arm in ("raw", "normalized"):
                    path = root / "models" / f"{arm}_seed{seed}.pt"
                    file_hash = _save_artifact(path, arm, seed, statistics)
                    models.append({"path": f"models/{arm}_seed{seed}.pt", "sha256": file_hash, "arm": arm, "seed": seed})
            verify_research_artifacts(root, {"models": models}, digest)
            broken_hash = json.loads(json.dumps({"models": models}))
            broken_hash["models"][0]["sha256"] = "0" * 64

            def forbidden(*args, **kwargs):
                raise AssertionError("un hash incorrecto no debe cargar el artefacto")

            import ablation_pack

            original = ablation_pack.load_research_checkpoint
            ablation_pack.load_research_checkpoint = forbidden
            try:
                with self.assertRaises(AblationError) as ctx:
                    verify_research_artifacts(root, broken_hash, digest)
            finally:
                ablation_pack.load_research_checkpoint = original
            self.assertIn("hash", str(ctx.exception))
            wrong_content = json.loads(json.dumps({"models": models}))
            wrong_content["models"][0]["arm"] = "normalized"
            wrong_content["models"][0]["seed"] = 43
            with self.assertRaises(AblationError) as ctx:
                verify_research_artifacts(root, wrong_content, digest)
            self.assertIn("brazo", str(ctx.exception))

    def test_published_model_hashes_match_without_loading(self):
        verification = json.loads((REAL_RUN / "training_verification.json").read_text(encoding="utf-8"))
        self.assertEqual(len(verification["models"]), 10)
        for row in verification["models"]:
            self.assertEqual(sha256_file(REAL_RUN / row["path"]), row["sha256"])
        before = sha256_file(REAL_RUN / "manifest.json")
        provenance = packing_provenance(REAL_RUN)
        self.assertEqual(sha256_file(REAL_RUN / "manifest.json"), before)
        self.assertEqual(provenance["training_code_sha256"]["paper/tools/ablation_pack.py"], TRAINING_PACK_HASH)
        self.assertNotEqual(
            provenance["packing_code_sha256"]["paper/tools/ablation_pack.py"],
            TRAINING_PACK_HASH,
        )
        self.assertEqual(len(provenance["model_sha256"]), 10)
        self.assertFalse((REAL_RUN / "packing").exists())

    def test_exact_550_keys_reject_foreign_duplicate_and_non_finite(self):
        contract = load_contract(PROTOCOL, FREEZE)
        keys = expected_case_keys(contract["orders"], contract["seeds"])
        self.assertEqual(len(keys), 550)
        self.assertEqual(sum(1 for key in keys if key[1] == "heuristic" and key[2] is None), 50)
        self.assertEqual(sum(1 for key in keys if key[1] in {"raw", "normalized"}), 500)
        self.assertEqual(len({key[0] for key in keys}), 50)
        orders = [{"order_id": "A", "target": "euro-pallet"}, {"order_id": "B", "target": "rollcontainer"}]
        rows = []
        for order in orders:
            rows.append(
                {
                    "order_id": order["order_id"],
                    "role": "heuristic",
                    "seed": None,
                    "effective_u_geom": 0.0,
                    "failure": True,
                    "target": order["target"],
                }
            )
        for seed in (42, 43, 44, 45, 46):
            for order in orders:
                for role, utility in (("raw", 0.2), ("normalized", 0.3)):
                    failed = order["order_id"] == "B"
                    rows.append(
                        {
                            "order_id": order["order_id"],
                            "role": role,
                            "seed": seed,
                            "effective_u_geom": 0.0 if failed else utility,
                            "failure": failed,
                            "target": order["target"],
                        }
                    )
        summary = aggregate_development(rows, orders)
        self.assertAlmostEqual(summary["normalized_minus_raw_by_seed"][0], 0.05)
        without_failure = (0.3 - 0.2)
        self.assertNotAlmostEqual(summary["normalized_minus_raw_by_seed"][0], without_failure)
        self.assertTrue(summary["advance"]["conditions"]["mean_normalized_minus_raw_positive"])
        foreign = json.loads(json.dumps(rows))
        foreign[0]["order_id"] = "ZZZ"
        with self.assertRaises(AblationError):
            aggregate_development(foreign, orders)
        duplicate = list(rows) + [dict(rows[0])]
        with self.assertRaises(AblationError):
            aggregate_development(duplicate, orders)
        non_finite = json.loads(json.dumps(rows))
        non_finite[0]["effective_u_geom"] = float("nan")
        with self.assertRaises(AblationError):
            aggregate_development(non_finite, orders)

    def test_preflight_rejects_protocol_drift_before_workers(self):
        contract = load_contract(PROTOCOL, FREEZE)
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            (root / "training_verification.json").write_text(
                json.dumps(
                    {
                        "training_status": "complete",
                        "discrepancies": [],
                        "protocol_sha256": "distinto",
                        "freeze_sha256": contract["freeze_sha256"],
                        "standardizer_sha256": contract["standardizer_sha256"],
                        "models": [{"path": "models/raw_seed42.pt"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(AblationError) as ctx:
                preflight_packing(contract, root, {})
            self.assertIn("protocolo", str(ctx.exception))
            self.assertFalse((root / "packing").exists())

    def test_internal_evaluator_error_is_not_hidden_as_a_zero(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            root = Path(folder)
            with self.assertRaises(AblationError) as ctx:
                execute_packing_cases([_case("MISSING")], {}, root, worker=lambda job: {"status": "ok"})
            self.assertIn("snapshot", str(ctx.exception))
            self.assertFalse((root / "cases" / "heuristic__MISSING" / "result.json").exists())
        self.assertEqual(TIMEOUT_SECONDS, 300)

    def test_outcome_contrast_uses_the_snapshot(self):
        orders = _orders()
        snapshots = build_order_snapshots(orders, "SYN1", "euro-pallet", Path("/tmp/actor.pt"))
        mutated = json.loads(json.dumps(snapshots["actor"]))
        mutated["items"][0]["weight_kg"] = 99
        with self.assertRaises(AblationError):
            assert_geometric_equivalence(mutated, snapshots["heuristic"])
        row = row_from_outcome(
            {"status": "timeout", "worker_failure": "timeout", "attempts": 1, "capture": None},
            _case("SYN1"),
            snapshots["heuristic"],
        )
        self.assertEqual(row["effective_u_geom"], 0.0)
        self.assertIsNone(row["physical_stability_verified"])
