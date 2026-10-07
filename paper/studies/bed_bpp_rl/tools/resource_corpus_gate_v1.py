"""Freeze and validate only the initial corpus phase; no RL authorization."""
import copy
import hashlib
import json
from pathlib import Path
from check_resource_campaign_v1 import ROOT,STUDY,DATASET_SHA,check,sha,validate_sample


def digest(document):
    body=copy.deepcopy(document);body.pop('sha256',None)
    return hashlib.sha256((json.dumps(body,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()).hexdigest()


def validate_protocol_document(protocol):
    if protocol.get('sha256')!=digest(protocol):raise ValueError('Protocol digest mismatch')
    if protocol.get('status')!='frozen_corpus_only' or protocol.get('authorized_phase')!='initial_corpus':
        raise ValueError('Only frozen initial corpus phase is authorized')
    if protocol.get('training_authorized') is not False or protocol.get('evaluation_authorized') is not False:
        raise ValueError('No training/evaluation authorization')
    if protocol['corpus']['episodes']!=64 or protocol['corpus']['wall_seconds']!=600:
        raise ValueError('Corpus budget mismatch')


def freeze(orders):
    draft,report=check(orders)
    protocol=dict(schema_version=1,status='frozen_corpus_only',authorized_phase='initial_corpus',
        training_authorized=False,evaluation_authorized=False,
        dataset_sha256=DATASET_SHA,sample_relpath=draft['sample_relpath'],sample_sha256=draft['sample_sha256'],
        code_sha256=draft['implementation_sha256'],environment_contract_sha256=draft['environment_contract_sha256'],
        corpus_schema_sha256=draft['corpus_schema_sha256'],prepared_at_head=draft['prepared_at_head'],
        corpus=dict(episodes=64,wall_seconds=600,concurrency=1,attempts_per_key=1,
            policies=['fixed_greedy_best_fit','fixed_lowest_top','fixed_least_height_increase','uniform_rules'],
            uniform_base_seed=20261006,
            seed_derivation='sha256(bed-bpp-rl-corpus-v1|base_seed|order_id), first 8 bytes big-endian',
            deadline='external_process_group_timeout',automatic_restart=False,
            incomplete='preserve confirmed and unconfirmed artifacts; no substitution or automatic retry'),
        dataset_redistributed=False,physical_stability_verified=None,
        nominal_geometry_only=True,not_official_robotic_protocol=True,
        novelty_established=False,budget_feasibility_proven=False)
    protocol['sha256']=digest(protocol);validate_protocol_document(protocol)
    path=STUDY/'resource_corpus_protocol_frozen_v1.json'
    with path.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(protocol,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    return dict(report,corpus_protocol_written=str(path),corpus_protocol_file_sha256=sha(path),
        corpus_protocol_internal_digest=protocol['sha256'],training_authorized=False,evaluation_authorized=False)


def validate_phase(protocol_path,orders_path):
    protocol=json.loads(Path(protocol_path).read_text());validate_protocol_document(protocol)
    if sha(orders_path)!=protocol['dataset_sha256']:raise ValueError('Dataset hash mismatch')
    for rel,expected in protocol['code_sha256'].items():
        p=Path(rel)
        if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe dependency path')
        if sha(ROOT/p)!=expected:raise ValueError('Frozen code changed: '+rel)
    for path,expected in [(STUDY/'environment_contract_draft.json',protocol['environment_contract_sha256']),
                          (STUDY/'corpus_schema_v1.json',protocol['corpus_schema_sha256'])]:
        if sha(path)!=expected:raise ValueError('Environment/schema hash mismatch')
    sample_path=ROOT/protocol['sample_relpath']
    if sha(sample_path)!=protocol['sample_sha256']:raise ValueError('Sample hash mismatch')
    sample=json.loads(sample_path.read_text());validate_sample(sample)
    rows=[r for target in ('euro-pallet','rollcontainer') for r in sample['train'][target]]
    return protocol,rows
