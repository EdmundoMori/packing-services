"""Synthetic nested-checkpoint and confirmed-reference recovery tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import torch
from ppo_core_v1 import ActorCritic
from resource_corpus_adapter_v2 import synthetic_fixture, build_plan
from run_resource_evaluation_recovery_v2 import actor_policy, generate, inspect_reuse, sha, load
from corpus_writer import _atomic_write_json

class TestRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.orders,rows=synthetic_fixture()
        self.rows=rows[:1];self.orders={self.rows[0]['order_id']:self.orders[self.rows[0]['order_id']]}
        self.checkpoint=self.root/'nested.pt'
        torch.save({'model':ActorCritic().state_dict(),'optimizer':{},'rng':{},'torch_rng':torch.get_rng_state(),'decisions':2048,'updates':16},self.checkpoint)
        self.models={'101':{'relpath':str(self.checkpoint),'path':str(self.checkpoint),'sha256':sha(self.checkpoint)}}
        self.cases=[dict(c,model_seed=None) for c in build_plan(self.rows)]
        row=self.rows[0]
        self.cases.append(dict(order_id=row['order_id'],target=row['target'],policy='ppo_deterministic_seed_101',model_seed=101,episode_id=row['order_id']+'__ppo_deterministic_seed_101'))
    def test_nested_checkpoint_and_mask(self):
        before=self.checkpoint.read_bytes();choose,trace=actor_policy(self.checkpoint)
        self.assertEqual(choose([0.0]*36,[False,True,True],{}),1)
        self.assertEqual(self.checkpoint.read_bytes(),before)
    def test_flat_checkpoint_rejected(self):
        flat=self.root/'flat.pt';torch.save(ActorCritic().state_dict(),flat)
        with self.assertRaises(ValueError):actor_policy(flat)
    def test_synthetic_nested_full(self):
        r=generate(self.orders,self.cases,self.models,self.root/'complete',mode='synthetic',wall_seconds=60)
        self.assertEqual(r['evaluation_episodes'],5);self.assertEqual(r['reused_episodes'],0)
    def test_reuse_four_without_reexecuting(self):
        source=self.root/'source'
        with patch('run_resource_evaluation_recovery_v2.actor_policy',side_effect=ValueError('simulated loader error')):
            with self.assertRaises(ValueError):generate(self.orders,self.cases,self.models,source,mode='synthetic',wall_seconds=60)
        before={p:str(sha(p)) for p in source.rglob('*') if p.is_file()}
        design={'cases':self.cases,'models':{'101':{'relpath':str(self.checkpoint),'sha256':sha(self.checkpoint)}}}
        reused=inspect_reuse(source,design);self.assertEqual(len(reused),4)
        protocol=self.root/'protocol.json';orders=self.root/'orders.json'
        _atomic_write_json(protocol,{});_atomic_write_json(orders,self.orders)
        frozen=dict(design=design,remaining_seconds=60,source_relpath=str(source),reused=reused,prior_accounted_seconds=540)
        import resource_corpus_adapter_v2 as adapter
        real_run=adapter.run_and_record;calls=[]
        def counted(*args,**kwargs):
            calls.append(kwargs['behavior_policy']);return real_run(*args,**kwargs)
        with patch('run_resource_evaluation_recovery_v2.validate_phase',return_value=frozen),patch.object(adapter,'run_and_record',side_effect=counted):
            r=generate(self.orders,self.cases,self.models,self.root/'recovery',mode='industrial',wall_seconds=60,protocol_sha256=sha(protocol),protocol_path=protocol,orders_path=orders,reuse_source=source)
        self.assertEqual(calls,['ppo_deterministic_seed_101'])
        self.assertEqual(r['reused_episodes'],4);self.assertEqual(r['new_episodes'],1)
        self.assertEqual(before,{p:str(sha(p)) for p in source.rglob('*') if p.is_file()})
    def test_unfrozen_rejected(self):
        with self.assertRaises(ValueError):generate(self.orders,self.cases,self.models,self.root/'out',mode='industrial',wall_seconds=600)
        self.assertFalse((self.root/'out').exists())

if __name__=='__main__':
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    unittest.main()
