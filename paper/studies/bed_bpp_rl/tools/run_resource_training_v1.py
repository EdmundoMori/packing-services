"""Serial three-seed PPO launcher with per-seed external deadline; no evaluation."""
import argparse
import json
from pathlib import Path
import sys
from resource_training_gate_v1 import freeze,validate_phase,STUDY
from corpus_writer import _atomic_write_json


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    for name in ('freeze','synthetic','execute','worker','verify-only'):group.add_argument('--'+name,action='store_true')
    parser.add_argument('--orders',type=Path);parser.add_argument('--protocol',type=Path,default=STUDY/'resource_training_protocol_frozen_v1.json')
    parser.add_argument('--out',type=Path);parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.freeze:
        if args.orders is None:parser.error('--orders required')
        result=freeze(args.orders)
    elif args.synthetic or args.verify_only:
        if args.out is None:parser.error('--out required')
        import torch
        torch.set_num_threads(1);torch.set_num_interop_threads(1)
        from resource_ppo_engine_v1 import run_campaign,verify_saved
        result=verify_saved(args.out) if args.verify_only else run_campaign(args.out)
    else:
        if args.orders is None or args.out is None:parser.error('--orders and --out required')
        protocol,rows=validate_phase(args.protocol,args.orders)
        if args.worker:
            if args.seed not in protocol['seeds']:raise ValueError('Seed not frozen')
            import torch
            torch.set_num_threads(1);torch.set_num_interop_threads(1)
            from resource_ppo_engine_v1 import run_campaign
            result=run_campaign(args.out,decisions=2048,rollout_size=128,seed=args.seed,wall_seconds=600,
                train_rows=rows,mode='industrial',protocol_path=args.protocol,orders_path=args.orders)
        else:
            from resource_process_supervisor_v1 import supervise
            args.out.mkdir(parents=True,exist_ok=False)
            reports=[]
            for seed in protocol['seeds']:
                report=supervise([sys.executable,'-u',str(Path(__file__).absolute()),'--worker',
                    '--orders',str(args.orders.absolute()),'--protocol',str(args.protocol.absolute()),
                    '--seed',str(seed),'--out',str((args.out/f'seed_{seed}').absolute())],
                    run_dir=args.out/f'supervisor_{seed}',timeout_seconds=600)
                reports.append(dict(seed=seed,**report))
                if report['exitcode']!=0 or report['timed_out']:
                    _atomic_write_json(args.out/'campaign_incomplete.json',dict(status='incomplete',reports=reports,automatic_restart=False))
                    print(json.dumps(reports,indent=2));raise SystemExit(1)
                summary=json.loads((args.out/f'seed_{seed}'/'summary.json').read_text())
                if summary['status']!='completed' or summary['trained_decisions']!=2048 or summary['confirmed_updates']!=16:
                    raise ValueError('Seed incompleteness blocks next seed')
            result=dict(status='processes_completed_pending_independent_review',reports=reports,evaluation_executed=False)
            _atomic_write_json(args.out/'campaign.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
