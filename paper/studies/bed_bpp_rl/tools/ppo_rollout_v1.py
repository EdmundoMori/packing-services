"""Single-episode PPO collection and atomic audit records; no dataset launcher.

A rollout boundary keeps the episode open. Only an environment budget closes
it as truncated. Records are PPO audit supplements, not corpus-v1 episodes.
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path
import torch
from ppo_core_v1 import act, gae, validate_batch, masked_distribution


def model_digest(model):
    h = hashlib.sha256()
    for key, tensor in sorted(model.state_dict().items()):
        h.update(key.encode()); h.update(str(tuple(tensor.shape)).encode())
        h.update(str(tensor.dtype).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


class EpisodeCollector:
    """Public observations only; caller owns environment lifetime and resets."""
    def __init__(self, env, observation, info, *, episode_id):
        self.env = env
        self.observation = list(observation)
        self.info = dict(info)
        self.episode_id = episode_id
        self.offset = 0
        self.closed = bool(info['terminated'] or info['truncated'])

    @torch.no_grad()
    def collect(self, model, max_decisions, *, generator):
        if type(max_decisions) is not int or max_decisions <= 0:
            raise ValueError('max_decisions must be positive strict int')
        before = model_digest(model)
        rows = []
        for _ in range(max_decisions):
            if self.closed:
                break
            obs = torch.tensor([self.observation], dtype=torch.float32)
            mask = torch.tensor([self.info['action_mask']], dtype=torch.bool)
            action, logp, value, probs = act(model, obs, mask, generator=generator)
            nxt, reward, term, trunc, info = self.env.step(int(action.item()))
            if info.get('placed') is not True:
                raise ValueError('step without placement cannot fabricate PPO row')
            next_tensor = torch.tensor([nxt], dtype=torch.float32)
            next_value = 0.0 if term else float(model(next_tensor)[1].item())
            rows.append(dict(episode_id=self.episode_id, step_index=self.offset,
                observation=list(self.observation), action_mask=list(self.info['action_mask']),
                action=int(action.item()), old_log_prob=float(logp.item()),
                old_value=float(value.item()), behavior_probabilities=probs[0].tolist(),
                reward=float(reward), observation_next=list(nxt),
                action_mask_next=list(info['action_mask']), next_value=next_value,
                terminated=term, truncated=trunc, end_reason=info.get('end_reason')))
            self.offset += 1
            self.observation = list(nxt); self.info = dict(info)
            self.closed = bool(term or trunc)
        if model_digest(model) != before:
            raise ValueError('Policy changed during collection')
        record = dict(schema='bed-bpp-rl-ppo-audit-v1', behavior_model_sha256=before,
            episode_id=self.episode_id, rows=rows, episode_closed=self.closed,
            rollout_boundary_open=not self.closed, physical_stability_verified=None)
        if rows:
            batch = batch_from_record(record)
            for i, row in enumerate(rows):
                row['advantage'] = float(batch['advantages'][i])
                row['return'] = float(batch['returns'][i])
        return record


def batch_from_record(record):
    rows = record['rows']
    if not rows:
        raise ValueError('No PPO batch for zero-transition episode')
    def vector(key, dtype=torch.float32):
        return torch.tensor([r[key] for r in rows], dtype=dtype)
    advantages, returns = gae(vector('reward'), vector('old_value'),
        vector('next_value'), vector('terminated', torch.bool), vector('truncated', torch.bool))
    batch = dict(observations=vector('observation'), masks=vector('action_mask', torch.bool),
        actions=vector('action', torch.int64), old_log_probs=vector('old_log_prob'),
        old_values=vector('old_value'), advantages=advantages, returns=returns)
    validate_batch(batch)
    return batch


@torch.no_grad()
def verify_record(record, model):
    if record['schema'] != 'bed-bpp-rl-ppo-audit-v1' or model_digest(model) != record['behavior_model_sha256']:
        raise ValueError('Behavior checkpoint mismatch')
    rows = record['rows']
    if not rows:
        if not record['episode_closed']:
            raise ValueError('Empty open rollout')
        return {'rows': 0, 'verified': True}
    batch = batch_from_record(record)
    logits, values = model(batch['observations'])
    dist = masked_distribution(logits, batch['masks'])
    expected_logp = dist.log_prob(batch['actions'])
    if not torch.allclose(values, batch['old_values'], atol=1e-6, rtol=1e-6) or not torch.allclose(expected_logp, batch['old_log_probs'], atol=1e-6, rtol=1e-6):
        raise ValueError('Behavior values/log probabilities mismatch')
    for i, row in enumerate(rows):
        if row['episode_id'] != record['episode_id'] or type(row['action']) is not int:
            raise ValueError('Invalid identity/action type')
        if type(row['terminated']) is not bool or type(row['truncated']) is not bool:
            raise ValueError('Invalid closure types')
        if i:
            prev = rows[i-1]
            if prev['terminated'] or prev['truncated'] or row['step_index'] != prev['step_index']+1 or row['observation'] != prev['observation_next'] or row['action_mask'] != prev['action_mask_next']:
                raise ValueError('Broken transition chain')
        next_value = 0.0 if row['terminated'] else float(model(torch.tensor([row['observation_next']], dtype=torch.float32))[1].item())
        if abs(next_value-row['next_value']) > 1e-6:
            raise ValueError('Bootstrap mismatch')
        if not torch.allclose(torch.tensor(row['behavior_probabilities']), dist.probs[i], atol=1e-6, rtol=1e-6):
            raise ValueError('Probability vector mismatch')
        for field, key in [('advantage','advantages'), ('return','returns')]:
            if abs(row[field]-float(batch[key][i])) > 1e-6:
                raise ValueError('GAE/return mismatch')
    closed = rows[-1]['terminated'] or rows[-1]['truncated']
    if record['episode_closed'] != closed or record['rollout_boundary_open'] != (not closed):
        raise ValueError('Closure mismatch')
    return {'rows': len(rows), 'verified': True}


def save_record(path, record):
    """Exclusive destination, atomic replacement; no claim of host-crash safety."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(record, allow_nan=False, sort_keys=True, indent=2)+'\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.ppo_', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        # link refuses existing destinations even in a concurrent race.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)
    return hashlib.sha256(raw).hexdigest()
