"""Synthetic training adapter checks; no industrial dataset access."""
import json
from pathlib import Path
import tempfile
import unittest
import torch
from run_ppo_training_draft_v1 import run_campaign,verify_saved
from synthetic_problems import make_problem

class TestTrainingAdapter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def short(self,path,**kwargs):
        return run_campaign(path,decisions=8,rollout_size=4,wall_seconds=60,**kwargs)
    def test_order_cycles_and_audit(self):
        self.short(self.root/'a')
        trace=json.loads((self.root/'a/order_trace.json').read_text())
        for cycle in sorted({row['cycle'] for row in trace}):
            ids=[row['order_id'] for row in trace if row['cycle']==cycle]
            self.assertEqual(len(ids),len(set(ids)))
        report=verify_saved(self.root/'a')
        self.assertEqual(report['verified_training_rows'],8)
        self.assertEqual(report['geometry_verification']['unique_transitions'],8)
    def test_seed_reproducibility(self):
        self.short(self.root/'a');self.short(self.root/'b')
        self.assertEqual(json.loads((self.root/'a/order_trace.json').read_text()),json.loads((self.root/'b/order_trace.json').read_text()))
        a=next((self.root/'a/update_001').glob('segment_*.json'))
        b=self.root/'b/update_001'/a.name
        self.assertEqual(json.loads(a.read_text()),json.loads(b.read_text()))
    def test_actual_order_metadata(self):
        self.short(self.root/'a')
        ids=set()
        for p in (self.root/'a/episodes').glob('*.json'):
            if p.name.endswith('.audit.json'):continue
            d=json.loads(p.read_text())
            for row in d['transitions']:ids.add(row['order_id'])
        self.assertEqual(ids,{'syn-euro','syn-roll'})
    def test_industrial_ids_blocked(self):
        with self.assertRaises(ValueError):self.short(self.root/'a',train_rows=[{'order_id':'00105039','target':'euro-pallet'}])
        self.assertFalse((self.root/'a').exists())
    def test_duplicate_rows_blocked(self):
        row={'order_id':'syn-euro','target':'euro-pallet'}
        with self.assertRaises(ValueError):self.short(self.root/'a',train_rows=[row,row])
    def test_empty_cycle_detected(self):
        rows=[{'order_id':'syn-empty','target':'euro-pallet'}]
        def factory(row):return make_problem(row['order_id'],[('large',3000,3000,3000)])
        with self.assertRaises(ValueError):self.short(self.root/'a',train_rows=rows,problem_factory=factory)
        self.assertEqual(json.loads((self.root/'a/failure.json').read_text())['confirmed_updates'],0)

if __name__=='__main__':
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    unittest.main()
