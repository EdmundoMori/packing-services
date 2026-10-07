"""Read saved episodes and replay policy inference only; no env steps or updates."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def close(study):
    import torch
    from ppo_core_v1 import ActorCritic,act
    from run_resource_evaluation_recovery_v2 import verify
    study=Path(study);root=study/'resource_evaluation_recovery_02'
    summary=load(root/'summary.json');report=verify(root);plan=load(root/'plan.json')
    protocol_path=study/'resource_evaluation_recovery_protocol_v2.json'
    protocol=load(protocol_path)
    from resource_corpus_gate_v1 import digest
    if protocol.get('sha256')!=digest(protocol):raise ValueError('Recovery protocol digest mismatch')
    if plan['protocol_sha256']!=sha(protocol_path):raise ValueError('Recovery protocol identity mismatch')
    if plan['cases']!=protocol['design']['cases']:raise ValueError('Evaluation plan changed')
    if report['episodes']!=56 or report['terminated']!=56 or report['truncated']!=0:
        raise ValueError('Evaluation coverage incomplete')
    if summary['reused_episodes']!=4 or summary['new_episodes']!=52:raise ValueError('Recovery accounting mismatch')
    current=load(study/'resource_evaluation_recovery_02_supervisor/supervisor.json')
    prior=load(study/'resource_evaluation_01_supervisor/supervisor.json')
    if current['exitcode']!=0 or current['timed_out'] or current['automatic_restart']:
        raise ValueError('Recovery supervisor unsuccessful')
    if sha(study/'resource_evaluation_01_supervisor/supervisor.json')!=protocol['prior_supervisor_sha256']:
        raise ValueError('Prior supervisor changed')
    if current['timeout_seconds']!=protocol['remaining_seconds']:
        raise ValueError('Recovery timeout changed')
    charged=prior['wall_seconds']+current['wall_seconds']
    if charged>600:raise ValueError('Evaluation budget exceeded')
    for rel,expected in protocol['reused'].items():
        if sha(study/'resource_evaluation_01/confirmed_corpus'/rel)!=expected or sha(root/'confirmed_corpus'/rel)!=expected:
            raise ValueError('Reusable episode changed')
    replay=[]
    for seed in (101,102,103):
        checkpoint=study/protocol['design']['models'][str(seed)]['relpath']
        if sha(checkpoint)!=protocol['design']['models'][str(seed)]['sha256']:
            raise ValueError('Checkpoint changed')
        model=ActorCritic();model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True)['model']);model.eval()
        decisions=0;hist=[0,0,0];max_error=0.;episodes=0
        for case in plan['cases']:
            if case['model_seed']!=seed:continue
            trace=load(root/'actor_decisions'/(case['episode_id']+'.json'))
            if trace['actor_eval_mode'] is not True or trace['deterministic'] is not True:
                raise ValueError('Actor metadata inconsistent')
            episodes+=1
            for row in trace['decisions']:
                action,_,_,prob=act(model,torch.tensor([row['observation']],dtype=torch.float32),torch.tensor([row['action_mask']],dtype=torch.bool),deterministic=True)
                saved=torch.tensor(row['probabilities'],dtype=torch.float32)
                error=float((prob[0]-saved).abs().max());max_error=max(error,max_error)
                if not torch.allclose(prob[0],saved,atol=1e-6,rtol=1e-6) or int(action.item())!=row['action']:
                    raise ValueError('Checkpoint inference differs from saved evaluation')
                hist[int(action.item())]+=1;decisions+=1
        if episodes!=8:raise ValueError('Actor episode coverage mismatch')
        replay.append(dict(seed=seed,episodes=episodes,decisions=decisions,action_counts=hist,max_probability_absolute_error=max_error,checkpoint_sha256=sha(checkpoint)))
    per_order=report['per_order'];grouped={}
    keys=set()
    for row in per_order:
        key=(row['order_id'],row['policy'])
        if key in keys:raise ValueError('Duplicate result key')
        keys.add(key);grouped.setdefault(row['order_id'],{})[row['policy']]=row
    if len(grouped)!=8 or len(keys)!=56:raise ValueError('Result table coverage mismatch')
    policies=list(report['policy_means']);tables=[]
    for policy in policies:
        values=[g[policy]['U_geom'] for g in grouped.values()]
        by_target={target:sum(g[policy]['U_geom'] for g in grouped.values() if g[policy]['target']==target)/4 for target in ('euro-pallet','rollcontainer')}
        tables.append(dict(policy=policy,mean_U_geom=sum(values)/8,**by_target))
    ppo=[]
    for oid,g in grouped.items():
        value=sum(g[f'ppo_deterministic_seed_{s}']['U_geom'] for s in (101,102,103))/3
        ppo.append(dict(order_id=oid,target=g['fixed_greedy_best_fit']['target'],U_geom=value))
    tables.append(dict(policy='PPO_all_seeds_order_weighted',mean_U_geom=sum(r['U_geom'] for r in ppo)/8,
        **{target:sum(r['U_geom'] for r in ppo if r['target']==target)/4 for target in ('euro-pallet','rollcontainer')}))
    csvstream=io.StringIO();writer=csv.DictWriter(csvstream,fieldnames=('policy','mean_U_geom','euro-pallet','rollcontainer'));writer.writeheader();writer.writerows(tables)
    tex=['% Generated from saved evaluation artifacts; descriptive means only.',r'\begin{tabular}{lrrr}',r'\hline',r'Policy & All orders & Euro-pallet & Rollcontainer \\',r'\hline']
    labels={'fixed_greedy_best_fit':'GreedyBestFit','fixed_lowest_top':'Lowest top','fixed_least_height_increase':'Least height increase','uniform_rules':'Uniform rules','PPO_all_seeds_order_weighted':'PPO (all seeds)'}
    for row in tables:
        label=labels.get(row['policy'],'PPO seed '+row['policy'].split('_')[-1])
        tex.append(f"{label} & {row['mean_U_geom']:.6f} & {row['euro-pallet']:.6f} & {row['rollcontainer']:.6f} "+r'\\')
    tex.extend([r'\hline',r'\end{tabular}'])
    report.update(actor_logits_recomputed=True,actor_probability_replay=replay,
        reused_episodes=4,new_episodes=52,evaluation_supervisor_wall_charged_seconds=charged,
        evaluation_wall_budget_seconds=600,aggregation=tables,
        new_packing_executed=False,new_training_executed=False,
        optimizer_replay_performed=False,superiority_inference_performed=False,
        execution_head_reported_in_launch=load(study/'resource_evaluation_recovery_02_supervisor/launch.json'),
        recovery_protocol_sha256=sha(protocol_path),summary_sha256=sha(root/'summary.json'))
    review='''# R13 — Final-policy evaluation closure\n\n56 unique episodes on eight evaluation orders: 24 final PPO actor episodes\nand 32 internal reference episodes. Four confirmed references were reused;\n52 episodes were generated during recovery. All 56 episodes terminate naturally.\nInput, sequence, orientations, rewards and AABB geometry are checked by the\nartifact verifier. Physical stability is not verified.\n\nThe first attempt failed because the evaluator loaded the entire training\ncheckpoint as a state dict instead of its model field. The original attempt\nand frozen v1 protocol remain intact. Recovery changes the loader, preserves\nweights and reuses confirmed references. Both supervisor times count against\nthe same 600-second episode-generation budget.\n\nThe closure replays deterministic policy inference on saved observations\nagainst all three final checkpoints. It does not step the environment, train,\nor replay Adam. Summary tables use equal weights for orders; the combined\nPPO row first averages the three seeds within each order.\n\nThis is a resource usability demonstration, not evidence of general packing\nsuperiority. Equal returns do not establish equality of actions or layouts.\nAction counts and per-order returns are reported separately. Eight orders,\nthree seeds and one uniform realization per order limit generalization.\nNo seed, checkpoint, configuration or method is selected by these results.\n'''
    return report,csvstream.getvalue(),'\n'.join(tex)+'\n',review

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--study-dir',type=Path,default=STUDY);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    report,csvtext,textext,review=close(args.study_dir)
    if args.write:
        destination=args.study_dir/'evaluation_closure_01'
        destination.mkdir(exist_ok=False)
        for name,text in [('verification.json',json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n'),('policy_means.csv',csvtext),('policy_means.tex',textext),('R13_evaluation_closure.md',review)]:
            (destination/name).write_text(text,encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','episodes','transitions','actor_logits_recomputed','actor_probability_replay','evaluation_supervisor_wall_charged_seconds','aggregation')},indent=2))

if __name__=='__main__':main()
