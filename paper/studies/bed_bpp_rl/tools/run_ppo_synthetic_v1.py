"""Synthetic-only campaign integration. Never reads industrial BED-BPP orders.

Cooperative deadline, not a hard timeout. An interrupted update is unconfirmed;
no automatic resume. This is not the industrial campaign executor.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import torch

# Explicit local environment: historical environment modules share the name.
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('environment', HERE/'environment.py')
import sys
module = importlib.util.module_from_spec(spec)
sys.modules['environment'] = module
spec.loader.exec_module(module)
from ppo_core_v1 import ActorCritic, PPOConfig, make_optimizer, update
from ppo_rollout_v1 import EpisodeCollector, batch_from_record, verify_record, save_record, model_digest
from synthetic_problems import scenario_catalog


def atomic_torch(path, payload):
    path = Path(path)
    if path.exists(): raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.checkpoint_', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            torch.save(payload, stream); stream.flush(); os.fsync(stream.fileno())
        os.link(tmp, path)
    finally:
        os.unlink(tmp)


def write_json(path, payload):
    save_record(path, payload)


def checkpoint(model, optimizer, generators, *, decisions, updates):
    return dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
        rng={key: value.get_state() for key, value in generators.items()},
        torch_rng=torch.get_rng_state(), decisions=decisions, updates=updates)


def run_campaign(output, *, decisions=256, rollout_size=128, seed=101,
                 wall_seconds=60.0, fail_before_update=None):
    for value in (decisions, rollout_size, seed):
        if type(value) is not int: raise ValueError('Strict integers required')
    if decisions <= 0 or rollout_size <= 0 or decisions % rollout_size:
        raise ValueError('Positive divisible decision budget required')
    if wall_seconds <= 0: raise ValueError('Positive wall required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter(); deadline = start+wall_seconds
    config = PPOConfig()
    torch.manual_seed(seed)
    model = ActorCritic(config); optimizer = make_optimizer(model, config)
    generators = {name: torch.Generator().manual_seed(seed+offset)
                  for name, offset in [('actions', 1000), ('minibatches', 2000)]}
    write_json(output/'plan.json', dict(mode='synthetic_only', seed=seed,
        decisions=decisions, rollout_size=rollout_size, wall_seconds=wall_seconds,
        ppo_config=asdict(config), deadline_kind='cooperative', source_sha256={
            name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
            for name in ('ppo_core_v1.py','ppo_rollout_v1.py','run_ppo_synthetic_v1.py','environment.py')}))
    atomic_torch(output/'initial.pt', checkpoint(model, optimizer, generators, decisions=0, updates=0))
    env = module.BedBppRlEnv(); collector = None
    collected = 0; trained = 0; updates = 0; episode = 0; boundary_continuations = 0
    try:
        while trained < decisions:
            if time.perf_counter() >= deadline: raise TimeoutError('Cooperative deadline')
            folder = output/f'update_{updates+1:03d}'; folder.mkdir()
            atomic_torch(folder/'behavior.pt', checkpoint(model, optimizer, generators, decisions=collected, updates=updates))
            parts = []; count = 0; segment = 0
            while count < rollout_size:
                if time.perf_counter() >= deadline: raise TimeoutError('Cooperative deadline')
                if collector is None or collector.closed:
                    episode += 1
                    problem = scenario_catalog()['all_fit']
                    obs, info = env.reset(problem, decision_budget=decisions-collected)
                    collector = EpisodeCollector(env, obs, info, episode_id=f'synthetic_{episode:04d}')
                elif count == 0 and updates:
                    boundary_continuations += 1
                record = collector.collect(model, rollout_size-count, generator=generators['actions'])
                if not record['rows']: raise ValueError('No progress in synthetic episode')
                verify_record(record, model)
                path = folder/f'segment_{segment:03d}.json'
                write_json(path, record)
                restored = json.loads(path.read_text())
                verify_record(restored, model)
                parts.append(batch_from_record(restored))
                n = len(record['rows']); count += n; collected += n; segment += 1
            batch = {key: torch.cat([part[key] for part in parts]) for key in parts[0]}
            atomic_torch(folder/'batch.pt', batch)
            # Re-read the behavior checkpoint and reproduce records independently.
            saved = torch.load(folder/'behavior.pt', map_location='cpu', weights_only=True)
            audit_model = ActorCritic(config); audit_model.load_state_dict(saved['model'])
            for path in sorted(folder.glob('segment_*.json')):
                verify_record(json.loads(path.read_text()), audit_model)
            write_json(folder/'preupdate_verification.json', dict(verified=True, rows=count,
                behavior_model_sha256=model_digest(audit_model)))
            if fail_before_update == updates+1:
                raise RuntimeError('Synthetic injected failure before optimizer')
            if time.perf_counter() >= deadline: raise TimeoutError('Cooperative deadline')
            report = update(model, optimizer, batch, config=config, generator=generators['minibatches'])
            if time.perf_counter() >= deadline:
                raise TimeoutError('Update finished after deadline: not confirmed')
            atomic_torch(folder/'after.pt', checkpoint(model, optimizer, generators,
                decisions=collected, updates=updates+1))
            write_json(folder/'optimizer_report.json', report)
            # Commit marker written last. Artifacts without it are unconfirmed.
            files = [p for p in sorted(folder.iterdir()) if p.is_file()]
            write_json(folder/'confirmed.json', dict(update=updates+1, rows=count,
                files=[dict(relpath=p.relative_to(output).as_posix(), size_bytes=p.stat().st_size,
                    sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]))
            trained += count; updates += 1
        summary = dict(status='completed', mode='synthetic_only', collected_decisions=collected,
            trained_decisions=trained, confirmed_updates=updates, episodes_started=episode,
            open_episode=not collector.closed, boundary_continuations=boundary_continuations,
            optimizer_steps=sum(json.loads(p.read_text())['optimizer_steps']
                for p in output.glob('update_*/optimizer_report.json')),
            wall_seconds=time.perf_counter()-start, physical_stability_verified=None,
            geometry_audit_performed=False, industrial_orders_used=False)
        write_json(output/'summary.json', summary)
        return summary
    except Exception as exc:
        write_json(output/'failure.json', dict(status='incomplete', error=repr(exc),
            collected_decisions=collected, trained_decisions=trained,
            confirmed_updates=updates, wall_seconds=time.perf_counter()-start,
            automatic_resume=False))
        raise
    finally:
        env.close()


def verify_saved(output):
    output = Path(output)
    plan = json.loads((output/'plan.json').read_text())
    config = PPOConfig(**plan['ppo_config']); rows = 0; updates = 0
    for marker in sorted(output.glob('update_*/confirmed.json')):
        confirmation = json.loads(marker.read_text())
        for item in confirmation['files']:
            path = output/item['relpath']
            if path.stat().st_size != item['size_bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('Artifact hash mismatch')
        folder = marker.parent
        saved = torch.load(folder/'behavior.pt', map_location='cpu', weights_only=True)
        model = ActorCritic(config); model.load_state_dict(saved['model'])
        parts = []
        for path in sorted(folder.glob('segment_*.json')):
            record = json.loads(path.read_text()); verify_record(record, model)
            parts.append(batch_from_record(record))
        batch = torch.load(folder/'batch.pt', map_location='cpu', weights_only=True)
        for key in batch:
            if not torch.equal(batch[key], torch.cat([part[key] for part in parts])):
                raise ValueError('Persisted batch mismatch')
        rows += confirmation['rows']; updates += 1
    return dict(confirmed_updates=updates, verified_training_rows=rows,
        optimizer_replay_performed=False, geometry_audit_performed=False)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--synthetic', action='store_true')
    group.add_argument('--verify-only', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    result = verify_saved(args.out) if args.verify_only else run_campaign(args.out)
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
