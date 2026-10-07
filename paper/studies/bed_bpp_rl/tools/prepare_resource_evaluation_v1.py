"""Prepare evaluation identities from existing artifacts; never run episodes."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
SEEDS = (101, 102, 103)
REFERENCES = ('fixed_greedy_best_fit', 'fixed_lowest_top',
              'fixed_least_height_increase', 'uniform_rules')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def prepare(study):
    study = Path(study)
    sample_path = study / 'resource_sample_draft.json'
    sample = load(sample_path)
    train = [r for group in sample['train'].values() for r in group]
    rows = [r for group in sample['evaluation'].values() for r in group]
    if len(rows) != 8 or len(train) != 16:
        raise ValueError('Expected 16 train and 8 evaluation orders')
    if any(len(group) != 4 for group in sample['evaluation'].values()):
        raise ValueError('Expected four evaluation orders per target')
    all_rows = train + rows
    if len({r['order_id'] for r in all_rows}) != 24:
        raise ValueError('Duplicate or overlapping order identities')
    if len({r['signature'] for r in all_rows}) != 24:
        raise ValueError('Duplicate or overlapping signatures')
    models = {}
    root = study / 'ppo_training_industrial_01'
    closure_path = root / 'training_closure_verification.json'
    closure = load(closure_path)
    if closure['status'] != 'training_closure_checks_passed':
        raise ValueError('Training closure not accepted')
    closure_rows = {r['seed']: r for r in closure['seeds']}
    if set(closure_rows) != set(SEEDS):
        raise ValueError('Training closure seed mismatch')
    for seed in SEEDS:
        directory = root / f'seed_{seed}'
        summary = load(directory / 'summary.json')
        final = load(directory / 'final_checkpoint.json')
        checkpoint = directory / 'final.pt'
        source = (directory / final['source']).resolve()
        if not source.is_relative_to(directory.resolve()):
            raise ValueError('Checkpoint source escapes seed directory')
        if (summary['status'] != 'completed' or
            summary['trained_decisions'] != 2048 or
            summary['confirmed_updates'] != 16 or
            summary['optimizer_steps'] != 128 or summary['open_episode']):
            raise ValueError('Incomplete training seed')
        digest = sha(checkpoint)
        if digest != final['sha256'] or digest != closure_rows[seed]['final_checkpoint_sha256']:
            raise ValueError('Checkpoint identity mismatch')
        if checkpoint.read_bytes() != source.read_bytes():
            raise ValueError('Final checkpoint differs from final update')
        supervisor = load(root / f'supervisor_{seed}' / 'supervisor.json')
        if supervisor['exitcode'] != 0 or supervisor['timed_out'] or supervisor['automatic_restart']:
            raise ValueError('Unsuccessful training supervisor')
        models[str(seed)] = {'relpath': str(checkpoint.relative_to(study)), 'sha256': digest}
    cases = []
    for row in rows:
        for policy in REFERENCES:
            cases.append({'episode_id': row['order_id'] + '__' + policy,
                          'order_id': row['order_id'], 'target': row['target'],
                          'policy': policy, 'model_seed': None})
        for seed in SEEDS:
            policy = f'ppo_deterministic_seed_{seed}'
            cases.append({'episode_id': row['order_id'] + '__' + policy,
                          'order_id': row['order_id'], 'target': row['target'],
                          'policy': policy, 'model_seed': seed})
    if len(cases) != 56 or len({r['episode_id'] for r in cases}) != 56:
        raise ValueError('Invalid evaluation coverage')
    return {'status': 'evaluation_design_verified_not_frozen',
            'sample_sha256': sha(sample_path), 'training_closure_sha256': sha(closure_path),
            'models': models, 'cases': cases, 'episodes': 56,
            'uniform_base_seed': 20261007,
            'uniform_seed_derivation': 'sha256(bed-bpp-rl-corpus-v1|base_seed|order_id), first 8 bytes big-endian',
            'actor_action': 'masked argmax; exact tie uses lowest rule index',
            'checkpoint_selection': 'all three final confirmed checkpoints',
            'wall_seconds_proposed': 600, 'concurrency': 1,
            'attempts_per_key': 1, 'automatic_restart': False,
            'aggregation': 'report each seed; average seeds within each order, then equal-weight orders',
            'scope': 'resource usability demonstration on eight held-out orders; no general superiority claim',
            'packing_executed': False, 'training_executed': False,
            'evaluation_authorized': False, 'protocol_frozen': False,
            'physical_stability_verified': None}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--study-dir', type=Path, default=STUDY)
    parser.add_argument('--write-draft', action='store_true')
    args = parser.parse_args()
    report = prepare(args.study_dir)
    if args.write_draft:
        path = args.study_dir / 'resource_evaluation_design_draft_v1.json'
        with path.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}, indent=2))

if __name__ == '__main__':
    main()
