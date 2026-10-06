"""PPO CPU core for BED-BPP-RL. No dataset access or experiment launcher.

Draft implementation. gamma=lambda=1; bootstrap on truncation, not terminal.
All rollout tensors are frozen before optimisation; each update uses one
behaviour-policy version. See tests before integrating with real orders.
"""
from dataclasses import dataclass
import torch
from torch import nn
from torch.distributions import Categorical

OBS_DIM = 36
N_ACTIONS = 3


@dataclass(frozen=True)
class PPOConfig:
    hidden_size: int = 64
    learning_rate: float = 3e-4
    weight_decay: float = 0.0
    clip_ratio: float = 0.2
    entropy_coefficient: float = 0.01
    value_coefficient: float = 0.5
    max_grad_norm: float = 0.5
    optimisation_epochs: int = 4
    minibatch_size: int = 64


class ActorCritic(nn.Module):
    def __init__(self, config=PPOConfig()):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(OBS_DIM, config.hidden_size), nn.Tanh())
        self.actor = nn.Linear(config.hidden_size, N_ACTIONS)
        self.critic = nn.Linear(config.hidden_size, 1)
        nn.init.zeros_(self.actor.weight)
        nn.init.zeros_(self.actor.bias)

    def forward(self, observation):
        if observation.device.type != 'cpu':
            raise ValueError('CPU only')
        if observation.ndim != 2 or observation.shape[1] != OBS_DIM:
            raise ValueError('Expected batch x 36 observations')
        if not torch.isfinite(observation).all():
            raise ValueError('Non-finite observations')
        encoded = self.encoder(observation)
        return self.actor(encoded), self.critic(encoded).squeeze(-1)


def masked_distribution(logits, mask):
    if logits.ndim != 2 or logits.shape[1] != N_ACTIONS:
        raise ValueError('Expected batch x 3 logits')
    if mask.dtype != torch.bool or mask.shape != logits.shape:
        raise ValueError('Mask must be bool with logits shape')
    if mask.device != logits.device or not mask.any(dim=-1).all():
        raise ValueError('No selectable action or incompatible device')
    if not torch.isfinite(logits).all():
        raise ValueError('Non-finite logits')
    return Categorical(logits=logits.masked_fill(~mask, -torch.inf))


@torch.no_grad()
def act(model, observation, mask, *, generator=None, deterministic=False):
    """Record log_prob and value before any optimiser update."""
    logits, value = model(observation)
    distribution = masked_distribution(logits, mask)
    action = (distribution.probs.argmax(dim=-1) if deterministic else
              torch.multinomial(distribution.probs, 1, generator=generator).squeeze(-1))
    return action, distribution.log_prob(action), value, distribution.probs


@torch.no_grad()
def gae(rewards, values, next_values, terminated, truncated):
    """gamma=lambda=1. next_values correspond to actual next observations.

    Terminal: no bootstrap. Truncated: bootstrap, no trace across reset.
    The final rollout row also bootstraps when its episode remains open.
    """
    n = rewards.numel()
    arrays = (rewards, values, next_values, terminated, truncated)
    if n == 0 or any(x.ndim != 1 or x.shape != rewards.shape for x in arrays):
        raise ValueError('Expected equal nonempty 1-D vectors')
    if terminated.dtype != torch.bool or truncated.dtype != torch.bool:
        raise ValueError('Closure flags must be bool')
    if (terminated & truncated).any():
        raise ValueError('terminated and truncated are exclusive')
    if any(not torch.isfinite(x).all() for x in (rewards, values, next_values)):
        raise ValueError('Non-finite rollout')
    advantages = torch.empty_like(values)
    trace = torch.zeros((), dtype=values.dtype, device=values.device)
    for index in range(n - 1, -1, -1):
        bootstrap = (~terminated[index]).to(values.dtype)
        continue_trace = (~(terminated[index] | truncated[index])).to(values.dtype)
        delta = rewards[index] + bootstrap * next_values[index] - values[index]
        trace = delta + continue_trace * trace
        advantages[index] = trace
    return advantages, advantages + values


def normalise_advantages(advantages):
    centred = advantages - advantages.mean()
    deviation = advantages.std(unbiased=False)
    if deviation.item() == 0:
        return torch.zeros_like(advantages)
    return centred / deviation


