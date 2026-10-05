"""Pruebas de pérdidas diferenciables. No cargan datos reales ni checkpoints."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import torch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from losses import (  # noqa: E402
    TIE_COEFFICIENT,
    classification_loss,
    preference_loss,
    return_difference_loss,
)
from torch_losses import (  # noqa: E402
    classification_loss_torch,
    loss_for_arm_torch,
    mean_state_loss_torch,
    preference_loss_torch,
    return_difference_loss_torch,
)


def _stable_classification_reference(logits: list[float], q_hats: list[float]) -> float:
    """Referencia estable vía log-sum-exp; no altera losses.py congelado."""

    peak = max(logits)
    log_z = peak + math.log(sum(math.exp(value - peak) for value in logits))
    best = max(q_hats)
    selected = [1.0 if abs(value - best) <= 1e-9 else 0.0 for value in q_hats]
    total = sum(selected)
    target = [value / total for value in selected]
    return -sum(mass * (logit - log_z) for mass, logit in zip(target, logits) if mass > 0.0)


class TorchLossTests(unittest.TestCase):
    def test_numeric_agreement_float64(self) -> None:
        cases = [
            ([0.0, 1.5, -0.5], [0.1, 0.4, 0.2]),
            ([0.0, 0.0, 0.0], [0.2, 0.2, 0.1]),
            ([2.0], [0.3]),
            ([0.0, 0.0], [0.5, 0.5]),
            ([1.0, -1.0, 0.5, 0.2], [0.0, 0.0, 0.3, 0.1]),
        ]
        for logits, q_hats in cases:
            scores = torch.tensor(logits, dtype=torch.float64, requires_grad=True)
            q = torch.tensor(q_hats, dtype=torch.float64)
            self.assertAlmostEqual(
                float(classification_loss_torch(scores, q).item()),
                classification_loss(logits, q_hats),
                places=10,
            )
            self.assertAlmostEqual(
                float(preference_loss_torch(scores, q).item()),
                preference_loss(logits, q_hats, tie_coefficient=TIE_COEFFICIENT),
                places=10,
            )
            self.assertAlmostEqual(
                float(return_difference_loss_torch(scores, q).item()),
                return_difference_loss(logits, q_hats),
                places=10,
            )

    def test_gradcheck_classification_and_return_difference(self) -> None:
        scores = torch.tensor([0.2, -0.1, 0.4], dtype=torch.float64, requires_grad=True)
        q = torch.tensor([0.1, 0.3, 0.2], dtype=torch.float64)

        def class_fn(s: torch.Tensor) -> torch.Tensor:
            return classification_loss_torch(s, q)

        def rd_fn(s: torch.Tensor) -> torch.Tensor:
            return return_difference_loss_torch(s, q)

        self.assertTrue(torch.autograd.gradcheck(class_fn, (scores.clone().detach().requires_grad_(True),), eps=1e-6, atol=1e-6))
        self.assertTrue(torch.autograd.gradcheck(rd_fn, (scores.clone().detach().requires_grad_(True),), eps=1e-6, atol=1e-6))

    def test_gradcheck_preferences(self) -> None:
        scores = torch.tensor([0.3, -0.2], dtype=torch.float64, requires_grad=True)
        q = torch.tensor([0.1, 0.4], dtype=torch.float64)

        def pref_fn(s: torch.Tensor) -> torch.Tensor:
            return preference_loss_torch(s, q)

        self.assertTrue(torch.autograd.gradcheck(pref_fn, (scores.clone().detach().requires_grad_(True),), eps=1e-6, atol=1e-5))

    def test_gradient_direction_classification(self) -> None:
        scores = torch.tensor([2.0, 0.0], dtype=torch.float64, requires_grad=True)
        q = torch.tensor([0.1, 0.9], dtype=torch.float64)
        loss = classification_loss_torch(scores, q)
        loss.backward()
        grad = scores.grad
        self.assertIsNotNone(grad)
        self.assertTrue(torch.isfinite(grad).all())
        # Mejor Q_hat está en el índice 1: su score debería recibir gradiente ≤ 0
        # (aumentarlo reduce CE) y el índice 0 ≥ 0.
        self.assertGreaterEqual(float(grad[0]), -1e-12)
        self.assertLessEqual(float(grad[1]), 1e-12)

    def test_tied_maxima_and_all_tied_returns(self) -> None:
        scores = torch.tensor([0.0, 0.0, 0.0], dtype=torch.float64, requires_grad=True)
        q_tied_max = torch.tensor([0.2, 0.2, 0.1], dtype=torch.float64)
        loss_max = classification_loss_torch(scores, q_tied_max)
        # target = [0.5, 0.5, 0]; softmax uniforme = 1/3; CE = log(3)
        self.assertAlmostEqual(float(loss_max.item()), math.log(3.0), places=10)
        q_all = torch.tensor([0.4, 0.4, 0.4], dtype=torch.float64)
        self.assertEqual(float(return_difference_loss_torch(scores, q_all).item()), 0.0)
        pref_scores = torch.tensor([1.0, 0.0, -1.0], dtype=torch.float64, requires_grad=True)
        pref = preference_loss_torch(pref_scores, q_all)
        pref.backward()
        self.assertTrue(torch.isfinite(pref).all())
        self.assertTrue(torch.isfinite(pref_scores.grad).all())

    def test_single_candidate_and_no_strict_pairs(self) -> None:
        scores = torch.tensor([0.7], dtype=torch.float64, requires_grad=True)
        q = torch.tensor([0.3], dtype=torch.float64)
        self.assertAlmostEqual(float(classification_loss_torch(scores, q).item()), 0.0, places=12)
        pref = preference_loss_torch(scores, q)
        rd = return_difference_loss_torch(scores, q)
        self.assertEqual(float(pref.item()), 0.0)
        self.assertEqual(float(rd.item()), 0.0)
        (pref + rd).backward()
        self.assertTrue(torch.isfinite(scores.grad).all())
        self.assertEqual(float(scores.grad.item()), 0.0)

    def test_rejects_nan_inf_and_mismatch(self) -> None:
        q = torch.tensor([0.1, 0.2], dtype=torch.float64)
        with self.assertRaises(ValueError):
            classification_loss_torch(torch.tensor([float("nan"), 0.0]), q)
        with self.assertRaises(ValueError):
            preference_loss_torch(torch.tensor([0.0, float("inf")]), q)
        with self.assertRaises(ValueError):
            return_difference_loss_torch(torch.tensor([0.0, 1.0, 2.0]), q)
        with self.assertRaises(ValueError):
            classification_loss_torch(torch.tensor([[0.0, 1.0]]), q)

    def test_extreme_logits_stability(self) -> None:
        logits = [80.0, -80.0, 0.0]
        q_hats = [0.1, 0.9, 0.2]
        scores = torch.tensor(logits, dtype=torch.float64, requires_grad=True)
        q = torch.tensor(q_hats, dtype=torch.float64)
        torch_value = float(classification_loss_torch(scores, q).item())
        stable = _stable_classification_reference(logits, q_hats)
        self.assertTrue(math.isfinite(torch_value))
        self.assertAlmostEqual(torch_value, stable, places=10)
        # losses.py usa math.log(softmax); con logits extremos puede underflow.
        try:
            ref = classification_loss(logits, q_hats)
            if math.isfinite(ref):
                self.assertAlmostEqual(torch_value, ref, places=8)
            else:
                self._extreme_ref_note = "losses.py no finito en logits extremos; verificado vía referencia estable"
        except (OverflowError, ValueError) as exc:
            self._extreme_ref_note = f"losses.py falló en logits extremos: {exc}"

    def test_backward_mean_of_states_and_optimizer_step(self) -> None:
        model = torch.nn.Linear(3, 1, bias=False, dtype=torch.float64)
        torch.nn.init.zeros_(model.weight)
        opt = torch.optim.SGD(model.parameters(), lr=0.1)
        states = [
            (torch.tensor([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=torch.float64), torch.tensor([0.1, 0.8], dtype=torch.float64)),
            (torch.tensor([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.5, 0.5, 0.0]], dtype=torch.float64), torch.tensor([0.2, 0.2, 0.5], dtype=torch.float64)),
        ]
        opt.zero_grad()
        losses = []
        for features, q in states:
            scores = model(features).reshape(-1)
            losses.append(loss_for_arm_torch("preferences", scores, q))
        total = mean_state_loss_torch(losses)
        total.backward()
        self.assertTrue(torch.isfinite(model.weight.grad).all())
        before = model.weight.detach().clone()
        opt.step()
        self.assertFalse(torch.equal(before, model.weight.detach()))


if __name__ == "__main__":
    unittest.main()
