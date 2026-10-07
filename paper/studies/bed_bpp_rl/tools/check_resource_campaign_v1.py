"""Metadata-only campaign preparation. No torch import, candidates or packing.

Replays the published deterministic selector without --write. Draft generation
is exclusive and is not experiment authorization or a frozen protocol.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
ROOT = HERE.parents[3]
DATASET_SHA = '6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc'
TARGETS = ('euro-pallet', 'rollcontainer')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''): h.update(chunk)
    return h.hexdigest()


def validate_sample(document):
    if document.get('status') != 'draft_selected_not_executed': raise ValueError('Unexpected sample status')
    if document.get('packing_executed') is not False or document.get('training_executed') is not False:
        raise ValueError('Sample flags mismatch')
    rows = []
    for split, count in [('train',8),('evaluation',4)]:
        if set(document[split]) != set(TARGETS): raise ValueError('Targets mismatch')
        for target in TARGETS:
            bucket = document[split][target]
            if len(bucket) != count: raise ValueError('Split size mismatch')
            for row in bucket:
                if row['target'] != target: raise ValueError('Row target mismatch')
                if type(row['n_items']) is not int or row['n_items'] <= 0: raise ValueError('Invalid item count')
                if not isinstance(row['order_id'],str) or len(row['order_id']) != 8 or not row['order_id'].isdigit():
                    raise ValueError('Invalid order ID')
                if len(row['signature']) != 64 or any(c not in '0123456789abcdef' for c in row['signature']):
                    raise ValueError('Invalid signature')
                rows.append(row)
    if len({r['order_id'] for r in rows}) != 24 or len({r['signature'] for r in rows}) != 24:
        raise ValueError('Duplicate identity/signature')
    return rows


def exclusion_ids(document, *, full_split=False):
    from select_resource_sample import ids_in
    if full_split:
        document = {'train':document['train'], 'test':document['test']}
    return ids_in(document)


def verify_sources(sample, root=ROOT):
    blocked = set()
    for row in sample['exclusion_sources']:
        rel = Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe source path')
        path = root/rel
        if sha(path) != row['sha256']: raise ValueError('Exclusion hash mismatch: '+str(rel))
        ids = exclusion_ids(json.loads(path.read_text()), full_split=path.name=='full_split.json')
        if len(ids) != row['ids_n']: raise ValueError('Exclusion count mismatch')
        blocked.update(ids)
    if len(blocked) != sample['excluded_ids_n']: raise ValueError('Exclusion union mismatch')
    return blocked


def operational_settings():
    return dict(mode='resource_demonstration', status='draft_not_frozen',
        industrial_execution_authorized=False,
        seeds=[101,102,103], device='cpu', concurrency=1, torch_threads=1,
        torch_interop_threads=1, observation_dim=36, action_dim=3,
        observation_scaling='fixed_environment_scales', gamma=1.0, gae_lambda=1.0,
        decisions_per_seed=2048, rollout_size=128, updates_per_complete_seed=16,
        adam_steps_per_complete_seed=128,
        architecture={'hidden_size':64,'activation':'Tanh','shared_encoder':True,'actor_initial_logits':[0,0,0]},
        ppo={'learning_rate':0.0003,'weight_decay':0.0,'clip_ratio':0.2,
             'entropy_coefficient':0.01,'value_coefficient':0.5,'value_loss':'0.5*MSE',
             'max_grad_norm':0.5,'optimisation_epochs':4,'minibatch_size':64,
             'adam_betas':[0.9,0.999],'adam_eps':1e-8,'value_clipping':False},
        phases={'corpus':{'episodes':64,'wall_seconds':600,'uniform_seed':20261006},
                'training':{'seeds':3,'wall_seconds_per_seed':600},
                'evaluation':{'episodes':56,'wall_seconds':600,'uniform_seed':20261007}},
        checkpoint_selection='final_confirmed_checkpoint_no_evaluation_selection',
        incomplete_budget='record_incomplete_no_automatic_resume_no_budget_extension',
        physical_stability_verified=None, markov_sufficiency_claimed=False,
        superiority_required_for_resource_integrity=False,
        pending_before_freeze=['industrial_corpus_executor','industrial_PPO_executor',
            'industrial_evaluation_executor','RSS_measurement','full_dependency_hash_check',
            'synthetic_tests_of_industrial_adapters'])


def check(orders, *, root=ROOT, study=STUDY):
    start = time.perf_counter()
    if sha(orders) != DATASET_SHA: raise ValueError('Dataset SHA256 mismatch')
    sample_path = study/'resource_sample_draft.json'
    sample = json.loads(sample_path.read_text()); rows = validate_sample(sample)
    if sample['dataset_sha256'] != DATASET_SHA: raise ValueError('Sample dataset mismatch')
    selector = study/'tools/select_resource_sample.py'
    if sha(selector) != sample['selector_sha256']: raise ValueError('Selector mismatch')
    pool = root/'online_policy_ml/data/splits/val_order_ids_full.json'
    if sha(pool) != sample['pool_sha256']: raise ValueError('Pool hash mismatch')
    blocked = verify_sources(sample, root)
    if blocked & {r['order_id'] for r in rows}: raise ValueError('Sample intersects exclusions')
    # Selector reconstructs signatures and checks clones from metadata only.
    command = [sys.executable, str(selector.absolute()), '--orders', str(Path(orders).absolute())]
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180, check=True)
    replay = json.loads(run.stdout)
    for split in ('train','evaluation'):
        expected = {target:[r['order_id'] for r in sample[split][target]] for target in TARGETS}
        if replay[split] != expected: raise ValueError('Deterministic selection mismatch')
    if replay['excluded_ids_n'] != sample['excluded_ids_n'] or replay['pool_remaining'] != sample['pool_remaining']:
        raise ValueError('Selection metadata mismatch')
    # Reconstruct each selected signature as well, independently of ID comparison.
    sys.path.insert(0,str(root/'paper/tools'))
    from compact_study import build_compact_problem
    orders_document = json.loads(Path(orders).read_text())
    for row in rows:
        problem = build_compact_problem(orders_document,row['order_id'])
        dims = problem.containers[0].dimensions
        items = [[*sorted([float(i.length),float(i.width),float(i.height)]),float(i.weight)] for i in problem.items]
        payload = {'target':orders_document[row['order_id']]['properties']['target'],
            'bin_lwh':[float(dims.length),float(dims.width),float(dims.height)],
            'constraints':problem.constraints.model_dump(mode='json'), 'items_in_order':items}
        digest = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if digest != row['signature'] or len(items) != row['n_items']: raise ValueError('Sample signature mismatch')
    dependencies = set((root/'src/packing_services').rglob('*.py'))
    dependencies.update((study/'tools').glob('*.py'))
    dependencies.update((root/'paper/studies/rl_rule_selection/tools').glob('*.py'))
    dependencies.update((root/'paper/tools').glob('*.py'))
    dependencies.add(root/'online_policy_ml/src_ml/bedbpp_eval.py')
    hashes = {p.relative_to(root).as_posix():sha(p) for p in sorted(dependencies)}
    draft = operational_settings()
    draft.update(sample_relpath=sample_path.relative_to(root).as_posix(), sample_sha256=sha(sample_path),
        dataset_sha256=DATASET_SHA, environment_contract_sha256=sha(study/'environment_contract_draft.json'),
        corpus_schema_sha256=sha(study/'corpus_schema_v1.json'), implementation_sha256=hashes,
        prepared_at_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip())
    versions = {}
    for name in ('torch','numpy','pydantic'):
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]='not_installed'
    report = dict(status='static_verified_not_frozen', sample_orders=24, train=16,evaluation=8,
        exclusion_sources=len(sample['exclusion_sources']), excluded_ids=len(blocked),
        selected_signatures_recomputed=24, deterministic_selector_replayed=True,
        implementation_files_hashed=len(hashes), versions_observed=versions,
        metadata_wall_seconds=time.perf_counter()-start, candidate_generation_executed=False,
        packing_executed=False, training_executed=False, protocol_frozen=False)
    return draft, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--static-only',action='store_true',required=True)
    parser.add_argument('--orders',type=Path,required=True)
    parser.add_argument('--write-draft',action='store_true')
    args = parser.parse_args()
    draft, report = check(args.orders)
    if args.write_draft:
        path = STUDY/'resource_campaign_protocol_draft.json'
        with path.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(draft,indent=2,sort_keys=True,allow_nan=False)+'\n')
        report['draft_written']=path.relative_to(ROOT).as_posix()
        report['draft_sha256']=sha(path)
    print(json.dumps(report,indent=2,allow_nan=False))

if __name__ == '__main__': main()
