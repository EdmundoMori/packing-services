"""Short synthetic campaign checks, not industrial training."""
import json
import tempfile
import unittest
from pathlib import Path
import torch
from run_ppo_synthetic_v1 import run_campaign, verify_saved

class TestCampaign(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/'run'

    def run_short(self, **kwargs):
        return run_campaign(self.output, decisions=8, rollout_size=4, wall_seconds=60, **kwargs)

    def test_complete_across_episodes_and_updates(self):
        result = self.run_short()
        self.assertEqual(result['trained_decisions'], 8)
        self.assertEqual(result['confirmed_updates'], 2)
        self.assertEqual(result['optimizer_steps'], 8)
        self.assertGreater(result['boundary_continuations'], 0)
        self.assertFalse(result['open_episode'])
        report = verify_saved(self.output)
        self.assertEqual(report['verified_training_rows'], 8)

    def test_no_overwrite(self):
        self.run_short()
        with self.assertRaises(FileExistsError): self.run_short()

    def test_failure_before_update(self):
        with self.assertRaises(RuntimeError): self.run_short(fail_before_update=1)
        failure = json.loads((self.output/'failure.json').read_text())
        self.assertEqual(failure['confirmed_updates'], 0)
        self.assertEqual(failure['trained_decisions'], 0)
        self.assertEqual(verify_saved(self.output)['confirmed_updates'], 0)
        self.assertFalse((self.output/'summary.json').exists())

    def test_tampering_detected(self):
        self.run_short()
        path = next(self.output.glob('update_*/segment_*.json'))
        path.write_text('{}')
        with self.assertRaises(ValueError): verify_saved(self.output)

    def test_natural_priority_at_final_budget(self):
        result = run_campaign(self.output, decisions=6, rollout_size=3, wall_seconds=60)
        last = json.loads((self.output/'update_002/segment_000.json').read_text())['rows'][-1]
        self.assertTrue(last['terminated']); self.assertFalse(last['truncated'])
        self.assertFalse(result['open_episode'])

    def test_bad_budget_rejected(self):
        with self.assertRaises(ValueError): run_campaign(self.output, decisions=True)
        self.assertFalse(self.output.exists())

if __name__ == '__main__':
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    unittest.main()
