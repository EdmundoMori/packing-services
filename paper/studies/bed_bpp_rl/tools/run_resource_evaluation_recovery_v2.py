"""Frozen final-policy evaluation; no training or model selection."""
import argparse
import json
import math
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(HERE.parents[2]/"tools"))
from prepare_resource_evaluation_v1 import prepare, sha, load
from resource_corpus_gate_v1 import digest


def validate_document(p):
    if p.get('sha256') != digest(p) or p.get('status') != 'frozen_evaluation_only':
        raise ValueError('Invalid evaluation protocol')
    if p.get('authorized_phase') != 'evaluation' or p.get('training_authorized') is not False:
        raise ValueError('Wrong phase')
    d = p['design']
    if d['episodes'] != 56 or d['wall_seconds_proposed'] != 600 or d['concurrency'] != 1:
        raise ValueError('Invalid evaluation budget')
    if len(d['cases']) != 56 or len({r['episode_id'] for r in d['cases']}) != 56:
        raise ValueError('Duplicate evaluation keys')


def freeze(orders):
    from run_resource_evaluation_v1 import validate_phase as original_validate
    original = STUDY/'resource_evaluation_protocol_frozen_v1.json'
    p = original_validate(original, orders)
    source = STUDY/'resource_evaluation_01'
    supervisor = load(STUDY/'resource_evaluation_01_supervisor/supervisor.json')
    if supervisor['exitcode'] != 1 or supervisor['timed_out'] or supervisor['automatic_restart']:
        raise ValueError('Unexpected original attempt')
    prior = float(supervisor['wall_seconds'])
    if not 0 < prior < 600: raise ValueError('Invalid prior time')
    reused = inspect_reuse(source, p['design'])
    if len(reused) != 4: raise ValueError('Expected four confirmed references')
    recovery = dict(status='frozen_evaluation_recovery',original_protocol_sha256=sha(original),
        dataset_sha256=sha(orders),prior_accounted_seconds=prior,remaining_seconds=600-prior,
        design=p['design'],source_relpath='resource_evaluation_01',
        source_manifest_sha256=sha(source/'confirmed_corpus/manifest.json'),
        prior_supervisor_sha256=sha(STUDY/'resource_evaluation_01_supervisor/supervisor.json'),
        reused=reused,code_sha256={name:sha(HERE/name) for name in
             ('run_resource_evaluation_recovery_v2.py','test_resource_evaluation_recovery_v2.py')},
        correction='load checkpoint[model]; policies, data, actions and weights unchanged',
        automatic_restart=False,attempts=1)
    recovery['sha256']=digest(recovery)
    path=STUDY/'resource_evaluation_recovery_protocol_v2.json'
    with path.open('x',encoding='utf-8') as f:
        json.dump(recovery,f,indent=2,sort_keys=True);f.write('\n')
    return dict(status='recovery_phase_frozen',reused=4,pending=52,
        prior_accounted_seconds=prior,remaining_seconds=600-prior,
        file_sha256=sha(path),packing_executed=False)


def inspect_reuse(source, design):
    from resource_corpus_adapter_v2 import verify_episode_document
    from corpus_writer import CorpusStore
    from corpus_loader import load_episode_from_store
    source=Path(source);plan=load(source/'plan.json')
    if plan['cases'] != design['cases'] or plan['uniform_base_seed'] != 20261007:
        raise ValueError('Original plan mismatch')
    expected_models={k:dict(v,path=str(STUDY/v['relpath'])) for k,v in design['models'].items()}
    if plan['models'] != expected_models:raise ValueError('Original model plan mismatch')
    entries=load(source/'confirmed_corpus/manifest.json')['confirmed_files']
    expected={c['episode_id']+'.json':c for c in design['cases']}
    result={}
    for entry in entries:
        rel=entry['relpath'];case=expected.get(rel)
        if case is None or case['model_seed'] is not None or rel in result:
            raise ValueError('Unexpected reusable key')
        doc=load_episode_from_store(CorpusStore(source/'confirmed_corpus'),rel)
        meta=doc['meta']
        if meta['order_id']!=case['order_id'] or meta['target_id']!=case['target'] or meta['behavior_policy']!=case['policy']:
            raise ValueError('Reuse identity mismatch')
        from resource_corpus_adapter_v2 import policy_seed
        seed=policy_seed(20261007,case['order_id']) if case['policy']=='uniform_rules' else None
        if meta['behavior_seed']!=seed:raise ValueError('Reuse seed mismatch')
        if verify_episode_document(doc,require_complete=True).get('complete_verification') is not True:
            raise ValueError('Reuse audit failed')
        result[rel]=sha(source/'confirmed_corpus'/rel)
    return result


