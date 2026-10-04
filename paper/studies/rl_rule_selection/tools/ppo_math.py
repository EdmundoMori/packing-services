"""Cálculo PPO registrable. No entrena pedidos reales.

gamma y lambda quedan en 1. La ventaja con varianza cero no se divide
por cero: el lote normalizado es cero y el término de política se anula.
"""

from __future__ import annotations

import torch
from torch import nn

GAMMA = 1.0
GAE_LAMBDA = 1.0
CLIP = 0.2
EPOCHS = 4
ROLLOUT_DECISIONS = 512
MINIBATCH = 128
ADAM_LR = 3e-4
ADAM_BETAS = (0.9, 0.999)
ADAM_EPS = 1e-8
ADAM_WEIGHT_DECAY = 0.0
ADAM_AMSGRAD = False
ADAM_MAXIMIZE = False
ADAM_FOREACH = None
ADAM_CAPTURABLE = False
ADAM_DIFFERENTIABLE = False
ADAM_FUSED = None
ADAM_DECOUPLED_WEIGHT_DECAY = False
ENTROPY_COEF = 0.01
VALUE_COEF = 0.5
VALUE_CLIPPING = False
GRAD_CLIP = 0.5
GRAD_NORM_TYPE = 2.0
DECISIONS_PER_SEED = 6144
ROLLOUTS_PER_SEED = 12
SEED_WALL_SECONDS = 4800.0
GLOBAL_WALL_SECONDS = 14400.0


def detached_log_probs(actor: nn.Module, observation: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        logits = actor(observation)
        gathered = torch.log_softmax(logits, dim=-1).gather(1, action.unsqueeze(1)).squeeze(1)
    return gathered.detach()


def detached_values(critic: nn.Module, observation: torch.Tensor) -> torch.Tensor:
    with torch.no_grad():
        values = critic(observation).squeeze(1)
    return values.detach()


def normalize_advantages(advantage: torch.Tensor) -> torch.Tensor:
    centered = advantage - advantage.mean()
    scale = centered.std(unbiased=False)
    if float(scale) == 0.0:
        return centered
    return centered / scale


def clipped_policy_loss(ratio: torch.Tensor, advantage: torch.Tensor, clip: float = CLIP) -> torch.Tensor:
    unclipped = ratio * advantage
    clipped = torch.clamp(ratio, 1.0 - clip, 1.0 + clip) * advantage
    return -torch.minimum(unclipped, clipped).mean()


def value_loss(predicted: torch.Tensor, returns: torch.Tensor) -> torch.Tensor:
    """Error cuadrático sin clipping del valor. El coeficiente 0.5 se aplica fuera."""

    if VALUE_CLIPPING:
        raise RuntimeError("este protocolo no recorta el valor")
    return (predicted - returns).pow(2).mean()


def probability_ratio(new_log_prob: torch.Tensor, old_log_prob: torch.Tensor) -> torch.Tensor:
    return torch.exp(new_log_prob - old_log_prob)


def compute_returns(
    rewards: torch.Tensor,
    values: torch.Tensor,
    next_values: torch.Tensor,
    terminated: torch.Tensor,
    truncated: torch.Tensor,
    *,
    gamma: float = GAMMA,
    lam: float = GAE_LAMBDA,
) -> torch.Tensor:
    """Retorno por transición.

    `terminated` es el fin real del episodio: no hay bootstrap.
    `truncated` es un corte del rollout con el episodio aún abierto: entra
    `next_values` y la ventaja no cruza ese límite.
    Una transición interior usa el valor del estado siguiente, que pertenece
    al mismo rollout.
    """

    if not (
        rewards.shape == values.shape == next_values.shape == terminated.shape == truncated.shape
    ):
        raise ValueError("recompensas, valores, acciones y máscaras no están alineados")
    returns = torch.zeros_like(rewards)
    gae = torch.zeros((), dtype=rewards.dtype)
    for index in range(rewards.shape[0] - 1, -1, -1):
        ended = bool(terminated[index].item())
        cut = bool(truncated[index].item())
        if ended and cut:
            raise ValueError("una transición no puede terminar y truncarse a la vez")
        next_value = torch.zeros((), dtype=rewards.dtype) if ended else next_values[index]
        delta = rewards[index] + gamma * next_value - values[index]
        carry = 0.0 if ended or cut else 1.0
        gae = delta + gamma * lam * carry * gae
        returns[index] = gae + values[index]
    return returns
