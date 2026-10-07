"""Synthetic corpus adapter tests; no industrial dataset or torch needed."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from resource_corpus_adapter_v1 import generate,verify_corpus,synthetic_fixture,build_plan,behavior
from synthetic_problems import synthetic_order

class TestCorpusAdapter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.orders,self.rows=synthetic_fixture()
    def test_complete_and_portable(self):
        report=generate(self.orders,self.rows,self.root/'run')
        self.assertEqual(report['episodes'],8);self.assertEqual(report['transitions'],16)
        shutil.copytree(self.root/'run',self.root/'copied')
        self.assertEqual(verify_corpus(self.root/'copied')['transitions'],16)
    def test_duplicate_sample_rejected(self):
        with self.assertRaises(ValueError):build_plan([self.rows[0],self.rows[0]])
    def test_industrial_blocked(self):
        with self.assertRaises(ValueError):generate(self.orders,self.rows,self.root/'run',mode='industrial')
        self.assertFalse((self.root/'run').exists())
    def test_existing_output_rejected(self):
        generate(self.orders,self.rows,self.root/'run')
        with self.assertRaises(FileExistsError):generate(self.orders,self.rows,self.root/'run')
    def test_uniform_reproducible(self):
        a,seed_a=behavior('uniform_rules',20261006,'syn-euro')
        b,seed_b=behavior('uniform_rules',20261006,'syn-euro')
        self.assertEqual(seed_a,seed_b)
        self.assertEqual([a([], [True,False,True],{}) for _ in range(20)], [b([], [True,False,True],{}) for _ in range(20)])
    def test_modified_episode_rejected(self):
        generate(self.orders,self.rows,self.root/'run')
        path=next((self.root/'run/confirmed_corpus').glob('syn-*.json'))
        path.write_text('{}')
        with self.assertRaises(ValueError):verify_corpus(self.root/'run')
    def test_zero_transitions_preserved(self):
        orders=synthetic_order('syn-impossible',[('large',3000,3000,3000)])
        report=generate(orders,[{'order_id':'syn-impossible','target':'euro-pallet'}],self.root/'run')
        self.assertEqual(report['episodes'],4);self.assertEqual(report['transitions'],0)
        self.assertEqual(report['terminated'],4)

if __name__=='__main__':unittest.main()
