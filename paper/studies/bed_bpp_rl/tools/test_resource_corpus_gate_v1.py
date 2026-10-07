"""Freeze gate tests + supervised synthetic integration, no industrial orders."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from resource_corpus_gate_v1 import digest,validate_protocol_document
from resource_corpus_adapter_v2 import generate,verify_corpus,synthetic_fixture

class TestCorpusGate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def protocol(self):
        p=dict(status='frozen_corpus_only',authorized_phase='initial_corpus',training_authorized=False,
            evaluation_authorized=False,corpus={'episodes':64,'wall_seconds':600})
        p['sha256']=digest(p);return p
    def test_digest_and_gate(self):validate_protocol_document(self.protocol())
    def test_changed_budget_rejected(self):
        p=self.protocol();p['corpus']['wall_seconds']=601
        with self.assertRaises(ValueError):validate_protocol_document(p)
    def test_other_phase_rejected(self):
        p=self.protocol();p['authorized_phase']='training';p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_protocol_document(p)
    def test_draft_rejected(self):
        p=self.protocol();p['status']='draft';p['sha256']=digest(p)
        with self.assertRaises(ValueError):validate_protocol_document(p)
    def test_no_unfrozen_industrial(self):
        orders,rows=synthetic_fixture()
        with self.assertRaises(ValueError):generate(orders,rows,self.root/'run',mode='industrial')
        self.assertFalse((self.root/'run').exists())
    def test_synthetic_unchanged(self):
        orders,rows=synthetic_fixture();report=generate(orders,rows,self.root/'run')
        self.assertEqual(report['episodes'],8);self.assertEqual(report['transitions'],16)
    def test_supervised_synthetic(self):
        from resource_process_supervisor_v1 import supervise
        worker=Path(__file__).absolute().parent/'run_resource_corpus_v1.py'
        report=supervise([sys.executable,str(worker),'--synthetic','--out',str(self.root/'corpus')],
            run_dir=self.root/'supervisor',timeout_seconds=30)
        self.assertEqual(report['exitcode'],0)
        self.assertEqual(verify_corpus(self.root/'corpus')['episodes'],8)

if __name__=='__main__':unittest.main()
