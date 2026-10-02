"""Selección, bootstrap e interfaz del protocolo 07 con datos sintéticos."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from freeze_independent_sample import (
    EXPECTED_EXCLUSIONS,
    POOL_N,
    QUOTA_N,
    FreezeStopped,
    check_pools,
    frozen_list_sha256,
    rank_ids,
    select_sample,
)
from independent_analysis import bootstrap_primary, interpret_interval, secondary_target_mean
from pilot_common import PilotError, sha256_file
from pilot_preflight import preflight


def _ids(prefix: str, count: int) -> list[str]:
    return [f"{prefix}{index:05d}" for index in range(count)]


def _pools() -> tuple[dict[str, list[str]], dict[str, list[str]], set[str]]:
    pools = {
        "euro-pallet": _ids("E", POOL_N["euro-pallet"]),
        "rollcontainer": _ids("R", POOL_N["rollcontainer"]),
    }
    exclusions = {target: list(EXPECTED_EXCLUSIONS[target]) for target in EXPECTED_EXCLUSIONS}
    full_test = set(pools["euro-pallet"]) | set(pools["rollcontainer"])
    for values in exclusions.values():
        full_test.update(values)
    return pools, exclusions, full_test


class SelectionTests(unittest.TestCase):
    def test_selection_is_reproducible_and_ignores_input_order(self):
        pools, exclusions, full_test = _pools()
        forward = select_sample(pools, exclusions, full_test)
        reversed_pools = {target: list(reversed(ids)) for target, ids in pools.items()}
        backward = select_sample(reversed_pools, exclusions, full_test)
        self.assertEqual(forward["execution_items"], backward["execution_items"])
        self.assertEqual(forward["frozen_list_sha256"], frozen_list_sha256(
            [row["order_id"] for row in forward["execution_items"]]
        ))
        euro = [row for row in forward["execution_items"] if row["target"] == "euro-pallet"]
        roll = [row for row in forward["execution_items"] if row["target"] == "rollcontainer"]
        self.assertEqual(len(euro), 91)
        self.assertEqual(len(roll), 109)
        self.assertEqual(
            [row["order_id"] for row in forward["execution_items"]],
            sorted(row["order_id"] for row in forward["execution_items"]),
        )
        ranked = rank_ids(list(reversed(pools["euro-pallet"])), "euro-pallet")
        self.assertEqual([row["selection_rank"] for row in ranked[:91]], list(range(91)))
        self.assertEqual(ranked, rank_ids(pools["euro-pallet"], "euro-pallet"))

    def test_wrong_pool_or_exclusion_stops_before_selection(self):
        pools, exclusions, full_test = _pools()
        short = {"euro-pallet": pools["euro-pallet"][:-1], "rollcontainer": pools["rollcontainer"]}
        with self.assertRaises(FreezeStopped):
            select_sample(short, exclusions, full_test)
        mixed = {target: list(ids) for target, ids in pools.items()}
        mixed["euro-pallet"] = [EXPECTED_EXCLUSIONS["euro-pallet"][0], *mixed["euro-pallet"][1:]]
        with self.assertRaises(FreezeStopped):
            check_pools(mixed, exclusions, full_test | {EXPECTED_EXCLUSIONS["euro-pallet"][0]})
        self.assertFalse(select_sample(pools, exclusions, full_test)["called_clean"])
        self.assertFalse(select_sample(pools, exclusions, full_test)["absolute_independence"])


class BootstrapTests(unittest.TestCase):
    def test_stratified_paired_interval_is_reproducible(self):
        euro = [1.0] * QUOTA_N["euro-pallet"]
        roll = [0.0] * QUOTA_N["rollcontainer"]
        first = bootstrap_primary(euro, roll)
        second = bootstrap_primary(euro, roll)
        expected = 91 / 200
        self.assertEqual(first, second)
        self.assertEqual(first["replicates"], 20000)
        self.assertEqual(first["seed"], 20261002)
        self.assertEqual(first["percentile_method"], "linear")
        self.assertAlmostEqual(first["mean_delta"], expected)
        self.assertAlmostEqual(first["ci_low"], expected)
        self.assertAlmostEqual(first["ci_high"], expected)
        self.assertEqual(first["interpretation"], "ventaja_media")
        self.assertFalse(first["equality_demonstrated"])
        self.assertEqual(len(euro) + len(roll), 200)

    def test_interpretation_covers_sign_and_does_not_call_zero_equality(self):
        self.assertEqual(interpret_interval(0.01, 0.2), "ventaja_media")
        self.assertEqual(interpret_interval(-0.2, -0.01), "desventaja_media")
        self.assertEqual(interpret_interval(-0.05, 0.04), "no_concluyente")
        self.assertEqual(interpret_interval(0.0, 0.1), "no_concluyente")
        self.assertEqual(interpret_interval(-0.1, 0.0), "no_concluyente")
        secondary = secondary_target_mean([0.4] * 10)
        self.assertEqual(secondary["role"], "secundario")
        self.assertFalse(secondary["used_as_primary"])
        with self.assertRaises(ValueError):
            bootstrap_primary([1.0, 2.0], [0.0])


class ProtocolInterfaceTests(unittest.TestCase):
    def test_independent_preflight_rejects_a_validation_subset_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            protocol = Path(tmp) / "protocol.json"
            protocol.write_text(
                json.dumps({"protocol_id": "07_independent_evaluation", "orders": {"n": 1}}),
                encoding="utf-8",
            )
            with self.assertRaises(PilotError) as caught:
                preflight(
                    protocol_path=protocol,
                    dataset_path=Path(tmp) / "source.json",
                    checkpoint_path=Path(tmp) / "checkpoint.bin",
                    manifest_path=Path(tmp) / "manifest.json",
                )
            self.assertIn("07", str(caught.exception))

    def test_independent_preflight_accepts_a_synthetic_frozen_sample(self):
        import pilot_preflight
        from freeze_independent_sample import protocol_items

        pools, exclusions, full_test = _pools()
        selected = select_sample(pools, exclusions, full_test)
        items = protocol_items(selected)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = {}
            for target, ids in pools.items():
                for order_id in ids:
                    dataset[order_id] = {
                        "properties": {"target": target},
                        "item_sequence": {
                            "1": {
                                "length/mm": 100.0,
                                "width/mm": 80.0,
                                "height/mm": 60.0,
                                "weight/kg": 1.0,
                            }
                        },
                    }
            exposure = {
                "by_target": {
                    target: {
                        "absent_from_inspected_sources": {"ids": pools[target]},
                        "positive_exclusion": {"ids": exclusions[target]},
                    }
                    for target in pools
                }
            }
            paths = {
                "dataset": root / "source.json",
                "full": root / "full_split.json",
                "exposure": root / "exposure.json",
                "freeze": root / "freeze.json",
                "checkpoint": root / "checkpoint.bin",
                "protocol": root / "protocol.json",
            }
            paths["dataset"].write_text(json.dumps(dataset), encoding="utf-8")
            paths["full"].write_text(json.dumps({"test": sorted(full_test)}), encoding="utf-8")
            paths["exposure"].write_text(json.dumps(exposure), encoding="utf-8")
            paths["freeze"].write_text("{}\n", encoding="utf-8")
            paths["checkpoint"].write_bytes(b"bytes-only\n")
            protocol = {
                "protocol_id": "07_independent_evaluation",
                "evaluation_executed": False,
                "not_scale_val": True,
                "methods": {"A": {"sha256": sha256_file(paths["checkpoint"])}},
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
                    "n": 200,
                    "n_euro_pallet": 91,
                    "n_rollcontainer": 109,
                    "source_dataset_sha256": sha256_file(paths["dataset"]),
                    "full_test_manifest": str(paths["full"]),
                    "full_test_sha256": sha256_file(paths["full"]),
                    "exposure_file": str(paths["exposure"]),
                    "exposure_sha256": sha256_file(paths["exposure"]),
                    "freeze_file": str(paths["freeze"]),
                    "freeze_sha256": sha256_file(paths["freeze"]),
                    "frozen_list_sha256": selected["frozen_list_sha256"],
                    "items": items,
                },
            }
            paths["protocol"].write_text(json.dumps(protocol), encoding="utf-8")
            original_build = pilot_preflight.build_problem
            original_snapshot = pilot_preflight.problem_snapshot
            original_root = pilot_preflight.REPO_ROOT

            def fake_build(orders, order_id, method, checkpoint, *, lookahead_p, select_s):
                row = next(item for item in items if item["order_id"] == order_id)
                return {
                    "containers": [
                        {
                            "id": row["container_id"],
                            "length_mm": row["container_length_mm"],
                            "width_mm": row["container_width_mm"],
                            "height_mm": row["container_height_mm"],
                            "max_weight_kg": row["max_weight_kg"],
                            "volume_mm3": row["container_volume_mm3"],
                        }
                    ],
                    "items": [
                        {
                            "length_mm": 100.0,
                            "width_mm": 80.0,
                            "height_mm": 60.0,
                            "weight_kg": 1.0,
                            "allowed_orientations": "all",
                        }
                    ],
                    "constraints": protocol["common_conditions"][2]["value"],
                    "lookahead_p": lookahead_p,
                    "select_s": select_s,
                    "selection": "best_fit",
                    "sort_strategy": "input_order",
                    "problem_type": "3D_BPP",
                    "n_containers": 1,
                    "min_support_ratio_effective": 0.0,
                    "consolidate_effective": False,
                    "algorithm": "drl_policy_3d_bpp" if method == "actor" else "online_3d_bpp_heuristic",
                    "model_path": str(checkpoint) if method == "actor" else None,
                }

            pilot_preflight.REPO_ROOT = root
            pilot_preflight.build_problem = fake_build
            pilot_preflight.problem_snapshot = lambda problem: problem
            try:
                report = preflight(
                    protocol_path=paths["protocol"],
                    dataset_path=paths["dataset"],
                    checkpoint_path=paths["checkpoint"],
                )
            finally:
                pilot_preflight.REPO_ROOT = original_root
                pilot_preflight.build_problem = original_build
                pilot_preflight.problem_snapshot = original_snapshot
        self.assertEqual(report["n_orders"], 200)
        self.assertEqual(report["protocol_id"], "07_independent_evaluation")
        self.assertFalse(report["checkpoint_loaded"])
        self.assertFalse(report["workers_started"])
        self.assertEqual(report["n_euro_pallet"], 91)
        self.assertEqual(report["n_rollcontainer"], 109)
        self.assertTrue(report["equivalent_configs"])


if __name__ == "__main__":
    unittest.main()
