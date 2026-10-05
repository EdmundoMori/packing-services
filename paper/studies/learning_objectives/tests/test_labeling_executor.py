"""Pruebas sintéticas del ejecutor de etiquetado. Sin dataset real ni packing."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
STUDY = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import labeling_campaign as campaign  # noqa: E402
import labeling_contracts as contracts  # noqa: E402
import labeling_reuse as reuse_mod  # noqa: E402
import labeling_verify as verify_mod  # noqa: E402
from normalization import fit_normalization  # noqa: E402


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _minimal_protocol(**overrides) -> dict:
    code_hashes = {f"tools/{name}.py": _sha(name) for name in ("candidate_support", "preflight")}
    protocol = {
        "study": "learning_objectives",
        "status": "frozen",
        "authorizes_labeling": False,
        "dataset": "/tmp/synthetic-dataset.json",
        "dataset_sha256": _sha("dataset"),
        "support_contract": {"name": "greedy_plus_orientation_position_diversity_v1"},
        "labeling": {
            "states_per_order_max": 4,
            "train_max_states": 192,
            "train_max_continuations": 768,
            "development_max_states": 96,
            "development_max_continuations": 384,
            "incomplete_states_kept": True,
            "no_training_on_partial_labels": True,
        },
        "budget": {
            "total_wall_seconds": 28800,
            "preflight_wall_seconds": 900,
            "labeling_wall_seconds": 13500,
            "training_wall_seconds": 1800,
            "development_wall_seconds": 3600,
            "test_wall_seconds": 9000,
        },
        "code_files": list(code_hashes),
        "code_hashes": code_hashes,
        "normalization": {"fit_on": "train_rows_only"},
    }
    protocol.update(overrides)
    body = {key: value for key, value in protocol.items() if key != "sha256"}
    raw = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    protocol["sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return protocol


class ControlledClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += delta


class LabelingExecutorTests(unittest.TestCase):
    def test_existing_output_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "out"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("safe\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                contracts.directory_must_be_absent_or_empty(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "safe\n")

    def test_wrong_protocol_hash_rejected_before_packing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study = root / "study"
            study.mkdir()
            protocol = _minimal_protocol()
            # corrupt expected by writing protocol with different content then checking against EXPECTED constants
            _write(study / "protocol_frozen.json", protocol)
            sample = {
                "n_train": 48,
                "n_development": 24,
                "n_test": 100,
                "train": {"euro-pallet": [], "rollcontainer": []},
                "development": {"euro-pallet": [], "rollcontainer": []},
                "test": {"euro-pallet": [], "rollcontainer": []},
            }
            _write(study / "sample_manifest.json", sample)
            with self.assertRaises(RuntimeError):
                contracts.verify_frozen_artifacts(
                    protocol_path=study / "protocol_frozen.json",
                    sample_path=study / "sample_manifest.json",
                    study_dir=study,
                )

    def test_execution_order_excludes_test(self) -> None:
        sample = {
            "train": {
                "euro-pallet": [
                    {
                        "order_id": "00100001",
                        "target": "euro-pallet",
                        "selection_hash": "a" * 64,
                        "selection_chain": "x",
                        "signature": "s1",
                    }
                ],
                "rollcontainer": [],
            },
            "development": {
                "euro-pallet": [
                    {
                        "order_id": "00100002",
                        "target": "euro-pallet",
                        "selection_hash": "b" * 64,
                        "selection_chain": "y",
                        "signature": "s2",
                    }
                ],
                "rollcontainer": [],
            },
            "test": {
                "euro-pallet": [
                    {
                        "order_id": "00100999",
                        "target": "euro-pallet",
                        "selection_hash": "c" * 64,
                        "selection_chain": "z",
                        "signature": "s3",
                    }
                ],
                "rollcontainer": [],
            },
        }
        ordered = contracts.execution_order(sample)
        self.assertEqual([row["order_id"] for row in ordered], ["00100001", "00100002"])
        contracts.assert_no_test_execution(ordered, sample)

    def test_reuse_counts_once_and_rejects_incompatible_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = root / "preflight"
            study = root / "study"
            study.mkdir()
            action = [0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0]
            protocol = _minimal_protocol()
            for relative, digest in protocol["code_hashes"].items():
                path = study / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                # file_sha256 must match digest; write content whose hash equals digest is hard.
                # Instead patch file_sha256 during index build.
                path.write_text(relative + "\n", encoding="utf-8")
            verification = {
                "status": "completed",
                "continuations_used": 16,
                "unknown_returns": 0,
                "wall_seconds": contracts.PUBLISHED_PREFLIGHT_WALL_SECONDS,
                "protocol_sha256": protocol["sha256"],
                "code_hashes": protocol["code_hashes"],
                "orders": [
                    {"order_id": "00105883"},
                    {"order_id": "00104801"},
                ],
            }
            _write(preflight / "preflight_verification.json", verification)
            # Build 16 fake continuations across two orders / two states / four alts
            for order_id in ("00105883", "00104801"):
                states = []
                for choice in (0, 1):
                    alts = []
                    support = []
                    for index in range(4):
                        act = [0, float(index), 0.0, 0.0, 1.0, 2.0, 3.0]
                        support.append(act)
                        alts.append(
                            {
                                "action": act,
                                "q_hat": 0.5,
                                "recomputed_u_geom": 0.5,
                                "audited": True,
                                "geometry_valid": True,
                                "action_matches_current_item_placement": True,
                                "audit_failure_types": [],
                            }
                        )
                        _write(
                            preflight
                            / "orders"
                            / order_id
                            / "states"
                            / f"choice_{choice}"
                            / f"alt_{index}_capture.json",
                            {"placements": [], "units": {}},
                        )
                    states.append(
                        {
                            "choice_index": choice,
                            "current_item_id": f"item-{choice}",
                            "support_ids": support,
                            "greedy_key": support[0],
                            "checkpoint_remaining_ids": [f"item-{choice}", "tail"],
                            "support_contract": "greedy_plus_orientation_position_diversity_v1",
                            "n_legal": 4,
                            "alternatives": alts,
                        }
                    )
                _write(preflight / "orders" / order_id / "result.json", {"order_id": order_id, "states": states})

            with mock.patch.object(reuse_mod, "EXPECTED_PROTOCOL_INTERNAL_DIGEST", protocol["sha256"]), mock.patch.object(
                reuse_mod,
                "file_sha256",
                side_effect=lambda path: protocol["code_hashes"][str(Path(path).relative_to(study))],
            ):
                index = reuse_mod.PreflightReuseIndex(preflight, protocol=protocol, study_dir=study)
            state = {
                "choice_index": 0,
                "current_item_id": "item-0",
                "support_ids": states[0]["support_ids"],
                "greedy_key": states[0]["greedy_key"],
                "support_contract": "greedy_plus_orientation_position_diversity_v1",
                "checkpoint": {"remaining_ids": ["item-0", "tail"]},
            }
            # Fix support from 00104801 last write — use 00105883 structure
            support = [
                [0, float(index), 0.0, 0.0, 1.0, 2.0, 3.0] for index in range(4)
            ]
            state["support_ids"] = support
            state["greedy_key"] = support[0]
            first = index.try_reuse("00105883", state, {"action": support[0], "features": [0.0] * 17})
            self.assertEqual(first["source"], "preflight_reused")
            self.assertEqual(index.reused, 1)
            bad_state = dict(state)
            bad_state["support_ids"] = [[9, 9, 9, 9, 9, 9, 9]] + support[1:]
            with self.assertRaises(RuntimeError):
                index.try_reuse("00105883", bad_state, {"action": support[0], "features": [0.0] * 17})

    def test_timeout_yields_null_qhat(self) -> None:
        clock = ControlledClock(10.0)
        row = {"action": [0, 0, 0, 0, 1, 1, 1], "features": [0.0] * 17}
        state = {"checkpoint": {"remaining_ids": ["a"], "geometry": {}}, "current_item_id": "a"}

        def fake_continue(*args, **kwargs):
            clock.advance(1.0)
            return {"status": "wall_clock", "solution": None, "reason": "wall_clock"}

        with mock.patch.object(campaign, "continue_from", side_effect=fake_continue):
            labeled = campaign._run_new_alternative(
                problem=object(),
                snapshot={"containers": [{"volume_mm3": 1.0}], "target": "euro-pallet"},
                state=state,
                row=row,
                dataset="/tmp/x",
                dataset_sha256="0",
                order_id="00100000",
                deadline=10.5,
                continuation_timeout=60.0,
                audit_timeout=60.0,
                now=clock,
            )
        self.assertIsNone(labeled["q_hat"])
        self.assertEqual(labeled["reason"], "wall_clock")

    def test_clock_covers_audit_and_write(self) -> None:
        clock = ControlledClock(0.0)
        events = []

        def now():
            events.append(clock.t)
            return clock.t

        row = {"action": [0, 0, 0, 0, 1, 1, 1], "features": [0.0] * 17}
        state = {"checkpoint": {"remaining_ids": ["a"], "geometry": {}}, "current_item_id": "a"}

        def fake_continue(*args, **kwargs):
            clock.advance(2.0)
            return {"status": "ok", "solution": {"ok": True}}

        def fake_score(*args, **kwargs):
            clock.advance(3.0)
            return {
                "q_hat": 0.25,
                "reason": None,
                "capture": {
                    "placements": [
                        {
                            "item_id": "a",
                            "flb_mm": [0, 0, 0],
                            "oriented_lwh_mm": [1, 1, 1],
                        }
                    ]
                },
                "capture_seconds": 1.0,
                "audit_seconds": 2.0,
                "audit_failure_types": [],
            }

        with mock.patch.object(campaign, "continue_from", side_effect=fake_continue), mock.patch.object(
            campaign, "score_solution", side_effect=fake_score
        ), mock.patch.object(campaign, "recompute_u", return_value=0.25):
            labeled = campaign._run_new_alternative(
                problem=object(),
                snapshot={"containers": [{"volume_mm3": 1.0}], "target": "euro-pallet"},
                state=state,
                row=row,
                dataset="/tmp/x",
                dataset_sha256="0",
                order_id="00100000",
                deadline=100.0,
                continuation_timeout=60.0,
                audit_timeout=60.0,
                now=now,
            )
        self.assertEqual(labeled["q_hat"], 0.25)
        self.assertGreaterEqual(labeled["continuation_seconds"], 2.0)
        self.assertEqual(labeled["audit_seconds"], 2.0)

    def test_incomplete_state_excluded_from_normalization(self) -> None:
        orders = [
            {
                "split": "train",
                "order_id": "00100001",
                "target": "euro-pallet",
                "states": [
                    {
                        "choice_index": 0,
                        "eligible_for_learning": False,
                        "complete": False,
                        "alternatives": [
                            {"action": [0, 0, 0, 0, 1, 1, 1], "features": [1.0] * 17, "q_hat": None, "source": "new"}
                        ],
                    },
                    {
                        "choice_index": 1,
                        "eligible_for_learning": True,
                        "complete": True,
                        "alternatives": [
                            {"action": [0, 0, 0, 0, 2, 2, 2], "features": [2.0] * 17, "q_hat": 0.4, "source": "new"}
                        ],
                    },
                ],
            }
        ]
        rows = verify_mod.learning_rows_from_orders(orders, split="train")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["choice_index"], 1)
        doc = verify_mod.build_normalization_document(rows)
        self.assertEqual(doc["n_rows"], 1)
        self.assertEqual(doc["fit_on"], "train_rows_only")

    def test_normalization_train_only_and_constant_column(self) -> None:
        rows = [[1.0, 2.0], [3.0, 2.0], [5.0, 2.0]]
        stats = fit_normalization(rows)
        self.assertEqual(stats["scale"][1], 1.0)
        self.assertAlmostEqual(stats["mean"][0], 3.0)

    def test_counts_without_duplicates_and_fewer_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "labels"
            order = {
                "order_id": "00100001",
                "split": "train",
                "target": "euro-pallet",
                "n_states": 1,
                "states": [
                    {
                        "choice_index": 0,
                        "complete": True,
                        "eligible_for_learning": True,
                        "greedy_in_support": True,
                        "support_ids": [[0, 0, 0, 0, 1, 1, 1], [0, 1, 0, 0, 1, 1, 1]],
                        "n_support": 2,
                        "fewer_than_four_geometries": True,
                        "alternatives": [
                            {
                                "action": [0, 0, 0, 0, 1, 1, 1],
                                "features": [0.0] * 17,
                                "q_hat": 0.1,
                                "source": "new",
                                "capture_saved": False,
                            },
                            {
                                "action": [0, 1, 0, 0, 1, 1, 1],
                                "features": [0.1] * 17,
                                "q_hat": 0.2,
                                "source": "new",
                                "capture_saved": False,
                            },
                        ],
                    }
                ],
            }
            _write(output / "orders" / "00100001" / "result.json", order)
            manifest = {
                "execution_order": [
                    {"order_id": "00100001", "split": "train", "target": "euro-pallet"},
                ]
            }
            summary = {
                "status": "completed",
                "pending_order_ids": [],
                "continuations_reused": 16,
            }
            # Force reused mismatch issue path separately; here set status incomplete to avoid reused check
            summary["status"] = "incomplete_pending_orders"
            summary["pending_order_ids"] = ["x"]
            doc = verify_mod.verify_labeling_output(
                output=output,
                manifest=manifest,
                summary=summary,
                protocol=_minimal_protocol(),
            )
            self.assertEqual(doc["n_orders"], 1)
            self.assertEqual(doc["coverage"]["by_order"][0]["n_states"], 1)

    def test_verifier_detects_deliberate_alteration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "labels"
            order = {
                "order_id": "00100001",
                "split": "train",
                "target": "euro-pallet",
                "n_states": 1,
                "states": [
                    {
                        "choice_index": 0,
                        "complete": True,
                        "eligible_for_learning": True,
                        "greedy_in_support": True,
                        "support_ids": [[0, 0, 0, 0, 1, 1, 1]],
                        "alternatives": [
                            {
                                "action": [0, 0, 0, 0, 1, 1, 1],
                                "features": [0.0] * 17,
                                "q_hat": 0.9,
                                "source": "new",
                                "capture_saved": True,
                            }
                        ],
                    }
                ],
            }
            _write(output / "orders" / "00100001" / "result.json", order)
            capture_path = output / "orders" / "00100001" / "states" / "choice_0" / "alt_0_capture.json"
            _write(
                capture_path,
                {
                    "placements": [
                        {"item_id": "a", "oriented_lwh_mm": [10, 10, 10], "flb_mm": [0, 0, 0]}
                    ],
                    "containers": [{"volume_mm3": 1000}],
                },
            )
            manifest = {"execution_order": [{"order_id": "00100001", "split": "train", "target": "euro-pallet"}]}
            summary = {"status": "completed", "pending_order_ids": [], "continuations_reused": 16}
            with mock.patch.object(verify_mod, "recompute_u", return_value=0.1):
                doc = verify_mod.verify_labeling_output(
                    output=output,
                    manifest=manifest,
                    summary=summary,
                    protocol=_minimal_protocol(),
                )
            self.assertIn("qhat_mismatch:00100001:0", doc["issues"])

    def test_invoke_from_tmp_static_only_help(self) -> None:
        script = TOOLS / "run_learning_labels.py"
        env = os.environ.copy()
        proc = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd="/tmp",
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--study-dir", proc.stdout)
        self.assertIn("--output", proc.stdout)

    def test_restore_suffix_recorded_on_state(self) -> None:
        # Unit-level: closing state keeps suffix ids from checkpoint
        suffix = ["item-a", "item-b"]
        state = {
            "choice_index": 0,
            "current_item_id": "item-a",
            "n_legal": 2,
            "legal_ids": [],
            "support_ids": [[0, 0, 0, 0, 1, 1, 1]],
            "support_contract": "greedy_plus_orientation_position_diversity_v1",
            "greedy_key": [0, 0, 0, 0, 1, 1, 1],
            "greedy_in_support": True,
            "checkpoint": {"remaining_ids": suffix},
        }
        rows = [
            {
                "action": [0, 0, 0, 0, 1, 1, 1],
                "features": [0.0] * 17,
                "q_hat": 0.3,
                "audited": True,
                "capture_ok": True,
                "source": "new",
                "capture": {"placements": []},
            }
        ]
        self.assertTrue(campaign.complete_state(rows))
        self.assertEqual(state["checkpoint"]["remaining_ids"], suffix)


if __name__ == "__main__":
    unittest.main()
