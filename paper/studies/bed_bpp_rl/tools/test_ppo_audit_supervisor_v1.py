"""Synthetic PPO geometry and POSIX supervisor tests only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import torch
from run_ppo_synthetic_audited_v1 import run_campaign, verify_saved
from ppo_process_supervisor_v1 import supervise

class TestAuditSupervisor(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_audited_campaign(self):
        output = self.root/'campaign'
        result = run_campaign(output, decisions=8, rollout_size=4, wall_seconds=60)
        self.assertTrue(result['geometry_audit_performed'])
        report = verify_saved(output)['geometry_verification']
        self.assertEqual(report['unique_transitions'], 8)
        self.assertEqual(report['closed_episodes'], 3)
        self.assertGreater(report['prefixes'], report['closed_episodes'])

    def test_open_prefix_remains_open(self):
        output = self.root/'campaign'
        run_campaign(output, decisions=8, rollout_size=4, wall_seconds=60)
        documents = [json.loads(p.read_text()) for p in (output/'episodes').glob('*.json') if not p.name.endswith('.audit.json')]
        prefixes = [d for d in documents if d.get('kind') == 'ppo_open_prefix_audit_v1']
        self.assertTrue(prefixes)
        self.assertFalse(prefixes[0]['terminated']); self.assertFalse(prefixes[0]['truncated'])

    def test_geometry_tampering_rejected(self):
        output = self.root/'campaign'
        run_campaign(output, decisions=8, rollout_size=4, wall_seconds=60)
        path = next(p for p in (output/'episodes').glob('*.json') if not p.name.endswith('.audit.json'))
        document = json.loads(path.read_text())
        document['artifacts']['placements'][0]['x'] = 100000
        path.write_text(json.dumps(document))
        with self.assertRaises(AssertionError): verify_saved(output)

    def test_supervisor_success(self):
        report = supervise([sys.executable, '-c', 'print("synthetic")'], run_dir=self.root/'process', timeout_seconds=5)
        self.assertEqual(report['exitcode'], 0)
        self.assertFalse(report['scientific_completeness_verified'])

    def test_supervisor_timeout(self):
        report = supervise([sys.executable, '-c', 'import time; time.sleep(10)'], run_dir=self.root/'process', timeout_seconds=0.2)
        self.assertTrue(report['timed_out'])
        self.assertNotEqual(report['exitcode'], 0)
        self.assertFalse(report['automatic_restart'])

    def test_supervisor_nonzero(self):
        report = supervise([sys.executable, '-c', 'raise SystemExit(3)'], run_dir=self.root/'process', timeout_seconds=5)
        self.assertEqual(report['exitcode'], 3)
        self.assertEqual(report['status'], 'process_failed')

if __name__ == '__main__':
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    unittest.main()
