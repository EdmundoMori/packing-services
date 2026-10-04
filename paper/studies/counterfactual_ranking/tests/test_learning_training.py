"""Pruebas sintéticas del ajuste. No leen pedidos reales."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import torch

STUDY_TOOLS = Path(__file__).resolve().parents[1] / "tools"
PAPER_TOOLS = Path(__file__).resolve().parents[3] / "tools"
for entry in (str(PAPER_TOOLS), str(STUDY_TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from campaign import directory_must_be_new  # noqa: E402
from objectives import apply_normalization, fit_normalization  # noqa: E402
from train_loop import (  # noqa: E402
    aggregate_regret,
    epoch_permutations,
    forward_logits,
    paired_start,
    permutation_sha256,
    select_logit_index,
    state_loss,
    train_arm,
    weights_equal,
)


def _state(q_hats: list[float], order_id: str = "o", choice_index: int = 0) -> dict:
    features = torch.zeros((len(q_hats), 17), dtype=torch.float32)
    features[:, 0] = torch.arange(len(q_hats), dtype=torch.float32)
    return {
        "features": features,
        "q_hats": torch.tensor(q_hats, dtype=torch.float64),
        "q_float64": q_hats,
        "order_id": order_id,
        "target": "euro-pallet",
        "choice_index": choice_index,
        "split": "train",
    }


class TrainingLoopTests(unittest.TestCase):
    def test_losses_and_gradients_are_finite(self) -> None:
        for arm in ("classification", "preferences"):
            logits = torch.tensor([0.2, -0.4, 0.1], dtype=torch.float32, requires_grad=True)
            loss = state_loss(logits, torch.tensor([0.0, 0.2, 0.05], dtype=torch.float64), arm)
            loss.backward()
            self.assertTrue(torch.isfinite(loss).item())
            self.assertTrue(torch.isfinite(logits.grad).all().item())

    def test_ties_and_states_without_untied_pairs_keep_a_term(self) -> None:
        logits = torch.tensor([0.3, -0.1], dtype=torch.float32, requires_grad=True)
        q_hats = torch.tensor([0.2, 0.2], dtype=torch.float64)
        preference = state_loss(logits, q_hats, "preferences")
        self.assertAlmostEqual(float(preference.detach()), 0.16, places=5)
        classification = state_loss(torch.zeros(2), q_hats, "classification")
        self.assertAlmostEqual(float(classification.detach()), torch.log(torch.tensor(2.0)).item(), places=5)

    def test_preference_direction(self) -> None:
        q_hats = torch.tensor([0.0, 1.0], dtype=torch.float64)
        wrong = state_loss(torch.tensor([1.0, 0.0]), q_hats, "preferences")
        right = state_loss(torch.tensor([0.0, 1.0]), q_hats, "preferences")
        self.assertLess(float(right), float(wrong))

    def test_each_state_has_the_same_weight(self) -> None:
        short = state_loss(torch.zeros(2), torch.tensor([0.0, 1.0], dtype=torch.float64), "classification")
        long = state_loss(torch.zeros(4), torch.tensor([0.0, 0.0, 0.0, 1.0], dtype=torch.float64), "classification")
        combined = torch.mean(torch.stack([short, long]))
        self.assertAlmostEqual(float(combined), (float(short) + float(long)) / 2)

    def test_pairing_and_permutations(self) -> None:
        left, right, digest = paired_start(11)
        self.assertTrue(weights_equal(left, right))
        self.assertEqual(len(digest), 64)
        first = epoch_permutations(8, 3, 11)
        again = epoch_permutations(8, 3, 11)
        other = epoch_permutations(8, 3, 23)
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertEqual(permutation_sha256(first), permutation_sha256(again))
        self.assertEqual(select_logit_index([0.2, 0.5, 0.5]), 1)

    def test_normalization_is_applied_once(self) -> None:
        stats = fit_normalization([[0.0, 1.0], [0.0, 3.0]])
        once = apply_normalization([0.0, 3.0], stats)
        twice = apply_normalization(once, stats)
        self.assertNotEqual(once, twice)
        self.assertEqual(stats["scale"][0], 1.0)

    def test_checkpoint_is_epoch_40_and_reloads_logits(self) -> None:
        model, _other, _digest = paired_start(11)
        states = [_state([0.0, 0.4]), _state([0.1, 0.1, 0.3], order_id="p", choice_index=1)]
        permutations = epoch_permutations(len(states), 40, 11)
        history = train_arm(model, states, permutations, "classification")
        self.assertEqual(history[-1]["epoch"], 40)
        self.assertEqual(len(history), 40)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.pt"
            torch.save({"epoch": 40, "state_dict": model.state_dict()}, path)
            blob = torch.load(path, map_location="cpu", weights_only=False)
            self.assertEqual(blob["epoch"], 40)
            restored, _ignored, _hash = paired_start(0)
            restored.load_state_dict(blob["state_dict"])
            with torch.no_grad():
                original = forward_logits(model, states[0]["features"]).tolist()
                loaded = forward_logits(restored, states[0]["features"]).tolist()
            self.assertEqual(original, loaded)
        existing = Path(tempfile.mkdtemp())
        with self.assertRaises(FileExistsError):
            directory_must_be_new(existing)

    def test_regret_weights_orders_equally(self) -> None:
        rows = [
            {"order_id": "a", "target": "euro-pallet", "choice_index": 0, "regret": 0.0, "matches_maximum": True, "logit_tie": False, "q_multi_max": False},
            {"order_id": "a", "target": "euro-pallet", "choice_index": 1, "regret": 0.2, "matches_maximum": False, "logit_tie": False, "q_multi_max": True},
            {"order_id": "b", "target": "rollcontainer", "choice_index": 0, "regret": 0.0, "matches_maximum": True, "logit_tie": True, "q_multi_max": False},
        ]
        summary = aggregate_regret(rows)
        self.assertAlmostEqual(summary["per_order"][0]["regret"], 0.1)
        self.assertAlmostEqual(summary["regret"], 0.05)


if __name__ == "__main__":
    unittest.main()