def validate_batch(batch):
    required = ('observations', 'masks', 'actions', 'old_log_probs',
                'old_values', 'advantages', 'returns')
    if any(key not in batch for key in required):
        raise ValueError('Missing frozen rollout field')
    n = batch['actions'].numel()
    if n == 0:
        raise ValueError('Empty rollout')
    for key in required:
        value = batch[key]
        if value.device.type != 'cpu' or value.requires_grad:
            raise ValueError('Rollout must be detached CPU tensors')
        if value.shape[0] != n or not torch.isfinite(value).all():
            raise ValueError('Inconsistent/non-finite rollout')
    if batch['observations'].shape != (n, OBS_DIM):
        raise ValueError('Invalid observation shape')
    if batch['masks'].shape != (n, N_ACTIONS) or batch['masks'].dtype != torch.bool:
        raise ValueError('Invalid mask')
    if batch['actions'].shape != (n,) or batch['actions'].dtype != torch.int64:
        raise ValueError('Actions must be int64 vector')
    if ((batch['actions'] < 0) | (batch['actions'] >= N_ACTIONS)).any():
        raise ValueError('Invalid action')
    if not batch['masks'].gather(1, batch['actions'][:, None]).all():
        raise ValueError('Action incompatible with mask')
    for key in ('old_log_probs', 'old_values', 'advantages', 'returns'):
        if batch[key].shape != (n,):
            raise ValueError('Invalid scalar-field shape')


def loss_terms(model, batch, config=PPOConfig()):
    logits, values = model(batch['observations'])
    distribution = masked_distribution(logits, batch['masks'])
    log_probs = distribution.log_prob(batch['actions'])
    ratios = torch.exp(log_probs - batch['old_log_probs'])
    if not torch.isfinite(ratios).all():
        raise ValueError('Non-finite PPO ratios')
    advantages = batch['advantages']
    clipped = ratios.clamp(1-config.clip_ratio, 1+config.clip_ratio)
    policy_loss = -torch.minimum(ratios*advantages, clipped*advantages).mean()
    value_loss = 0.5 * (values-batch['returns']).square().mean()
    entropy = distribution.entropy().mean()
    total = policy_loss + config.value_coefficient*value_loss - config.entropy_coefficient*entropy
    metrics = {'policy_loss': float(policy_loss.detach()),
               'value_loss': float(value_loss.detach()), 'entropy': float(entropy.detach()),
               'approx_kl': float(((ratios-1)-(log_probs-batch['old_log_probs'])).mean().detach()),
               'clip_fraction': float(((ratios-1).abs()>config.clip_ratio).float().mean().detach())}
    return total, metrics


def make_optimizer(model, config=PPOConfig()):
    return torch.optim.Adam(model.parameters(), lr=config.learning_rate,
        weight_decay=config.weight_decay, betas=(0.9, 0.999), eps=1e-8,
        amsgrad=False, foreach=False, fused=False)


def update(model, optimizer, batch, *, config=PPOConfig(), generator=None):
    validate_batch(batch)
    # Check stored behaviour probabilities against pre-update checkpoint.
    with torch.no_grad():
        logits, values = model(batch['observations'])
        current = masked_distribution(logits, batch['masks']).log_prob(batch['actions'])
        if not torch.allclose(current, batch['old_log_probs'], atol=1e-5, rtol=1e-5):
            raise ValueError('Behaviour log_probs do not match pre-update model')
        if not torch.allclose(values, batch['old_values'], atol=1e-5, rtol=1e-5):
            raise ValueError('Behaviour values do not match pre-update model')
    frozen = {key: value.detach().clone() for key, value in batch.items()}
    frozen['advantages'] = normalise_advantages(frozen['advantages'])
    history = []; permutations = []; n = batch['actions'].numel()
    for epoch in range(config.optimisation_epochs):
        indices = torch.randperm(n, generator=generator)
        permutations.append(indices.tolist())
        for start in range(0, n, config.minibatch_size):
            selection = indices[start:start+config.minibatch_size]
            sub = {key: value[selection] for key, value in frozen.items()}
            optimizer.zero_grad(set_to_none=True)
            total, metrics = loss_terms(model, sub, config)
            if not torch.isfinite(total):
                raise ValueError('Non-finite loss')
            total.backward()
            norm = nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm,
                                           error_if_nonfinite=True)
            optimizer.step()
            if any(not torch.isfinite(param).all() for param in model.parameters()):
                raise ValueError('Non-finite parameters')
            history.append(dict(metrics, gradient_norm_before_clip=float(norm), epoch=epoch+1))
    return {'optimizer_steps': len(history), 'history': history, 'permutations': permutations}
