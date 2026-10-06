"""Synthetic PPO checks only: no BED-BPP file, no actual packing."""
import unittest
import torch
from ppo_core_v1 import (ActorCritic, PPOConfig, act, gae, loss_terms,
    make_optimizer, masked_distribution, normalise_advantages, update, validate_batch)


class TestPPOCore(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(123)
        self.model = ActorCritic()
        self.obs = torch.randn(32, 36)
        self.mask = torch.ones(32, 3, dtype=torch.bool)

    def batch(self):
        actions, log_probs, values, _ = act(self.model, self.obs, self.mask,
            generator=torch.Generator().manual_seed(42))
        rewards = (actions == 1).float()
        terminal = torch.ones(32, dtype=torch.bool)
        advantages, returns = gae(rewards, values, torch.zeros(32), terminal,
            torch.zeros(32, dtype=torch.bool))
        return {'observations': self.obs, 'masks': self.mask, 'actions': actions,
            'old_log_probs': log_probs, 'old_values': values,
            'advantages': advantages, 'returns': returns}

    def test_initial_uniform(self):
        _, _, _, probs = act(self.model, self.obs, self.mask)
        self.assertTrue(torch.allclose(probs, torch.full_like(probs, 1/3)))

    def test_mask(self):
        mask = torch.tensor([[False, True, False]]).expand(32, -1)
        actions, _, _, probs = act(self.model, self.obs, mask)
        self.assertTrue((actions == 1).all())
        self.assertTrue((probs[:, 0] == 0).all())

    def test_empty_mask_rejected(self):
        with self.assertRaises(ValueError):
            masked_distribution(torch.zeros(1, 3), torch.zeros(1, 3, dtype=torch.bool))

    def test_terminal_no_bootstrap(self):
        a, r = gae(torch.tensor([1.]), torch.tensor([.2]), torch.tensor([100.]),
                   torch.tensor([True]), torch.tensor([False]))
        self.assertAlmostEqual(r.item(), 1., places=6)

    def test_truncation_bootstrap_and_trace_stop(self):
        a, r = gae(torch.tensor([1., 2.]), torch.tensor([.2, .3]), torch.tensor([.7, 100.]),
                   torch.tensor([False, True]), torch.tensor([True, False]))
        self.assertTrue(torch.allclose(r, torch.tensor([1.7, 2.])))

    def test_rollout_tail_bootstrap(self):
        a, r = gae(torch.tensor([1., 2.]), torch.tensor([.2, .3]), torch.tensor([.3, .7]),
                   torch.tensor([False, False]), torch.tensor([False, False]))
        self.assertTrue(torch.allclose(r, torch.tensor([3.7, 2.7])))

    def test_exclusive_flags(self):
        with self.assertRaises(ValueError):
            gae(torch.ones(1), torch.zeros(1), torch.zeros(1),
                torch.tensor([True]), torch.tensor([True]))

    def test_zero_variance(self):
        self.assertTrue((normalise_advantages(torch.ones(5)) == 0).all())

    def test_policy_loss_ratio_one(self):
        batch = self.batch()
        total, metrics = loss_terms(self.model, batch)
        self.assertAlmostEqual(metrics['policy_loss'], -batch['advantages'].mean().item(), places=6)
        self.assertEqual(metrics['clip_fraction'], 0)

    def test_nonfinite_rejected(self):
        batch = self.batch(); batch['returns'][0] = float('nan')
        with self.assertRaises(ValueError):
            validate_batch(batch)

    def test_update_and_frozen_batch(self):
        batch = self.batch(); saved = {k:v.clone() for k,v in batch.items()}
        before = {k:v.clone() for k,v in self.model.state_dict().items()}
        config = PPOConfig(minibatch_size=8)
        report = update(self.model, make_optimizer(self.model, config), batch,
            config=config, generator=torch.Generator().manual_seed(77))
        self.assertEqual(report['optimizer_steps'], 16)
        self.assertTrue(any(not torch.equal(before[k],v) for k,v in self.model.state_dict().items()))
        self.assertTrue(all(torch.equal(saved[k],v) for k,v in batch.items()))
        for permutation in report['permutations']:
            self.assertEqual(sorted(permutation), list(range(32)))

    def test_stale_behavior_rejected(self):
        batch = self.batch(); batch['old_log_probs'] = batch['old_log_probs'] + 0.1
        with self.assertRaises(ValueError):
            update(self.model, make_optimizer(self.model), batch)


if __name__ == '__main__':
    unittest.main()
