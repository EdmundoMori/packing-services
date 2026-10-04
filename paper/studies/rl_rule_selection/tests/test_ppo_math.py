"""Pruebas del cálculo PPO sobre tensores. No usan pedidos."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch
from torch import nn

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from model import build_actor, build_critic  # noqa: E402
from observation import OBS_DIM  # noqa: E402
from ppo_math import (  # noqa: E402
    CLIP,
    GAE_LAMBDA,
    GAMMA,
    clipped_policy_loss,
    compute_returns,
    detached_log_probs,
    detached_values,
    normalize_advantages,
    probability_ratio,
)


class PpoMathTests(unittest.TestCase):
    def test_constants_match_the_recorded_proposal(self) -> None:
        self.assertEqual(GAMMA, 1.0)
        self.assertEqual(GAE_LAMBDA, 1.0)
        self.assertEqual(CLIP, 0.2)

    def test_old_log_prob_and_value_stay_out_of_the_graph(self) -> None:
        actor = build_actor()
        critic = build_critic()
        observation = torch.randn(4, OBS_DIM)
        action = torch.tensor([0, 1, 2, 0])
        old_log_prob = detached_log_probs(actor, observation, action)
        old_value = detached_values(critic, observation)
        self.assertFalse(old_log_prob.requires_grad)
        self.assertFalse(old_value.requires_grad)
        copied = old_log_prob.clone()
        loss = actor(observation).sum() + critic(observation).sum()
        loss.backward()
        self.assertTrue(torch.equal(old_log_prob, copied))

    def test_ratio_and_clip(self) -> None:
        new_log_prob = torch.tensor([0.0, 0.0])
        old_log_prob = torch.log(torch.tensor([0.5, 0.5]))
        ratio = probability_ratio(new_log_prob, old_log_prob)
        self.assertTrue(torch.allclose(ratio, torch.tensor([2.0, 2.0])))
        positive = clipped_policy_loss(torch.tensor([2.0]), torch.tensor([1.0]))
        self.assertAlmostEqual(float(positive), -1.2)
        negative = clipped_policy_loss(torch.tensor([2.0]), torch.tensor([-1.0]))
        self.assertAlmostEqual(float(negative), 2.0)

    def test_termination_does_not_bootstrap_and_truncation_does(self) -> None:
        rewards = torch.tensor([0.1, 0.2, 0.3])
        values = torch.zeros(3)
        next_values = torch.tensor([0.0, 0.0, 0.4])
        terminated = torch.tensor([False, False, True])
        truncated = torch.tensor([False, False, False])
        returns = compute_returns(rewards, values, next_values, terminated, truncated)
        self.assertTrue(torch.allclose(returns, torch.tensor([0.6, 0.5, 0.3])))
        rewards = torch.tensor([0.1, 0.2])
        values = torch.zeros(2)
        next_values = torch.tensor([0.0, 0.4])
        terminated = torch.tensor([False, False])
        truncated = torch.tensor([False, True])
        returns = compute_returns(rewards, values, next_values, terminated, truncated)
        self.assertTrue(torch.allclose(returns, torch.tensor([0.7, 0.6])))

    def test_zero_variance_advantages_become_zero(self) -> None:
        normalized = normalize_advantages(torch.tensor([2.0, 2.0, 2.0]))
        self.assertTrue(torch.equal(normalized, torch.zeros(3)))
        varying = normalize_advantages(torch.tensor([0.0, 2.0]))
        self.assertAlmostEqual(float(varying.mean()), 0.0)
        self.assertAlmostEqual(float(varying.std(unbiased=False)), 1.0)

    def test_actions_stay_aligned_with_observations(self) -> None:
        actor = nn.Sequential(nn.Linear(OBS_DIM, 3))
        observation = torch.zeros(2, OBS_DIM)
        action = torch.tensor([0, 2])
        old = detached_log_probs(actor, observation, action)
        with torch.no_grad():
            log_prob = torch.log_softmax(actor(observation), dim=-1)
        self.assertAlmostEqual(float(old[0]), float(log_prob[0, 0]))
        self.assertAlmostEqual(float(old[1]), float(log_prob[1, 2]))

    def test_reset_drops_previous_episode_state(self) -> None:
        import sys
        from pathlib import Path

        paper = Path(__file__).resolve().parents[1].parents[1] / "tools"
        if str(paper) not in sys.path:
            sys.path.insert(0, str(paper))
        from compact_study import build_compact_problem
        from environment import RuleSelectionEnv

        def order(order_id: str) -> dict:
            return {
                order_id: {
                    "properties": {"target": "euro-pallet"},
                    "item_sequence": {
                        "1": {
                            "sequence": 1,
                            "id": "box",
                            "length/mm": 100,
                            "width/mm": 100,
                            "height/mm": 100,
                            "weight/kg": 1,
                        }
                    },
                }
            }

        env = RuleSelectionEnv()
        env.reset(build_compact_problem(order("A"), "A"))
        env.step(0)
        self.assertEqual(len(env._rewards), 1)
        env.reset(build_compact_problem(order("B"), "B"))
        self.assertEqual(env._rewards, [])
        self.assertEqual(env._decisions, [])
        self.assertEqual(len(env.session.packed), 0)


if __name__ == "__main__":
    unittest.main()
