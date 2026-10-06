"""Select draft resource samples from metadata only; never runs packing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

TARGETS = ('euro-pallet', 'rollcontainer')
NAMESPACE = 'bed-bpp-rl-resource-sample-v1|20261006'
DATASET_SHA = '6ecc91d92b9ce88de113ac66c45a450ac3eec303018f14cd73e4bd0eaf8eb3cc'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def ids_in(value):
    if isinstance(value, str):
        return {value} if re.fullmatch(r'\d{8}', value) else set()
    if isinstance(value, dict):
        return set().union(*(ids_in(x) for x in [*value.keys(), *value.values()])) if value else set()
    if isinstance(value, list):
        return set().union(*(ids_in(x) for x in value)) if value else set()
    return set()


def choose(rows, blocked_signatures):
    ids = [row['order_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate order IDs in candidate rows')
    used = set(blocked_signatures)
    used_ids = set()
    result = {}
    for split, count in [('train', 8), ('evaluation', 4)]:
        result[split] = {}
        for target in TARGETS:
            ordered = sorted((r for r in rows if r['target'] == target),
                key=lambda r: (hashlib.sha256(f'{NAMESPACE}|{split}|{r["order_id"]}'.encode()).hexdigest(), r['order_id']))
            picked = []
            for row in ordered:
                if row['signature'] in used or row['order_id'] in used_ids:
                    continue
                picked.append(row)
                used.add(row['signature'])
                used_ids.add(row['order_id'])
                if len(picked) == count:
                    break
            if len(picked) != count:
                raise ValueError(f'Insufficient pool: {split}/{target}')
            result[split][target] = picked
    return result


def self_test():
    rows = [{'order_id': f'{(1000 if t == TARGETS[0] else 2000) + i:08d}', 'target': t, 'signature': f'{t}:{i}', 'n_items': i}
        for t in TARGETS for i in range(1, 25)]
    a = choose(rows, set()); b = choose(list(reversed(rows)), set()); assert a == b
    flat = [r for split in a.values() for bucket in split.values() for r in bucket]
    assert len(flat) == 24 and len({r['signature'] for r in flat}) == 24
    assert len({row['order_id'] for row in flat}) == 24
    blocked = {flat[0]['signature']}; c = choose(rows, blocked)
    assert all(r['signature'] not in blocked for split in c.values() for bucket in split.values() for r in bucket)
    print('Synthetic selector checks: OK; no dataset opened')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--orders', type=Path)
    p.add_argument('--write', action='store_true')
    p.add_argument('--self-test', action='store_true')
    a = p.parse_args()
    if a.self_test:
        self_test(); return
    if a.orders is None:
        p.error('--orders required')
    root = Path(__file__).resolve().parents[4]
    output = root / 'paper/studies/bed_bpp_rl/resource_sample_draft.json'
    if a.write and output.exists():
        raise ValueError('Draft exists; refusing overwrite')
    if sha(a.orders) != DATASET_SHA:
        raise ValueError('Dataset hash mismatch')
    pool_path = root / 'online_policy_ml/data/splits/val_order_ids_full.json'
    sources = set()
    for pattern in ['online_policy_ml/**/order_ids.json', 'online_policy_ml/**/splits/*.json',
        'paper/protocols/*.json', 'paper/studies/**/sample_manifest.json',
        'paper/studies/**/protocol_frozen.json', 'paper/studies/**/learning_protocol_frozen.json',
        'paper/results/*exposed*ids*.json']:
        sources.update(root.glob(pattern))
    sources = {path for path in sources if not (path.parent.name == 'splits' and 'val' in path.name)}
    sources.discard(pool_path)
    required = [root / 'online_policy_ml/data/splits/test_order_ids_full.json',
        root / 'paper/studies/learning_objectives/sample_manifest.json',
        root / 'paper/studies/bed_bpp_rl/preflight_real_recovery_02/execution_manifest.json']
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
        sources.add(path)
    blocked = set(); source_records = []
    for path in sorted(sources):
        source_document = json.loads(path.read_text())
        if path.name == "full_split.json":
            if not isinstance(source_document, dict):
                raise ValueError(f"Invalid full_split: {path}")
            if "train" not in source_document or "test" not in source_document:
                raise ValueError(f"Missing train/test partitions: {path}")
            # full.val es el pool candidato, no una lista de exposición.
            retained_document = {
                "train": source_document["train"],
                "test": source_document["test"],
            }
            found = ids_in(retained_document)
        else:
            found = ids_in(source_document)
        blocked.update(found)
        source_records.append({'path': str(path.relative_to(root)), 'sha256': sha(path), 'ids_n': len(found)})
    orders = json.loads(a.orders.read_text())
    pool = json.loads(pool_path.read_text())
    if not isinstance(pool, list) or len(pool) != len(set(pool)):
        raise ValueError('Invalid pool')
    sys.path.insert(0, str(root / 'paper/tools'))
    from compact_study import build_compact_problem

    def row_for(order_id):
        problem = build_compact_problem(orders, order_id)
        dims = problem.containers[0].dimensions
        items = []
        for item in problem.items:
            values = [float(item.length), float(item.width), float(item.height), float(item.weight)]
            if not all(math.isfinite(x) for x in values):
                raise ValueError('Non-finite item')
            # All permutations are allowed by the compact contract. Canonicalise
            # axes to conservatively reject geometry-equivalent ordered inputs.
            items.append([*sorted(values[:3]), values[3]])
        payload = {'target': orders[order_id]['properties']['target'],
            'bin_lwh': [float(dims.length), float(dims.width), float(dims.height)],
            'constraints': problem.constraints.model_dump(mode='json'), 'items_in_order': items}
        signature = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        return {'order_id': order_id, 'target': payload['target'], 'n_items': len(items), 'signature': signature}

    blocked_signatures = set()
    for oid in sorted(blocked & set(orders)):
        if orders[oid].get('properties', {}).get('target') in TARGETS:
            blocked_signatures.add(row_for(oid)['signature'])
    rows = [row_for(oid) for oid in sorted(pool) if oid not in blocked
        and orders[oid].get('properties', {}).get('target') in TARGETS]
    selected = choose(rows, blocked_signatures)
    document = {'status': 'draft_selected_not_executed', 'namespace': NAMESPACE,
        'dataset_sha256': DATASET_SHA, 'pool_sha256': sha(pool_path),
        'selector_sha256': sha(Path(__file__)),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'exclusion_sources': source_records, 'excluded_ids_n': len(blocked),
        'excluded_absent_from_dataset_n': len(blocked-set(orders)),
        'signature_definition': 'target, bin, compact constraints, ordered items with sorted dimensions and weight; IDs omitted',
        'pool_remaining': {t: sum(r['target']==t for r in rows) for t in TARGETS},
        'train': selected['train'], 'evaluation': selected['evaluation'],
        'absolute_independence_established': False, 'packing_executed': False,
        'training_executed': False, 'sampling_not_a_representativeness_claim': True}
    if a.write:
        with output.open('x') as f:
            json.dump(document, f, indent=2, ensure_ascii=False, allow_nan=False); f.write('\n')
    print(json.dumps({'mode': 'draft_written' if a.write else 'check_only',
        'exclusion_sources': len(sources), 'excluded_ids_n': len(blocked),
        'pool_remaining': document['pool_remaining'],
        'train': {t: [r['order_id'] for r in selected['train'][t]] for t in TARGETS},
        'evaluation': {t: [r['order_id'] for r in selected['evaluation'][t]] for t in TARGETS},
        'output': str(output) if a.write else None}, indent=2))


if __name__ == '__main__':
    main()
