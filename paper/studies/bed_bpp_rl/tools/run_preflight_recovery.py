"""Explicit recovery launcher. Default: validate inputs without packing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def write(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prior', type=Path, required=True)
    p.add_argument('--orders', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    started = time.monotonic()
    prior = json.loads((a.prior / 'execution_manifest.json').read_text())
    old = json.loads((a.prior / 'preflight_summary.json').read_text())
    if old['n_confirmed'] != 0 or old['n_failed_or_timeout'] != 16:
        raise ValueError('Prior attempt differs from reviewed failed attempt')
    jobs = prior['planned_episodes']
    if len(jobs) != 16 or len({j['key'] for j in jobs}) != 16:
        raise ValueError('Expected 16 distinct keys')
    if digest(a.orders) != prior['dataset_sha256']:
        raise ValueError('Dataset SHA256 mismatch')
    if a.out.exists():
        raise ValueError('Output already exists; refusing overwrite')
    tools = Path(__file__).absolute().parent
    runtime = tools / 'preflight_real_runtime.py'
    if 'spec_from_file_location' not in runtime.read_text():
        raise ValueError('Reviewed import correction not present')
    # Conservative operational carryover; excludes neither prior load nor loop.
    carry = float(old['campaign_wall_seconds']) + float(old['load_orders_seconds'])
    remaining = 600.0 - carry
    print(json.dumps({'mode': 'execute' if a.execute else 'check_only',
        'keys': len(jobs), 'orders': sorted({j['order_id'] for j in jobs}),
        'prior_accounted_seconds': carry, 'remaining_seconds': remaining,
        'runtime_sha256': digest(runtime)}, indent=2), flush=True)
    if not a.execute:
        return 0
    # No execution authorized by default. This path requires explicit flag.
    a.out.mkdir(parents=True)
    deadline = started + remaining
    orders = json.loads(a.orders.read_text())
    results = []
    write(a.out / 'execution_manifest.json', {
        'prior_manifest_sha256': digest(a.prior / 'execution_manifest.json'),
        'dataset_sha256': digest(a.orders), 'planned_episodes': jobs,
        'runtime_sha256': digest(runtime), 'launcher_sha256': digest(Path(__file__)),
        'python': sys.executable, 'prior_accounted_seconds': carry,
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()})
    child = '''import json,sys\nfrom pathlib import Path\nsys.path.insert(0,sys.argv[1])\nfrom preflight_real_runtime import worker_episode_main\npayload=json.loads(Path(sys.argv[2]).read_text())\nworker_episode_main(payload,sys.argv[3])\n'''
    reason = None
    for job in jobs:
        left = deadline - time.monotonic()
        if left <= 0:
            reason = 'global_budget'; break
        payload = dict(job)
        payload['orders'] = {job['order_id']: orders[job['order_id']]}
        payload_path = a.out / 'current_payload.json'
        write(payload_path, payload)
        target = a.out / (job['key'] + '.json')
        t = time.monotonic()
        with (a.out / (job['key'] + '.stdout.log')).open('w') as stdout, (a.out / (job['key'] + '.stderr.log')).open('w') as stderr:
            try:
                proc = subprocess.run([sys.executable, '-u', '-c', child,
                    str(tools), str(payload_path.absolute()), str(target.absolute())],
                    stdout=stdout, stderr=stderr, timeout=min(60.0, left))
                data = json.loads(target.read_text()) if target.exists() else {}
                good = proc.returncode == 0 and data.get('status') == 'ok' and data.get('metrics', {}).get('complete_verification') is True
                row = {'key': job['key'], 'exitcode': proc.returncode,
                    'status': 'ok' if good else 'failed', 'wall_seconds': time.monotonic()-t}
            except subprocess.TimeoutExpired:
                good = False
                row = {'key': job['key'], 'status': 'timeout', 'wall_seconds': time.monotonic()-t}
        results.append(row)
        write(a.out / 'progress.json', {'results': results, 'status': 'running'})
        print(row, flush=True)
        if not good:
            reason = 'worker_failure'; break
        if data['metrics']['ru_maxrss_kb'] * 1024 > 4 * 1024**3:
            reason = 'soft_rss_ceiling'; break
    payload_path = a.out / 'current_payload.json'
    if payload_path.exists():
        payload_path.unlink()
    write(a.out / 'recovery_summary.json', {'results': results,
        'status': 'completed_workers' if len(results)==16 and reason is None else 'incomplete',
        'stop_reason': reason, 'pending': len(jobs)-len(results),
        'wall_seconds': time.monotonic()-started,
        'corpus_published': False, 'portable_reverification_pending': True})
    return 0 if len(results)==16 and reason is None else 1


if __name__ == '__main__':
    raise SystemExit(main())
