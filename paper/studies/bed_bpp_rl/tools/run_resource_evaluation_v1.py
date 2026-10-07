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
    from check_resource_campaign_v1 import check
    from resource_training_gate_v1 import validate_phase
    validate_phase(STUDY/'resource_training_protocol_frozen_v1.json', orders)
    draft, _ = check(orders)
    p = dict(status='frozen_evaluation_only', authorized_phase='evaluation',
             training_authorized=False, design=prepare(STUDY),
             dataset_sha256=sha(orders), code_sha256=draft['implementation_sha256'],
             environment_contract_sha256=sha(STUDY/'environment_contract_draft.json'),
             corpus_schema_sha256=sha(STUDY/'corpus_schema_v1.json'),
             training_protocol_sha256=sha(STUDY/'resource_training_protocol_frozen_v1.json'),
             device='cpu', torch_threads=1, torch_interop_threads=1,
             automatic_restart=False, physical_stability_verified=None)
    p['sha256'] = digest(p)
    validate_document(p)
    path = STUDY/'resource_evaluation_protocol_frozen_v1.json'
    with path.open('x', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, sort_keys=True, indent=2); f.write('\n')
    return dict(status='evaluation_phase_frozen', file_sha256=sha(path),
                internal_digest=p['sha256'], episodes=56, packing_executed=False)


def validate_phase(protocol, orders):
    from check_resource_campaign_v1 import ROOT
    p = load(protocol); validate_document(p)
    if sha(orders) != p['dataset_sha256'] or prepare(STUDY) != p['design']:
        raise ValueError('Dataset or evaluation inputs changed')
    for rel, expected in p['code_sha256'].items():
        path = Path(rel)
        if path.is_absolute() or '..' in path.parts or sha(ROOT/path) != expected:
            raise ValueError('Frozen implementation changed: '+rel)
    for name,key in [('environment_contract_draft.json','environment_contract_sha256'),
                     ('corpus_schema_v1.json','corpus_schema_sha256'),
                     ('resource_training_protocol_frozen_v1.json','training_protocol_sha256')]:
        if sha(STUDY/name) != p[key]: raise ValueError('Frozen artifact changed')
    return p


def actor_policy(checkpoint):
    import torch
    from ppo_core_v1 import ActorCritic, act
    model = ActorCritic(); model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True))
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


def generate(orders, cases, models, output, *, mode, wall_seconds, protocol_sha256=None, protocol_path=None, orders_path=None):
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
        if cases != frozen['design']['cases'] or models != expected_models or wall_seconds != 600 or orders != load(orders_path) or protocol_sha256 != sha(protocol_path):
            raise ValueError('Frozen evaluation input mismatch')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter(); deadline = start+wall_seconds
    plan = dict(cases=cases,models=models,uniform_base_seed=20261007,
                mode=mode,protocol_sha256=protocol_sha256)
    _atomic_write_json(output/'plan.json',plan)
    store = CorpusStore(output/'confirmed_corpus')
    try:
        for case in cases:
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
        result.update(mode=mode,industrial_orders_used=(mode=='industrial'),
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
    parser.add_argument('--protocol',type=Path,default=STUDY/'resource_evaluation_protocol_frozen_v1.json')
    args = parser.parse_args()
    if args.freeze: result = freeze(args.orders)
    elif args.verify_only: result = verify(args.out)
    elif args.execute:
        validate_phase(args.protocol,args.orders)
        if args.out.exists(): raise ValueError('Output already exists')
        from resource_process_supervisor_v1 import supervise
        command=[sys.executable,'-u',str(Path(__file__).absolute()),'--worker',
                 '--orders',str(args.orders.absolute()),'--protocol',str(args.protocol.absolute()),'--out',str(args.out.absolute())]
        result=supervise(command,run_dir=args.out.with_name(args.out.name+'_supervisor'),timeout_seconds=600)
    else:
        p=validate_phase(args.protocol,args.orders)
        import torch
        torch.set_num_threads(1); torch.set_num_interop_threads(1)
        models={k:dict(v,path=str(STUDY/v['relpath'])) for k,v in p['design']['models'].items()}
        result=generate(load(args.orders),p['design']['cases'],models,args.out,mode='industrial',wall_seconds=600,protocol_sha256=sha(args.protocol),protocol_path=args.protocol,orders_path=args.orders)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
