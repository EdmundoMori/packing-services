"""Synthetic final-policy evaluation tests; no industrial orders."""
import copy
from pathlib import Path
import tempfile
import unittest
import torch
from run_resource_evaluation_v1 import actor_policy, generate, verify, validate_document, digest, sha, load
from resource_corpus_adapter_v2 import synthetic_fixture, build_plan
from ppo_core_v1 import ActorCritic
from corpus_writer import _atomic_write_json

class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.orders,self.rows=synthetic_fixture()
        self.checkpoint=self.root/'model.pt'
        torch.manual_seed(101);torch.save(ActorCritic().state_dict(),self.checkpoint)
        self.models={'101':{'path':str(self.checkpoint),'sha256':sha(self.checkpoint)}}
        self.cases=[dict(c,model_seed=None) for c in build_plan(self.rows)]
        for row in self.rows:
            self.cases.append(dict(order_id=row['order_id'],target=row['target'],
                policy='ppo_deterministic_seed_101',model_seed=101,
                episode_id=row['order_id']+'__ppo_deterministic_seed_101'))
    def run_synthetic(self):
        return generate(self.orders,self.cases,self.models,self.root/'out',mode='synthetic',wall_seconds=60)
    def test_complete_and_readonly_verification(self):
        r=self.run_synthetic();self.assertEqual(r['evaluation_episodes'],10)
        self.assertTrue(r['geometry_audit_performed']);self.assertFalse(r['training_executed'])
        self.assertEqual(verify(self.root/'out')['transitions'],20)
    def test_uniform_actor_tie_and_no_checkpoint_mutation(self):
        before=self.checkpoint.read_bytes();policy,trace=actor_policy(self.checkpoint)
        self.assertEqual(policy([0.0]*36,[True,True,True],{}),0)
        self.assertEqual(policy([0.0]*36,[False,True,True],{}),1)
        self.assertEqual(self.checkpoint.read_bytes(),before)
        self.assertAlmostEqual(sum(trace[0]['probabilities']),1,places=6)
    def test_trace_tampering_rejected(self):
        self.run_synthetic()
        p=next((self.root/'out/actor_decisions').glob('*.json'))
        d=load(p);d['decisions'][0]['action']=2;_atomic_write_json(p,d)
        with self.assertRaises(ValueError):verify(self.root/'out')
    def test_checkpoint_mismatch_rejected(self):
        self.models['101']['sha256']='0'*64
        with self.assertRaises(ValueError):self.run_synthetic()
        self.assertTrue((self.root/'out/failure.json').exists())
    def test_industrial_cannot_bypass_gate(self):
        with self.assertRaises(ValueError):generate(self.orders,self.cases,self.models,self.root/'out',mode='industrial',wall_seconds=600,protocol_sha256='fake')
        self.assertFalse((self.root/'out').exists())
    def test_existing_output_rejected(self):
        self.run_synthetic()
        with self.assertRaises(FileExistsError):self.run_synthetic()
    def test_synthetic_rejects_real_ids(self):
        c=copy.deepcopy(self.cases);c[0]['order_id']='00100001'
        with self.assertRaises(ValueError):generate(self.orders,c,self.models,self.root/'out',mode='synthetic',wall_seconds=60)
        self.assertFalse((self.root/'out').exists())
    def test_protocol_budget_and_duplicates(self):
        p=dict(status='frozen_evaluation_only',authorized_phase='evaluation',training_authorized=False,
               design=dict(episodes=56,wall_seconds_proposed=600,concurrency=1,cases=[{'episode_id':str(i)} for i in range(56)]))
        p['sha256']=digest(p);validate_document(p)
        p['design']['wall_seconds_proposed']=601;p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_document(p)
        p['design']['wall_seconds_proposed']=600;p['design']['cases'][0]=p['design']['cases'][1];p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_document(p)

if __name__=='__main__':
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    unittest.main()
