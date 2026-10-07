"""No dataset access, no torch import and no packing."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from check_resource_campaign_v1 import validate_sample, verify_sources, operational_settings, exclusion_ids, sha

HERE=Path(__file__).resolve().parent
class TestStaticPreparation(unittest.TestCase):
    def setUp(self):
        self.sample=json.loads((HERE.parent/'resource_sample_draft.json').read_text())

    def test_published_sample_structure(self):
        self.assertEqual(len(validate_sample(self.sample)),24)

    def test_duplicate_rejected(self):
        sample=copy.deepcopy(self.sample)
        sample['evaluation']['euro-pallet'][0]=copy.deepcopy(sample['train']['euro-pallet'][0])
        with self.assertRaises(ValueError):validate_sample(sample)

    def test_bad_target_rejected(self):
        self.sample['train']['euro-pallet'][0]['target']='rollcontainer'
        with self.assertRaises(ValueError):validate_sample(self.sample)

    def test_full_val_not_exposure(self):
        ids=exclusion_ids({'train':['00000001'],'val':['00000002'],'test':['00000003']},full_split=True)
        self.assertEqual(ids,{'00000001','00000003'})

    def test_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'source.json';path.write_text('["00000001"]')
            sample={'exclusion_sources':[{'path':'source.json','sha256':sha(path),'ids_n':1}], 'excluded_ids_n':1}
            self.assertEqual(verify_sources(sample,root),{'00000001'})
            path.write_text('["00000002"]')
            with self.assertRaises(ValueError):verify_sources(sample,root)

    def test_operational_budget_consistency(self):
        settings=operational_settings()
        self.assertEqual(settings['decisions_per_seed']//settings['rollout_size'],16)
        self.assertEqual(16*4*2,settings['adam_steps_per_complete_seed'])
        self.assertFalse(settings['industrial_execution_authorized'])
        self.assertEqual(settings['phases']['evaluation']['episodes'],8*(3+4))

if __name__=='__main__':unittest.main()