def validate_phase(protocol, orders):
    from run_resource_evaluation_v1 import validate_phase as original_validate
    p=load(protocol)
    if p.get('status')!='frozen_evaluation_recovery' or p.get('sha256')!=digest(p):raise ValueError('Invalid recovery protocol')
    original=STUDY/'resource_evaluation_protocol_frozen_v1.json'
    old=original_validate(original,orders)
    if sha(original)!=p['original_protocol_sha256'] or sha(orders)!=p['dataset_sha256'] or old['design']!=p['design']:
        raise ValueError('Original protocol changed')
    for name,expected in p['code_sha256'].items():
        if Path(name).name!=name or sha(HERE/name)!=expected:raise ValueError('Recovery code changed')
    source=STUDY/p['source_relpath']
    if sha(source/'confirmed_corpus/manifest.json')!=p['source_manifest_sha256'] or inspect_reuse(source,p['design'])!=p['reused']:
        raise ValueError('Reusable artifacts changed')
    supervisor=STUDY/'resource_evaluation_01_supervisor/supervisor.json'
    prior=load(supervisor)['wall_seconds']
    if sha(supervisor)!=p['prior_supervisor_sha256'] or prior!=p['prior_accounted_seconds'] or p['remaining_seconds']!=600-prior:
        raise ValueError('Budget changed')
    return p


def actor_policy(checkpoint):
    import torch
    from ppo_core_v1 import ActorCritic, act
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    if not isinstance(saved, dict) or 'model' not in saved: raise ValueError('Expected nested training checkpoint')
    model = ActorCritic(); model.load_state_dict(saved['model'], strict=True)
    model.eval(); decisions = []
    def choose(obs, mask, _public):
        action, _, _, probs = act(model, torch.tensor([obs], dtype=torch.float32),
                                  torch.tensor([mask], dtype=torch.bool), deterministic=True)
        action = int(action.item()); probs = probs[0].tolist()
        decisions.append(dict(observation=list(obs), action_mask=list(mask),
                              action=action, probabilities=probs))
        return action
    return choose, decisions


def verify(root):
    from resource_corpus_adapter_v2 import verify_corpus
    from corpus_writer import CorpusStore
    from corpus_loader import load_episode_from_store
    root = Path(root); result = verify_corpus(root); plan = load(root/'plan.json')
    store = CorpusStore(root/'confirmed_corpus'); per_policy = {}; details = []
    for case in plan['cases']:
        doc = load_episode_from_store(store, case['episode_id']+'.json')
        if not doc['terminated'] or doc['truncated']: raise ValueError('Incomplete evaluation episode')
        if case.get('model_seed') is not None:
            trace = load(root/'actor_decisions'/(case['episode_id']+'.json'))
            if trace['checkpoint_sha256'] != plan['models'][str(case['model_seed'])]['sha256']:
                raise ValueError('Actor checkpoint identity mismatch')
            if len(trace['decisions']) != len(doc['transitions']): raise ValueError('Actor trace coverage mismatch')
            for decision, row in zip(trace['decisions'], doc['transitions']):
                if any(decision[k] != row[k] for k in ('observation','action_mask','action')):
                    raise ValueError('Actor trace mismatch')
                probs = decision['probabilities']; mask = decision['action_mask']
                if len(probs)!=3 or any(not math.isfinite(v) or v<0 for v in probs) or abs(sum(probs)-1)>1e-6:
                    raise ValueError('Invalid actor probabilities')
                if any(v!=0 for v,ok in zip(probs,mask) if not ok): raise ValueError('Unmasked probabilities')
                expected = max((i for i,ok in enumerate(mask) if ok), key=lambda i: (probs[i],-i))
                if decision['action'] != expected: raise ValueError('Not deterministic masked argmax')
        value = float(doc['summary']['reward_sum'])
        details.append(dict(order_id=case['order_id'],target=case['target'],policy=case['policy'],U_geom=value))
        per_policy.setdefault(case['policy'], []).append(value)
    return dict(result, training_executed=False, evaluation_episodes=len(details),
                policy_means={k:sum(v)/len(v) for k,v in per_policy.items()},
                per_order=details, actor_logits_recomputed=False,
                superiority_inference_performed=False)


