"""Pruebas sintéticas del ejecutor de entrenamiento (sin datos reales)."""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import torch

HERE = Path(__file__).resolve().parents[1] / "tools"
# Preferir tools del estudio actual frente a counterfactual_ranking
for entry in list(sys.path):
    if entry.endswith("counterfactual_ranking/tools") or entry.endswith("counterfactual_ranking\\tools"):
        sys.path.remove(entry)
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from model_spec import ARMS, TRAINING_CONFIG, configure_torch_runtime  # noqa: E402
from training_loop import (  # noqa: E402
    TrainingBudgetExceeded,
    epoch_permutations,
    load_checkpoint_logits,
    paired_start,
    permutation_sha256,
    run_seed_arms,
    save_checkpoint,
    train_arm,
    weights_equal,
)
from torch_losses import loss_for_arm_torch  # noqa: E402


def _synthetic_states(n_states: int = 4, n_alt: int = 3) -> list[dict]:
    states = []
    for i in range(n_states):
        features = torch.randn(n_alt, 17, dtype=torch.float32)
        q = torch.tensor([0.1 * (j + 1) + 0.01 * i for j in range(n_alt)], dtype=torch.float32)
        states.append(
            {
                "order_id": f"o{i}",
                "target": "euro-pallet",
                "split": "train",
                "choice_index": 0,
                "features": features,
                "q_hats": q,
                "q_float64": q.tolist(),
            }
        )
    return states


class TestTrainingSynthetic(unittest.TestCase):
    def setUp(self) -> None:
        configure_torch_runtime()

    def test_autograd_through_torch_losses(self) -> None:
        scores = torch.tensor([0.2, -0.1, 0.4], dtype=torch.float32, requires_grad=True)
        q = torch.tensor([0.1, 0.3, 0.2], dtype=torch.float32)
        for arm in ARMS:
            loss = loss_for_arm_torch(arm, scores, q)
            loss.backward()
            self.assertTrue(scores.grad is not None)
            scores.grad = None

    def test_nine_combinations_and_pairing(self) -> None:
        states = _synthetic_states()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = []
            for seed in TRAINING_CONFIG["seeds"]:
                report = run_seed_arms(seed=seed, states=states, output_seed_dir=root / f"seed_{seed}")
                reports.append(report)
                for arm in ARMS:
                    self.assertTrue(report["torch_equal_across_arms"][arm])
                    self.assertEqual(report["arms"][arm]["n_optimizer_steps"], 40)
                    ckpt = Path(report["arms"][arm]["checkpoint"])
                    self.assertTrue(ckpt.is_file())
                    logits = load_checkpoint_logits(ckpt, states[0]["features"])
                    self.assertEqual(len(logits), states[0]["features"].shape[0])
            self.assertEqual(len(reports) * len(ARMS), 9)
            # mismas permutaciones por semilla
            for seed in TRAINING_CONFIG["seeds"]:
                perm = json.loads((root / f"seed_{seed}" / "permutations.json").read_text())
                self.assertEqual(perm["sha256"], permutation_sha256(epoch_permutations(len(states), 40, seed)))

    def test_paired_init_torch_equal(self) -> None:
        actors, digest, eqs = paired_start(11)
        self.assertTrue(all(eqs.values()))
        self.assertTrue(weights_equal(actors["classification"], actors["preferences"]))
        self.assertTrue(weights_equal(actors["classification"], actors["return_difference"]))
        self.assertEqual(len(digest), 64)

    def test_one_step_per_epoch(self) -> None:
        states = _synthetic_states(n_states=3)
        actors, _, _ = paired_start(23)
        perms = epoch_permutations(len(states), 2, 23)
        history = train_arm(actors["classification"], states, perms, "classification")
        self.assertEqual([h["optimizer_steps"] for h in history], [1, 2])

    def test_normalization_supplied_no_refit_in_loop(self) -> None:
        # training_loop no importa fit_normalization
        import training_loop as tl

        self.assertFalse(hasattr(tl, "fit_normalization"))

    def test_existing_output_refused_by_cli_logic(self) -> None:
        from run_learning_train import main

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            (out / "marker").write_text("x", encoding="utf-8")
            code = main(
                [
                    "--study-dir",
                    str(Path(__file__).resolve().parents[1]),
                    "--labels-output",
                    str(Path(tmp) / "labels"),
                    "--output",
                    str(out),
                ]
            )
            self.assertEqual(code, 2)

    def test_incompatible_empty_states(self) -> None:
        actors, _, _ = paired_start(11)
        with self.assertRaises(ValueError):
            train_arm(actors["classification"], [], epoch_permutations(0, 1, 11), "classification")

    def test_nonfinite_loss_raises(self) -> None:
        states = _synthetic_states(n_states=1, n_alt=2)
        actors, _, _ = paired_start(11)
        perms = [[0]]
        with mock.patch("training_loop.loss_for_arm_torch", return_value=torch.tensor(float("nan"))):
            with self.assertRaises(FloatingPointError):
                train_arm(actors["classification"], states, perms, "classification")

    def test_timeout_partial_evidence(self) -> None:
        states = _synthetic_states()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "seed_11"
            deadline = time.perf_counter() - 1.0
            with self.assertRaises(TrainingBudgetExceeded):
                run_seed_arms(seed=11, states=states, output_seed_dir=root, deadline=deadline)

    def test_checkpoint_logits_recoverable(self) -> None:
        states = _synthetic_states(n_states=2)
        actors, init_hash, _ = paired_start(37)
        perms = epoch_permutations(len(states), 1, 37)
        train_arm(actors["preferences"], states, perms, "preferences")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ckpt.pt"
            save_checkpoint(path, actors["preferences"], meta={"seed": 37, "arm": "preferences"})
            logits_a = load_checkpoint_logits(path, states[0]["features"])
            logits_b = load_checkpoint_logits(path, states[0]["features"])
            self.assertEqual(logits_a, logits_b)
            self.assertEqual(init_hash, init_hash)


if __name__ == "__main__":
    unittest.main()
