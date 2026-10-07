"""Initial corpus launcher: prepare freeze, synthetic proof or supervised corpus.

No PPO or evaluation execution. Output paths must be new. No automatic retries.
"""
import argparse
import json
from pathlib import Path
import sys
from resource_corpus_gate_v1 import freeze,validate_phase,STUDY


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    for name in ('freeze','synthetic','execute','worker','verify-only'):
        group.add_argument('--'+name,action='store_true')
    parser.add_argument('--orders',type=Path)
    parser.add_argument('--protocol',type=Path,default=STUDY/'resource_corpus_protocol_frozen_v1.json')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--run-dir',type=Path)
    args=parser.parse_args()
    if args.freeze:
        if args.orders is None:parser.error('--orders required')
        result=freeze(args.orders)
    elif args.verify_only:
        if args.out is None:parser.error('--out required')
        from resource_corpus_adapter_v2 import verify_corpus
        result=verify_corpus(args.out)
    elif args.synthetic:
        if args.out is None:parser.error('--out required')
        from resource_corpus_adapter_v2 import synthetic_fixture,generate
        orders,rows=synthetic_fixture();result=generate(orders,rows,args.out)
    else:
        if args.orders is None or args.out is None:parser.error('--orders and --out required')
        protocol,rows=validate_phase(args.protocol,args.orders)
        if args.out.exists():raise FileExistsError(args.out)
        if args.worker:
            from resource_corpus_adapter_v2 import generate
            orders=json.loads(args.orders.read_text())
            result=generate(orders,rows,args.out,mode='industrial',
                uniform_base_seed=protocol['corpus']['uniform_base_seed'],
                wall_seconds=protocol['corpus']['wall_seconds'],protocol_path=args.protocol,orders_path=args.orders)
        else:
            if args.run_dir is None:parser.error('--run-dir required')
            from resource_process_supervisor_v1 import supervise
            result=supervise([sys.executable,'-u',str(Path(__file__).absolute()),'--worker',
                '--orders',str(args.orders.absolute()),'--protocol',str(args.protocol.absolute()),
                '--out',str(args.out.absolute())],run_dir=args.run_dir,
                timeout_seconds=protocol['corpus']['wall_seconds'])
    print(json.dumps(result,indent=2))
    if args.execute and (result['exitcode']!=0 or result['timed_out']):raise SystemExit(1)

if __name__=='__main__':main()
