"""Freeze only PPO training; evaluation remains closed."""
import json
from pathlib import Path
from check_resource_campaign_v1 import check,sha,ROOT,STUDY,validate_sample
from resource_corpus_gate_v1 import digest


def validate_document(p):
    if p.get('sha256')!=digest(p):raise ValueError('Training protocol digest mismatch')
    if p.get('status')!='frozen_training_only' or p.get('authorized_phase')!='ppo_training':raise ValueError('Wrong phase')
    if p.get('evaluation_authorized') is not False:raise ValueError('Evaluation not authorized')
    if p.get('seeds')!=[101,102,103] or p.get('decisions_per_seed')!=2048 or p.get('rollout_size')!=128 or p.get('wall_seconds_per_seed')!=600:
        raise ValueError('Frozen training budget mismatch')


def freeze(orders):
    draft,report=check(orders)
    from resource_corpus_adapter_v2 import verify_corpus
    corpus=STUDY/'initial_corpus_01'
    audit=verify_corpus(corpus)
    if audit['episodes']!=64 or audit['transitions']!=2360:raise ValueError('Initial corpus closure mismatch')
    p=dict(schema_version=1,status='frozen_training_only',authorized_phase='ppo_training',evaluation_authorized=False,
        seeds=[101,102,103],decisions_per_seed=2048,rollout_size=128,wall_seconds_per_seed=600,
        updates_per_complete_seed=16,adam_steps_per_complete_seed=128,concurrency=1,
        checkpoint_selection='final_confirmed_update_only',automatic_restart=False,
        gamma=1,gae_lambda=1,ppo=draft['ppo'],device='cpu',torch_threads=1,torch_interop_threads=1,
        observation_dim=36,action_dim=3,architecture=draft['architecture'],
        sample_relpath=draft['sample_relpath'],sample_sha256=draft['sample_sha256'],
        dataset_sha256=draft['dataset_sha256'],code_sha256=draft['implementation_sha256'],
        environment_contract_sha256=draft['environment_contract_sha256'],corpus_schema_sha256=draft['corpus_schema_sha256'],
        initial_corpus_manifest_sha256=sha(corpus/'confirmed_corpus/manifest.json'),
        initial_corpus_used_for_PPO_updates=False,train_order_rule='complete permutations using seed+3000 generator',
        rng_offsets={'actions':1000,'minibatches':2000,'order':3000},
        probes='first reset observation actually visited per train order, initial versus final model',
        incomplete='preserve artifacts; no automatic retry or time transfer; no evaluation after incomplete integrity',
        markov_sufficiency_claimed=False,physical_stability_verified=None,
        prepared_at_head=draft['prepared_at_head'])
    p['sha256']=digest(p);validate_document(p)
    path=STUDY/'resource_training_protocol_frozen_v1.json'
    with path.open('x',encoding='utf-8') as stream:stream.write(json.dumps(p,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
    return dict(status='training_phase_frozen',protocol_file_sha256=sha(path),internal_digest=p['sha256'],
        seeds=p['seeds'],decisions_per_seed=2048,wall_seconds_per_seed=600,
        evaluation_authorized=False,training_executed=False)


def validate_phase(protocol_path,orders_path):
    p=json.loads(Path(protocol_path).read_text());validate_document(p)
    if sha(orders_path)!=p['dataset_sha256']:raise ValueError('Dataset mismatch')
    for rel,expected in p['code_sha256'].items():
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe code path')
        if sha(ROOT/path)!=expected:raise ValueError('Frozen code changed: '+rel)
    for path,expected in [(STUDY/'environment_contract_draft.json',p['environment_contract_sha256']),
        (STUDY/'corpus_schema_v1.json',p['corpus_schema_sha256']),
        (STUDY/'initial_corpus_01/confirmed_corpus/manifest.json',p['initial_corpus_manifest_sha256'])]:
        if sha(path)!=expected:raise ValueError('Frozen artifact changed')
    sample=ROOT/p['sample_relpath']
    if sha(sample)!=p['sample_sha256']:raise ValueError('Sample changed')
    d=json.loads(sample.read_text());validate_sample(d)
    return p,[r for target in ('euro-pallet','rollcontainer') for r in d['train'][target]]
