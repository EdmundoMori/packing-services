"""Corpus adapter with frozen initial-phase gate; no training launcher.

Four behavior policies share the same environment contract. These episodes
are not PPO training experiences. No behavior importance weights are claimed.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import resource
import sys
import time

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('environment',HERE/'environment.py')
module=importlib.util.module_from_spec(spec);sys.modules['environment']=module
spec.loader.exec_module(module)
from episode_export import run_and_record, publish_episode, fixed_action
from corpus_writer import CorpusStore, _atomic_write_json
from corpus_loader import load_episode_from_store, iter_agent_transitions_from_store
from resource_verifier import verify_episode_document
from synthetic_problems import synthetic_order
from compact_study import build_compact_problem

POLICIES=('fixed_greedy_best_fit','fixed_lowest_top','fixed_least_height_increase','uniform_rules')


def policy_seed(base_seed, order_id):
    if type(base_seed) is not int:raise ValueError('Strict seed int required')
    digest=hashlib.sha256(f'bed-bpp-rl-corpus-v1|{base_seed}|{order_id}'.encode()).digest()
    return int.from_bytes(digest[:8],'big')


def behavior(name, base_seed, order_id):
    if name in POLICIES[:3]:return fixed_action(POLICIES.index(name)),None
    if name!='uniform_rules':raise ValueError('Unknown behavior')
    seed=policy_seed(base_seed,order_id);rng=random.Random(seed)
    def choose(_observation,mask,_public):
        allowed=[index for index,legal in enumerate(mask) if legal]
        if not allowed:raise ValueError('Cannot sample an empty mask')
        return rng.choice(allowed)
    return choose,seed


def build_plan(train_rows):
    if not train_rows:raise ValueError('Empty training sample')
    ids=[r['order_id'] for r in train_rows]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate train IDs')
    for row in train_rows:
        if row['target'] not in ('euro-pallet','rollcontainer'):raise ValueError('Invalid target')
        if not row['order_id'].replace('-','').isalnum():raise ValueError('Unsafe order ID')
    return [dict(order_id=row['order_id'],target=row['target'],policy=policy,
                 episode_id=row['order_id']+'__'+policy)
            for row in train_rows for policy in POLICIES]


def verify_corpus(root):
    from compact_study import prepare_imports
    prepare_imports()
    root=Path(root);plan=json.loads((root/'plan.json').read_text())
    store=CorpusStore(root/'confirmed_corpus')
    if not store.manifest_path.exists():raise ValueError('No confirmed corpus manifest')
    manifest=json.loads(store.manifest_path.read_text())
    expected={r['episode_id']+'.json' for r in plan['cases']}
    actual=[r['relpath'] for r in manifest['confirmed_files']]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Corpus coverage mismatch')
    transitions=0;terminated=0;truncated=0
    for case in plan['cases']:
        relpath=case['episode_id']+'.json'
        document=load_episode_from_store(store,relpath)
        if document['episode_id']!=case['episode_id']:raise ValueError('Episode identity mismatch')
        meta=document['meta']
        if meta['order_id']!=case['order_id'] or meta['target_id']!=case['target'] or meta['behavior_policy']!=case['policy']:
            raise ValueError('Behavior metadata mismatch')
        expected_seed=policy_seed(plan['uniform_base_seed'],case['order_id']) if case['policy']=='uniform_rules' else None
        if meta['behavior_seed']!=expected_seed:raise ValueError('Behavior seed mismatch')
        report=verify_episode_document(document,require_complete=True)
        if report.get('complete_verification') is not True:raise ValueError('Incomplete artifact audit')
        # Verify loader projection contains no IDs, proposals or geometry fields.
        for view in iter_agent_transitions_from_store(store,relpath):
            if set(view)!=set(('observation','observation_next','action','action_mask','action_mask_next','reward','terminated','truncated')):
                raise ValueError('Agent projection mismatch')
        transitions+=document['n_transitions'];terminated+=int(document['terminated']);truncated+=int(document['truncated'])
    return dict(status='verified',episodes=len(actual),transitions=transitions,
        terminated=terminated,truncated=truncated,geometry_audit_performed=True,
        physical_stability_verified=None,training_executed=False)


def generate(orders, train_rows, output, *, mode='synthetic', uniform_base_seed=20261006, wall_seconds=30, protocol_path=None, orders_path=None):
    # Industrial callers cannot bypass a pending freeze through this draft.
    if mode not in ('synthetic','industrial'):raise ValueError('Unknown mode')
    if mode=='industrial':
        if protocol_path is None or orders_path is None:raise ValueError('Frozen protocol and dataset required')
        from resource_corpus_gate_v1 import validate_phase
        protocol,expected_rows=validate_phase(protocol_path,orders_path)
        if train_rows!=expected_rows or orders!=json.loads(Path(orders_path).read_text()):raise ValueError('Industrial input mismatch')
        if wall_seconds!=protocol['corpus']['wall_seconds'] or uniform_base_seed!=protocol['corpus']['uniform_base_seed']:raise ValueError('Frozen budget/seed mismatch')
    elif any(not row['order_id'].startswith('syn-') for row in train_rows):raise ValueError('Only synthetic IDs allowed')
    if wall_seconds<=0:raise ValueError('Positive cooperative wall required')
    cases=build_plan(train_rows)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();deadline=start+wall_seconds
    plan=dict(mode='synthetic_only' if mode=='synthetic' else 'industrial_corpus',cases=cases,uniform_base_seed=uniform_base_seed,
        uniform_seed_derivation='sha256(bed-bpp-rl-corpus-v1|base_seed|order_id), first 8 bytes big-endian',
        wall_seconds=wall_seconds,timeout_kind='cooperative',industrial_execution_authorized=(mode=='industrial'),
        protocol_sha256=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest() if protocol_path else None,
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    _atomic_write_json(output/'plan.json',plan)
    store=CorpusStore(output/'confirmed_corpus');done=0
    try:
        for case in cases:
            if time.perf_counter()>=deadline:raise TimeoutError('Cooperative corpus deadline')
            problem=build_compact_problem(orders,case['order_id'])
            policy,seed=behavior(case['policy'],uniform_base_seed,case['order_id'])
            env=None
            try:
                document,env,recorder=run_and_record(problem,episode_id=case['episode_id'],
                    order_id=case['order_id'],target_id=case['target'],behavior_policy=case['policy'],
                    behavior_seed=seed,policy=policy,hashes={'adapter_sha256':plan['adapter_sha256']})
                report=verify_episode_document(document,require_complete=True)
                if report.get('complete_verification') is not True:raise ValueError('Artifact audit failed')
                # Preserve completed computation even if it cannot be confirmed in time.
                _atomic_write_json(output/'captures'/ (case['episode_id']+'.json'),document)
                _atomic_write_json(output/'audits'/ (case['episode_id']+'.json'),report)
                if time.perf_counter()>=deadline:raise TimeoutError('Deadline before confirmation')
                publish_episode(recorder,document,store=store,relpath=case['episode_id']+'.json')
                done+=1
            finally:
                if env is not None:env.close()
        report=verify_corpus(output)
        if time.perf_counter()>=deadline:raise TimeoutError('Deadline during final verification')
        summary=dict(report,mode='synthetic_only' if mode=='synthetic' else 'industrial_corpus',wall_seconds=time.perf_counter()-start,
            ru_maxrss_kb=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
            RSS_scope='whole process high-water mark, Linux/WSL KB; not incremental',
            industrial_orders_used=(mode=='industrial'))
        _atomic_write_json(output/'summary.json',summary)
        return summary
    except Exception as exc:
        _atomic_write_json(output/'failure.json',dict(status='incomplete',error=repr(exc),
            confirmed_episodes=done,wall_seconds=time.perf_counter()-start,automatic_restart=False))
        raise


def synthetic_fixture():
    orders={};rows=[]
    for oid,target,items in (
        ('syn-euro','euro-pallet',[('a',200,180,120),('b',150,140,100)]),
        ('syn-roll','rollcontainer',[('a',150,100,100),('b',100,80,80)])):
        orders.update(synthetic_order(oid,items,target=target))
        rows.append({'order_id':oid,'target':target})
    return orders,rows


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--synthetic',action='store_true');group.add_argument('--verify-only',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.verify_only:report=verify_corpus(args.out)
    else:
        orders,rows=synthetic_fixture();report=generate(orders,rows,args.out)
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
