"""Synthetic environment integration only; no BED-BPP dataset access."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
import torch

# Load the resource environment before historical modules with the same name.
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('environment', here/'environment.py')
module = importlib.util.module_from_spec(spec)
sys.modules['environment'] = module
spec.loader.exec_module(module)
from ppo_core_v1 import ActorCritic, make_optimizer, update
from ppo_rollout_v1 import EpisodeCollector, verify_record, batch_from_record, save_record
from synthetic_problems import scenario_catalog

class TestRollout(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(7)
        self.model = ActorCritic()
        self.env = module.BedBppRlEnv()
        self.addCleanup(self.env.close)
        self.generator = torch.Generator().manual_seed(99)

    def collector(self, scenario='all_fit', budget=None):
        obs, info = self.env.reset(scenario_catalog()[scenario], decision_budget=budget)
        return EpisodeCollector(self.env, obs, info, episode_id='synthetic')

    def test_natural_end(self):
        record = self.collector().collect(self.model, 10, generator=self.generator)
        self.assertEqual(len(record['rows']), 3)
        self.assertTrue(record['rows'][-1]['terminated'])
        self.assertEqual(record['rows'][-1]['next_value'], 0)
        self.assertTrue(verify_record(record, self.model)['verified'])
        self.assertAlmostEqual(sum(r['reward'] for r in record['rows']), self.env.geometric_utilization())

    def test_open_rollout_resume(self):
        collector = self.collector()
        first = collector.collect(self.model, 1, generator=self.generator)
        self.assertTrue(first['rollout_boundary_open'])
        self.assertFalse(first['rows'][-1]['truncated'])
        second = collector.collect(self.model, 10, generator=self.generator)
        self.assertEqual(second['rows'][0]['step_index'], 1)
        self.assertEqual(first['rows'][-1]['observation_next'], second['rows'][0]['observation'])
        verify_record(first, self.model); verify_record(second, self.model)

    def test_budget_truncation(self):
        record = self.collector(budget=1).collect(self.model, 10, generator=self.generator)
        self.assertTrue(record['rows'][-1]['truncated'])
        self.assertTrue(any(record['rows'][-1]['action_mask_next']))
        verify_record(record, self.model)

    def test_terminal_priority(self):
        record = self.collector('two_fit', budget=2).collect(self.model, 10, generator=self.generator)
        self.assertTrue(record['rows'][-1]['terminated'])
        self.assertFalse(record['rows'][-1]['truncated'])

    def test_zero_transition(self):
        record = self.collector('first_impossible').collect(self.model, 10, generator=self.generator)
        self.assertEqual(record['rows'], [])
        verify_record(record, self.model)
        with self.assertRaises(ValueError): batch_from_record(record)

    def test_persistence_and_update(self):
        record = self.collector().collect(self.model, 10, generator=self.generator)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'audit.json'
            save_record(path, record)
            restored = json.loads(path.read_text())
            verify_record(restored, self.model)
            with self.assertRaises(FileExistsError): save_record(path, record)
        report = update(self.model, make_optimizer(self.model), batch_from_record(restored), generator=self.generator)
        self.assertEqual(report['optimizer_steps'], 4)
        with self.assertRaises(ValueError): verify_record(restored, self.model)

    def test_tampered_return(self):
        record = self.collector().collect(self.model, 10, generator=self.generator)
        record['rows'][0]['return'] += 1
        with self.assertRaises(ValueError): verify_record(record, self.model)

    def test_tampered_chain(self):
        record = self.collector().collect(self.model, 10, generator=self.generator)
        record['rows'][1]['observation'][0] += 1
        with self.assertRaises(ValueError): verify_record(record, self.model)

    def test_strict_budget(self):
        collector = self.collector()
        with self.assertRaises(ValueError): collector.collect(self.model, True, generator=self.generator)

if __name__ == '__main__': unittest.main()
