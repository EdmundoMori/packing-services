"""Linux/WSL external process-group deadline, no restart and no dataset access."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from ppo_rollout_v1 import save_record


def supervise(command, *, run_dir, timeout_seconds):
    if os.name != 'posix': raise ValueError('POSIX/WSL required')
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0: raise ValueError('Invalid timeout')
    run_dir = Path(run_dir); run_dir.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    timed_out = False
    with (run_dir/'stdout.txt').open('wb') as stdout, (run_dir/'stderr.txt').open('wb') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        save_record(run_dir/'launch.json', dict(pid=process.pid, command=command,
            timeout_seconds=timeout_seconds, automatic_restart=False))
        try:
            process.wait(timeout=max(0.001, timeout_seconds-(time.perf_counter()-start)))
        except subprocess.TimeoutExpired:
            timed_out = True
            # Group belongs to this start_new_session child; include descendants.
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
        except BaseException:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
            raise
    report = dict(status='timeout' if timed_out else ('process_exited_zero' if process.returncode == 0 else 'process_failed'),
        exitcode=process.returncode, timed_out=timed_out,
        wall_seconds=time.perf_counter()-start, timeout_seconds=timeout_seconds,
        scientific_completeness_verified=False, automatic_restart=False)
    save_record(run_dir/'supervisor.json', report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--synthetic', action='store_true', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--timeout-seconds', type=float, default=45)
    args = parser.parse_args()
    if args.out.exists(): raise FileExistsError(args.out)
    worker = Path(__file__).absolute().parent/'run_ppo_synthetic_audited_v1.py'
    result = supervise([sys.executable, '-u', str(worker), '--synthetic', '--out', str(args.out.absolute())],
        run_dir=args.run_dir, timeout_seconds=args.timeout_seconds)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['exitcode'] == 0 and not result['timed_out'] else 1)

if __name__ == '__main__': main()