def generate(orders, cases, models, output, *, mode, wall_seconds, protocol_sha256=None, protocol_path=None, orders_path=None, reuse_source=None):
    from resource_corpus_adapter_v2 import behavior, run_and_record, publish_episode, verify_episode_document
    from corpus_writer import CorpusStore, _atomic_write_json
    from compact_study import build_compact_problem
    if mode not in ('synthetic','industrial'): raise ValueError('Invalid mode')
    if mode=='synthetic' and any(not c['order_id'].startswith('syn-') for c in cases):
        raise ValueError('Industrial IDs forbidden in synthetic mode')
    # Industrial entry is restricted to the protocol-validated worker below.
    if mode=='industrial':
        if protocol_path is None or orders_path is None: raise ValueError('Frozen protocol required')
        frozen = validate_phase(protocol_path, orders_path)
        expected_models = {k:dict(v,path=str(STUDY/v['relpath'])) for k,v in frozen['design']['models'].items()}
        if cases != frozen['design']['cases'] or models != expected_models or wall_seconds != frozen['remaining_seconds'] or reuse_source != STUDY/frozen['source_relpath'] or orders != load(orders_path) or protocol_sha256 != sha(protocol_path):
            raise ValueError('Frozen evaluation input mismatch')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter(); deadline = start+wall_seconds
    plan = dict(cases=cases,models=models,uniform_base_seed=20261007,
                mode=mode,protocol_sha256=protocol_sha256)
    _atomic_write_json(output/'plan.json',plan)
    store = CorpusStore(output/'confirmed_corpus')
    reused = set()
    if reuse_source is not None:
        from corpus_loader import load_episode_from_store
        for rel in frozen['reused']:
            document=load_episode_from_store(CorpusStore(reuse_source/'confirmed_corpus'),rel)
            _atomic_write_json(output/'captures'/rel,document)
            _atomic_write_json(output/'audits'/rel,verify_episode_document(document,require_complete=True))
            store.publish_episode(rel,document);reused.add(rel[:-5])
        _atomic_write_json(output/'reuse.json',dict(source=str(reuse_source),keys=sorted(reused),prior_accounted_seconds=frozen['prior_accounted_seconds']))
    try:
        for case in cases:
            if case['episode_id'] in reused: continue
            if time.perf_counter()>=deadline: raise TimeoutError('Evaluation deadline')
            checkpoint = None; decisions = None
            if case.get('model_seed') is None:
                policy, seed = behavior(case['policy'],20261007,case['order_id'])
            else:
                model_info = models[str(case['model_seed'])]
                checkpoint = Path(model_info['path'])
                if sha(checkpoint)!=model_info['sha256']: raise ValueError('Checkpoint changed')
                policy, decisions = actor_policy(checkpoint); seed = None
            problem = build_compact_problem(orders,case['order_id'])
            doc,env,recorder = run_and_record(problem,episode_id=case['episode_id'],
                order_id=case['order_id'],target_id=case['target'],behavior_policy=case['policy'],
                behavior_seed=seed,policy=policy,
                hashes={'checkpoint_sha256':sha(checkpoint) if checkpoint else None,
                        'evaluation_protocol_sha256':protocol_sha256})
            try:
                audit = verify_episode_document(doc,require_complete=True)
                if audit.get('complete_verification') is not True: raise ValueError('Incomplete geometry audit')
                _atomic_write_json(output/'captures'/(case['episode_id']+'.json'),doc)
                _atomic_write_json(output/'audits'/(case['episode_id']+'.json'),audit)
                if decisions is not None:
                    _atomic_write_json(output/'actor_decisions'/(case['episode_id']+'.json'),
                                       dict(checkpoint_sha256=sha(checkpoint),actor_eval_mode=True,
                                            deterministic=True,decisions=decisions))
                if time.perf_counter()>=deadline: raise TimeoutError('Deadline before confirmation')
                publish_episode(recorder,doc,store=store,relpath=case['episode_id']+'.json')
            finally: env.close()
        result = verify(output)
        if time.perf_counter()>=deadline: raise TimeoutError('Deadline during verification')
        result.update(reused_episodes=len(reused),new_episodes=len(cases)-len(reused),mode=mode,industrial_orders_used=(mode=='industrial'),
                      wall_seconds=time.perf_counter()-start,
                      ru_maxrss_kb=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
                      RSS_scope='whole worker high-water mark; Linux KB')
        _atomic_write_json(output/'summary.json',result)
        return result
    except Exception as exc:
        _atomic_write_json(output/'failure.json',dict(error=repr(exc),status='incomplete',automatic_restart=False))
        raise


def main():
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True)
    for name in ('freeze','execute','worker','verify-only'): group.add_argument('--'+name,action='store_true')
    parser.add_argument('--orders',type=Path); parser.add_argument('--out',type=Path)
    parser.add_argument('--protocol',type=Path,default=STUDY/'resource_evaluation_recovery_protocol_v2.json')
    args = parser.parse_args()
    if args.freeze: result = freeze(args.orders)
    elif args.verify_only: result = verify(args.out)
    elif args.execute:
        p=validate_phase(args.protocol,args.orders)
        if args.out.exists(): raise ValueError('Output already exists')
        from resource_process_supervisor_v1 import supervise
        command=[sys.executable,'-u',str(Path(__file__).absolute()),'--worker',
                 '--orders',str(args.orders.absolute()),'--protocol',str(args.protocol.absolute()),'--out',str(args.out.absolute())]
        result=supervise(command,run_dir=args.out.with_name(args.out.name+'_supervisor'),timeout_seconds=p['remaining_seconds'])
    else:
        p=validate_phase(args.protocol,args.orders)
        import torch
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        models={k:dict(v,path=str(STUDY/v['relpath'])) for k,v in p['design']['models'].items()}
        result=generate(load(args.orders),p['design']['cases'],models,args.out,mode='industrial',wall_seconds=p['remaining_seconds'],protocol_sha256=sha(args.protocol),protocol_path=args.protocol,orders_path=args.orders,reuse_source=STUDY/p['source_relpath'])
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
