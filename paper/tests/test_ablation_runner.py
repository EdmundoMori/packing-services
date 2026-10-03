"""Pruebas sintéticas del ejecutor de la ablación. No abren pickle ni el dataset real."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ablation_aggregate import advance_decision, aggregate_development  # noqa: E402
from ablation_contract import (  # noqa: E402
    PRODUCTION_FORMAT,
    AblationError,
    hyperparameters_from_protocol,
    load_contract,
)
from ablation_pack import (  # noqa: E402
    AblationScoreBackend,
    assert_training_ready,
    build_case_plan,
    dataset_sha256_expected,
    pack_case,
)
from ablation_train import (  # noqa: E402
    expected_best_epoch,
    fit_paired_seed,
    initial_state_sha256,
    load_research_checkpoint,
    permutation_sha256,
    research_checkpoint,
    run_training_stage,
    save_research_checkpoint,
    transform_transitions,
)
from normalization_features import candidate_matrix, fit_standardizer, transform_rows  # noqa: E402
from pilot_problems import prepare_imports  # noqa: E402

PROTOCOL = Path("/home/edmundo/packing-services/paper/protocols/10_normalization_ablation.json")
FREEZE = Path("/home/edmundo/packing-services/paper/results/10_normalization_freeze.json")
REAL_RUN = Path("/home/edmundo/packing-services/paper/results/11_normalization_ablation")
STATS_HASH = "9a8604afe01455e5cd1e075ec32f408d42c464e1256173b0c970a7b15c69e266"
LIST_HASH = "f2b969649484166fe02052fbd26c09ba25337f898b74e17ff4ba86db2fd4ae69"


def _synthetic_rows(count: int, prefix: str, statistics: dict | None = None) -> list[dict]:
    prepare_imports()
    from methodology import closed_form_index

    rng = np.random.default_rng(abs(hash(prefix)) % (2**32))
    rows: list[dict] = []
    attempt = 0
    while len(rows) < count:
        attempt += 1
        features = rng.normal(size=(3, 35))
        features[:, 14] *= 800
        features[:, 15] *= 30
        label = (closed_form_index(features) + 1) % 3
        if statistics is not None:
            normalized = transform_rows(features, statistics, arm="normalized")
            if closed_form_index(normalized) == label:
                if attempt > 1000:
                    raise AssertionError("no hay transiciones sintéticas separables")
                continue
        rows.append(
            {
                "order_id": f"{prefix}{len(rows):04d}",
                "step": 0,
                "features": features.tolist(),
                "label": int(label),
                "n_options": 3,
            }
        )
    rows.append(
        {
            "order_id": f"{prefix}single",
            "step": 1,
            "features": rng.normal(size=(1, 35)).tolist(),
            "label": 0,
            "n_options": 1,
        }
    )
    return rows


def _tiny_hyperparameters() -> dict:
    values = hyperparameters_from_protocol(json.loads(PROTOCOL.read_text(encoding="utf-8")))
    values["epochs"] = 3
    return values


class ContractTests(unittest.TestCase):
    def test_frozen_contract_and_hashes(self):
        previous = os.getcwd()
        os.chdir("/tmp")
        try:
            contract = load_contract(PROTOCOL, FREEZE)
        finally:
            os.chdir(previous)
        self.assertEqual(contract["standardizer_sha256"], STATS_HASH)
        self.assertEqual(contract["protocol"]["development_sample"]["frozen_list_sha256"], LIST_HASH)
        self.assertEqual(contract["hyperparameters"]["seeds"], [42, 43, 44, 45, 46])
        self.assertEqual(contract["hyperparameters"]["epochs"], 10)
        self.assertEqual(contract["hyperparameters"]["select_best"], "val_loss")
        self.assertEqual(len(contract["orders"]), 50)
        self.assertTrue(REAL_RUN.is_dir())
        self.assertFalse((REAL_RUN / "packing").exists())


class PairingTests(unittest.TestCase):
    def test_pairing_labels_selection_and_checkpoint_roundtrip(self):
        train_probe = _synthetic_rows(5, "T")
        statistics = fit_standardizer(candidate_matrix(train_probe))
        train_rows = _synthetic_rows(5, "T", statistics)
        val_rows = _synthetic_rows(4, "V", statistics)
        raw = transform_transitions(train_rows, statistics, "raw")
        normalized = transform_transitions(train_rows, statistics, "normalized")
        self.assertEqual([row["label"] for row in raw], [row["label"] for row in train_rows])
        self.assertEqual([row["n_options"] for row in normalized], [row["n_options"] for row in train_rows])
        self.assertEqual(len(raw), len(train_rows))
        self.assertTrue(np.allclose(np.asarray(raw[0]["features"]), np.asarray(train_rows[0]["features"])))
        self.assertFalse(np.allclose(np.asarray(normalized[0]["features"]), np.asarray(train_rows[0]["features"])))
        before = json.dumps(statistics, sort_keys=True)
        paired = fit_paired_seed(
            train_rows,
            val_rows,
            statistics,
            seed=42,
            hyperparameters=_tiny_hyperparameters(),
        )
        self.assertEqual(before, json.dumps(statistics, sort_keys=True))
        self.assertTrue(paired["init_equal"])
        self.assertTrue(paired["permutations_equal"])
        self.assertEqual(paired["initial_state_sha256"], initial_state_sha256(paired["arms"]["raw"]["init"]))
        self.assertEqual(permutation_sha256([[1, 0]]), hashlib.sha256(b"[[1,0]]").hexdigest())
        self.assertEqual(len(paired["permutation_indices"]), 3)
        self.assertEqual(len(paired["permutation_indices"][0]), len(train_rows))
        for arm in ("raw", "normalized"):
            fitted = paired["arms"][arm]["fitted"]
            self.assertEqual(fitted["select_best"], "val_loss")
            self.assertEqual(expected_best_epoch(fitted["history"]), fitted["best_epoch"])
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            scores = {}
            for arm in ("raw", "normalized"):
                document = research_checkpoint(
                    arm=arm,
                    seed=42,
                    fitted=paired["arms"][arm]["fitted"],
                    statistics=statistics,
                    initial_state_sha256_value=paired["initial_state_sha256"],
                    permutation_hash=paired["permutation_sha256"],
                    permutation_indices=paired["permutation_indices"],
                    data_sha256={"source": "caller", "train": "synthetic", "val": "synthetic"},
                    protocol_sha256="synthetic",
                    freeze_sha256="synthetic",
                    code_hash={"synthetic": "synthetic"},
                )
                path = Path(folder) / f"{arm}.pt"
                save_research_checkpoint(path, document)
                loaded = load_research_checkpoint(path)
                rows = train_rows[0]["features"]
                before_score = AblationScoreBackend(document).score(rows)
                after_score = AblationScoreBackend(loaded).score(rows)
                self.assertEqual(before_score, after_score)
                scores[arm] = after_score
                if arm == "normalized":
                    matrix = np.asarray(rows, dtype=np.float64)
                    once = transform_rows(matrix, loaded["transform"]["statistics"], arm="normalized")
                    twice = transform_rows(once, loaded["transform"]["statistics"], arm="normalized")
                    self.assertFalse(np.allclose(once, twice))
                    self.assertNotEqual(after_score, AblationScoreBackend(loaded).score(twice.tolist()))
            self.assertNotEqual(scores["raw"], scores["normalized"])

    def test_incompatible_checkpoint_is_rejected(self):
        prepare_imports()
        from packing_services.online.learned.checkpoint import load_checkpoint_document
        from packing_services.utils.errors import InvalidInputError

        train_rows = _synthetic_rows(5, "R")
        statistics = fit_standardizer(candidate_matrix(train_rows))
        paired = fit_paired_seed(
            train_rows,
            _synthetic_rows(4, "S", statistics),
            statistics,
            seed=43,
            hyperparameters=_tiny_hyperparameters(),
        )
        document = research_checkpoint(
            arm="normalized",
            seed=43,
            fitted=paired["arms"]["normalized"]["fitted"],
            statistics=statistics,
            initial_state_sha256_value=paired["initial_state_sha256"],
            permutation_hash=paired["permutation_sha256"],
            permutation_indices=paired["permutation_indices"],
            data_sha256={"source": "caller"},
            protocol_sha256="synthetic",
            freeze_sha256="synthetic",
            code_hash={},
        )
        with tempfile.TemporaryDirectory(dir="/tmp") as folder:
            path = Path(folder) / "model.pt"
            broken = json.loads(json.dumps({key: value for key, value in document.items() if key != "state_dict"}))
            broken["state_dict"] = document["state_dict"]
            broken["format"] = "otro"
            save_research_checkpoint(path, broken)
            with self.assertRaises(AblationError):
                load_research_checkpoint(path)
            broken["format"] = document["format"]
            names = list(broken["feature_names"])
            names[0], names[1] = names[1], names[0]
            broken["feature_names"] = names
            save_research_checkpoint(path, broken)
            with self.assertRaises(AblationError):
                load_research_checkpoint(path)
            broken["feature_names"] = document["feature_names"]
            broken["transform"]["standardizer_sha256"] = "0" * 64
            save_research_checkpoint(path, broken)
            with self.assertRaises(AblationError):
                load_research_checkpoint(path)
            production = dict(document)
            production["format"] = PRODUCTION_FORMAT
            save_research_checkpoint(path, production)
            with self.assertRaises(AblationError):
                load_research_checkpoint(path)
            research_path = Path(folder) / "ok.pt"
            save_research_checkpoint(research_path, document)
            with self.assertRaises(InvalidInputError):
                load_checkpoint_document(research_path)
            previous = os.getcwd()
            os.chdir("/tmp")
            try:
                loaded = load_research_checkpoint(research_path)
                self.assertEqual(loaded["arm"], "normalized")
            finally:
                os.chdir(previous)


class PackingAndAggregateTests(unittest.TestCase):
    def test_plan_has_550_cases_and_one_shared_heuristic(self):
        contract = load_contract(PROTOCOL, FREEZE)
        cases = build_case_plan(contract)
        self.assertEqual(len(cases), 550)
        self.assertEqual(sum(1 for case in cases if case["role"] == "heuristic"), 50)
        self.assertEqual(sum(1 for case in cases if case["role"] in {"raw", "normalized"}), 500)
        self.assertTrue(all(case["seed"] is None for case in cases if case["role"] == "heuristic"))
        self.assertEqual(dataset_sha256_expected(), "6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc")

    def test_backend_packs_a_synthetic_order(self):
        train_rows = _synthetic_rows(5, "P")
        statistics = fit_standardizer(candidate_matrix(train_rows))
        paired = fit_paired_seed(
            train_rows,
            _synthetic_rows(4, "Q", statistics),
            statistics,
            seed=44,
            hyperparameters=_tiny_hyperparameters(),
        )
        document = research_checkpoint(
            arm="raw",
            seed=44,
            fitted=paired["arms"]["raw"]["fitted"],
            statistics=statistics,
            initial_state_sha256_value=paired["initial_state_sha256"],
            permutation_hash=paired["permutation_sha256"],
            permutation_indices=paired["permutation_indices"],
            data_sha256={"source": "caller"},
            protocol_sha256="synthetic",
            freeze_sha256="synthetic",
            code_hash={},
        )
        orders = {
            "SYN1": {
                "properties": {"target": "euro-pallet"},
                "item_sequence": {
                    "1": {
                        "sequence": 1,
                        "id": "caja",
                        "length/mm": 200,
                        "width/mm": 150,
                        "height/mm": 100,
                        "weight/kg": 1,
                    },
                    "2": {
                        "sequence": 2,
                        "id": "caja",
                        "length/mm": 180,
                        "width/mm": 120,
                        "height/mm": 80,
                        "weight/kg": 1,
                    },
                },
            }
        }
        calls = {"n": 0}
        original = AblationScoreBackend.score

        def counting(self, rows):
            calls["n"] += 1
            return original(self, rows)

        AblationScoreBackend.score = counting
        try:
            with tempfile.TemporaryDirectory(dir="/tmp") as folder:
                dataset = Path(folder) / "orders.json"
                dataset.write_text(json.dumps(orders), encoding="utf-8")
                evaluated = pack_case(
                    orders,
                    {"role": "raw", "seed": 44, "order_id": "SYN1", "target": "euro-pallet", "checkpoint": "research"},
                    dataset_path=dataset,
                    checkpoint=document,
                )
        finally:
            AblationScoreBackend.score = original
        self.assertGreater(calls["n"], 0)
        self.assertEqual(evaluated["order_id"], "SYN1")
        self.assertIn("effective_u_geom", evaluated)

    def test_five_seeds_keep_failures_and_evaluate_the_rule(self):
        orders = [
            {"order_id": "A", "target": "euro-pallet"},
            {"order_id": "B", "target": "rollcontainer"},
        ]
        rows = []
        for order in orders:
            rows.append(
                {
                    "order_id": order["order_id"],
                    "target": order["target"],
                    "role": "heuristic",
                    "seed": None,
                    "effective_u_geom": 0.2 if order["order_id"] == "A" else 0.0,
                    "failure": order["order_id"] == "B",
                }
            )
        for seed in (42, 43, 44, 45, 46):
            for order in orders:
                raw_u = 0.0 if order["order_id"] == "B" else 0.30
                norm_u = 0.0 if order["order_id"] == "B" else 0.40
                if seed == 46 and order["order_id"] == "A":
                    norm_u = 0.10
                rows.append(
                    {
                        "order_id": order["order_id"],
                        "target": order["target"],
                        "role": "raw",
                        "seed": seed,
                        "effective_u_geom": raw_u,
                        "failure": order["order_id"] == "B",
                    }
                )
                rows.append(
                    {
                        "order_id": order["order_id"],
                        "target": order["target"],
                        "role": "normalized",
                        "seed": seed,
                        "effective_u_geom": norm_u,
                        "failure": order["order_id"] == "B",
                    }
                )
        summary = aggregate_development(rows, orders)
        self.assertEqual(len(summary["normalized_minus_raw_by_seed"]), 5)
        self.assertNotIn("best_seed", summary)
        self.assertEqual(summary["failures_in_denominator"]["heuristic_orders"], 1)
        self.assertEqual(summary["failures_in_denominator"]["raw_order_seed"], 5)
        self.assertAlmostEqual(summary["normalized_minus_raw_by_seed"][0], 0.05)
        self.assertTrue(summary["advance"]["conditions"]["at_least_four_seeds_positive"])
        self.assertFalse(summary["confirmatory"])
        blocked = advance_decision([0.1, 0.1, 0.1, -0.2, -0.2], 0.3)
        self.assertFalse(blocked["continue_with_this_configuration"])
        passed = advance_decision([0.1, 0.2, 0.1, 0.1, 0.1], 0.05)
        self.assertTrue(passed["continue_with_this_configuration"])

    def test_training_folder_is_not_reused_or_retried(self):
        calls = {"n": 0}

        def fake_fit(*args, **kwargs):
            calls["n"] += 1
            seed = kwargs["seed"]
            if calls["n"] > 1:
                raise AblationError("corte de prueba")
            prepare_imports()
            import torch
            import train_mlp

            torch.manual_seed(seed)
            model = train_mlp.build_mlp_v1(64)
            state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
            fitted = {
                "state_dict": state,
                "hidden_size": 64,
                "history": [{"epoch": 1.0, "val_loss": 1.0}],
                "best_epoch": 1,
                "best_val_loss": 1.0,
                "select_best": "val_loss",
            }
            return {
                "seed": seed,
                "init_equal": True,
                "permutations_equal": True,
                "initial_state_sha256": initial_state_sha256(state),
                "permutation_sha256": permutation_sha256([[0]]),
                "permutation_indices": [[0]],
                "float32": True,
                "arms": {"raw": {"fitted": fitted}, "normalized": {"fitted": dict(fitted)}},
            }

        import ablation_train

        original = ablation_train.fit_paired_seed
        ablation_train.fit_paired_seed = fake_fit
        try:
            with tempfile.TemporaryDirectory(dir="/tmp") as folder:
                output = Path(folder) / "run"
                with self.assertRaises(AblationError):
                    run_training_stage(
                        protocol_path=PROTOCOL,
                        freeze_path=FREEZE,
                        output_dir=output,
                        command=["synthetic"],
                        transitions={
                            "train": [
                                {
                                    "order_id": "x",
                                    "step": 0,
                                    "features": [[0.0] * 35, [1.0] * 35],
                                    "label": 0,
                                    "n_options": 2,
                                }
                            ],
                            "val": [
                                {
                                    "order_id": "y",
                                    "step": 0,
                                    "features": [[0.0] * 35, [1.0] * 35],
                                    "label": 1,
                                    "n_options": 2,
                                }
                            ],
                        },
                    )
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "incomplete")
                self.assertTrue((output / "models" / "raw_seed42.pt").is_file())
                with self.assertRaises(AblationError):
                    assert_training_ready(output, load_contract(PROTOCOL, FREEZE))
                with self.assertRaises(AblationError):
                    run_training_stage(
                        protocol_path=PROTOCOL,
                        freeze_path=FREEZE,
                        output_dir=output,
                        command=["synthetic"],
                        transitions={"train": [], "val": []},
                    )
        finally:
            ablation_train.fit_paired_seed = original
        self.assertTrue(REAL_RUN.is_dir())
        self.assertFalse((REAL_RUN / "packing").exists())

    def test_complete_training_exposes_ten_artifacts(self):
        def fake_fit(*args, **kwargs):
            prepare_imports()
            import torch
            import train_mlp

            torch.manual_seed(kwargs["seed"])
            model = train_mlp.build_mlp_v1(64)
            state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
            fitted = {
                "state_dict": state,
                "hidden_size": 64,
                "history": [{"epoch": 1.0, "val_loss": 0.5}],
                "best_epoch": 1,
                "best_val_loss": 0.5,
                "select_best": "val_loss",
            }
            return {
                "seed": kwargs["seed"],
                "init_equal": True,
                "permutations_equal": True,
                "initial_state_sha256": initial_state_sha256(state),
                "permutation_sha256": permutation_sha256([[0, 1]]),
                "permutation_indices": [[0, 1]],
                "float32": True,
                "arms": {"raw": {"fitted": fitted}, "normalized": {"fitted": dict(fitted)}},
            }

        import ablation_train

        original = ablation_train.fit_paired_seed
        ablation_train.fit_paired_seed = fake_fit
        transitions = {
            "train": [
                {
                    "order_id": "x",
                    "step": 0,
                    "features": [[0.0] * 35, [1.0] * 35],
                    "label": 0,
                    "n_options": 2,
                }
            ],
            "val": [
                {
                    "order_id": "y",
                    "step": 0,
                    "features": [[0.2] * 35, [0.4] * 35],
                    "label": 1,
                    "n_options": 2,
                }
            ],
        }
        try:
            with tempfile.TemporaryDirectory(dir="/tmp") as folder:
                output = Path(folder) / "run"
                manifest = run_training_stage(
                    protocol_path=PROTOCOL,
                    freeze_path=FREEZE,
                    output_dir=output,
                    command=["synthetic-complete"],
                    transitions=transitions,
                )
                self.assertEqual(manifest["status"], "complete")
                self.assertEqual(len(manifest["models"]), 10)
                self.assertFalse(manifest["real_pickles_opened"])
                ready = assert_training_ready(output, load_contract(PROTOCOL, FREEZE))
                self.assertEqual(len(ready), 10)
                (output / "packing").mkdir()
                with self.assertRaises(AblationError):
                    assert_training_ready(output, load_contract(PROTOCOL, FREEZE))
        finally:
            ablation_train.fit_paired_seed = original
        self.assertTrue(REAL_RUN.is_dir())
        self.assertFalse((REAL_RUN / "packing").exists())


if __name__ == "__main__":
    unittest.main()
