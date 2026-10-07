"""Synthetic gated PPO tests only."""
import json
from pathlib import Path
import tempfile
import unittest
import torch
from resource_training_gate_v1 import digest,validate_document
from resource_ppo_engine_v1 import run_campaign,verify_saved

class TestTrainingGate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def protocol(self):
        p=dict(status='frozen_training_only',authorized_phase='ppo_training',evaluation_authorized=False,
            seeds=[101,102,103],decisions_per_seed=2048,rollout_size=128,wall_seconds_per_seed=600)
        p['sha256']=digest(p);return p
    def test_training_gate(self):validate_document(self.protocol())
    def test_evaluation_blocked(self):
        p=self.protocol();p['evaluation_authorized']=True;p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_document(p)
    def test_changed_budget(self):
        p=self.protocol();p['decisions_per_seed']=4096;p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_document(p)
    def test_unfrozen_industrial_rejected(self):
        with self.assertRaises(ValueError):run_campaign(self.root/'run',mode='industrial')
        self.assertFalse((self.root/'run').exists())
    def test_final_and_probes(self):
        result=run_campaign(self.root/'run',decisions=8,rollout_size=4,wall_seconds=60)
        self.assertEqual(result['optimizer_steps'],8)
        self.assertEqual((self.root/'run/final.pt').read_bytes(),(self.root/'run/update_002/after.pt').read_bytes())
        probes=json.loads((self.root/'run/policy_probes.json').read_text())['probes']
        self.assertEqual(len(probes),2)
        for p in probes:self.assertTrue(all(abs(x-1/3)<1e-6 for x in p['initial_probabilities']))
        self.assertEqual(verify_saved(self.root/'run')['verified_training_rows'],8)
    def test_seed_recorded(self):
        run_campaign(self.root/'run',decisions=8,rollout_size=4,seed=102,wall_seconds=60)
        self.assertEqual(json.loads((self.root/'run/plan.json').read_text())['seed'],102)

if __name__=='__main__':
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    unittest.main()
