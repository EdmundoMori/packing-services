"""Actor de tres logits y crítico separado. No carga pesos históricos."""

from __future__ import annotations

import math

import torch
from torch import nn

from observation import OBS_DIM
from ppo_math import (
    ADAM_AMSGRAD,
    ADAM_BETAS,
    ADAM_CAPTURABLE,
    ADAM_DECOUPLED_WEIGHT_DECAY,
    ADAM_DIFFERENTIABLE,
    ADAM_EPS,
    ADAM_FOREACH,
    ADAM_FUSED,
    ADAM_LR,
    ADAM_MAXIMIZE,
    ADAM_WEIGHT_DECAY,
    CLIP,
    ENTROPY_COEF,
    EPOCHS,
    GRAD_CLIP,
    GRAD_NORM_TYPE,
    VALUE_COEF,
    clipped_policy_loss,
    detached_log_probs,
    detached_values,
    normalize_advantages,
    probability_ratio,
    value_loss,
)

GREEDY_LOGIT_BIAS = 1.0
HIDDEN = 64


def greedy_softmax_probability(bias: float = GREEDY_LOGIT_BIAS) -> float:
    return math.exp(bias) / (math.exp(bias) + 2.0)


def build_actor() -> nn.Sequential:
    actor = nn.Sequential(
        nn.Linear(OBS_DIM, HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, 3),
    )
    last = actor[-1]
    last.weight.data.zero_()
    last.bias.data.copy_(torch.tensor([GREEDY_LOGIT_BIAS, 0.0, 0.0]))
    return actor


def build_critic() -> nn.Sequential:
    critic = nn.Sequential(
        nn.Linear(OBS_DIM, HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, 1),
    )
    critic[-1].weight.data.zero_()
    critic[-1].bias.data.zero_()
    return critic


def adam_effective_parameters() -> dict[str, object]:
    optimizer = build_optimizer([nn.Parameter(torch.zeros(1))])
    payload: dict[str, object] = {}
    for key, value in optimizer.param_groups[0].items():
        if key == "params":
            continue
        payload[key] = list(value) if isinstance(value, tuple) else value
    return payload


def build_optimizer(parameters) -> torch.optim.Adam:
    return torch.optim.Adam(
        parameters,
        lr=ADAM_LR,
        betas=ADAM_BETAS,
        eps=ADAM_EPS,
        weight_decay=ADAM_WEIGHT_DECAY,
        amsgrad=ADAM_AMSGRAD,
        maximize=ADAM_MAXIMIZE,
        foreach=ADAM_FOREACH,
        capturable=ADAM_CAPTURABLE,
        differentiable=ADAM_DIFFERENTIABLE,
        fused=ADAM_FUSED,
        decoupled_weight_decay=ADAM_DECOUPLED_WEIGHT_DECAY,
    )


def synthetic_ppo_update_seconds() -> float:
    """Una pasada sobre filas aleatorias. No mide el entrenamiento BED-BPP."""

    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        actor = build_actor()
        critic = build_critic()
        optimizer = build_optimizer(list(actor.parameters()) + list(critic.parameters()))
        observation = torch.randn(32, OBS_DIM)
        action = torch.randint(0, 3, (32,))
        old_log_prob = detached_log_probs(actor, observation, action)
        old_value = detached_values(critic, observation)
        returns = old_value + torch.rand(32)
        clock_start = __import__("time").perf_counter()
        for _epoch in range(EPOCHS):
            logits = actor(observation)
            new_log_prob = torch.log_softmax(logits, dim=-1).gather(1, action.unsqueeze(1)).squeeze(1)
            ratio = probability_ratio(new_log_prob, old_log_prob)
            value = critic(observation).squeeze(1)
            advantage = normalize_advantages(returns - old_value)
            policy_loss = clipped_policy_loss(ratio, advantage, CLIP)
            value_mse = value_loss(value, returns)
            weighted_value = VALUE_COEF * value_mse
            entropy = -(torch.softmax(logits, dim=-1) * torch.log_softmax(logits, dim=-1)).sum(-1).mean()
            loss = policy_loss + weighted_value - ENTROPY_COEF * entropy
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(actor.parameters()) + list(critic.parameters()),
                GRAD_CLIP,
                norm_type=GRAD_NORM_TYPE,
            )
            optimizer.step()
        return __import__("time").perf_counter() - clock_start
    finally:
        torch.set_num_threads(previous)
