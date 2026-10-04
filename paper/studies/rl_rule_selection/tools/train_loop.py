"""Piloto PPO on-policy. No evalúa desarrollo ni test."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Callable

import torch

from model import build_actor, build_critic, build_optimizer
from observation import OBS_DIM
from ppo_math import (
    CLIP,
    DECISIONS_PER_SEED,
    ENTROPY_COEF,
    EPOCHS,
    GAE_LAMBDA,
    GAMMA,
    GRAD_CLIP,
    GRAD_NORM_TYPE,
    MINIBATCH,
    ROLLOUT_DECISIONS,
    ROLLOUTS_PER_SEED,
    VALUE_CLIPPING,
    VALUE_COEF,
    clipped_policy_loss,
    compute_returns,
    normalize_advantages,
    probability_ratio,
    value_loss,
)

Clock = Callable[[], float]


def iter_orders(order_ids: list[str], generator: torch.Generator):
    ordered = sorted(order_ids)
    while True:
        permutation = torch.randperm(len(ordered), generator=generator).tolist()
        for index in permutation:
            yield ordered[index]


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _sample_action(actor, critic, observation: list[float], generator: torch.Generator) -> tuple[int, float, float]:
    row = torch.tensor(observation, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        logits = actor(row)[0]
        value = critic(row)[0, 0]
    if not torch.isfinite(logits).all() or not torch.isfinite(value):
        raise FloatingPointError("logits o valor no finitos")
    probabilities = torch.softmax(logits, dim=0)
    action = int(torch.multinomial(probabilities, 1, generator=generator).item())
    log_prob = float(torch.log_softmax(logits, dim=0)[action])
    return action, log_prob, float(value)


def collect_rollout(
    live: dict[str, Any],
    actor,
    critic,
    action_generator: torch.Generator,
    *,
    n_steps: int,
    deadline: float,
    clock: Clock,
    start_episode: Callable[[], dict[str, Any]],
    on_finished: Callable[[dict[str, Any], str], None] | None = None,
) -> dict[str, Any]:
    """Recoge hasta n_steps llamadas a step. Conserva el episodio abierto."""

    rows: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    while len(rows) < n_steps:
        if clock() >= deadline:
            break
        if live.get("env") is None or live.get("terminated"):
            if clock() >= deadline:
                break
            started = start_episode()
            live.update(started)
            live["episode_steps"] = 0
            live["episode_placed"] = 0
            live["episode_distinct"] = 0
            if live["terminated"]:
                episodes.append(_episode_record(live, "sin_candidata"))
                if on_finished is not None:
                    on_finished(live, "sin_candidata")
                live["env"] = None
                continue
        action, log_prob, value = _sample_action(actor, critic, live["observation"], action_generator)
        _observation, reward, terminated, info = live["env"].step(action)
        if not _finite(float(reward)):
            raise FloatingPointError("recompensa no finita")
        placed = bool(info.get("placed"))
        redundancy = info.get("decision_redundancy") or {}
        distinct = placed and redundancy.get("all_three") is False
        rows.append(
            {
                "observation": list(live["observation"]),
                "action": action,
                "reward": float(reward),
                "old_log_prob": log_prob,
                "value": value,
                "terminated": bool(terminated),
                "truncated": False,
                "distinct": distinct,
            }
        )
        live["observation"] = list(_observation)
        live["terminated"] = bool(terminated)
        live["episode_steps"] += 1
        live["episode_placed"] += int(placed)
        live["episode_distinct"] += int(distinct)
        if terminated:
            cause = "secuencia_agotada" if placed else "sin_candidata"
            episodes.append(_episode_record(live, cause))
            if on_finished is not None:
                on_finished(live, cause)
            live["env"] = None
    if rows and live.get("env") is not None and not live.get("terminated"):
        rows[-1]["truncated"] = True
        rows[-1]["terminated"] = False
    return {
        "rows": rows,
        "episodes": episodes,
        "complete": len(rows) == n_steps,
        "distinct_proposal_decisions": sum(1 for row in rows if row["distinct"]),
    }


def _episode_record(live: dict[str, Any], cause: str) -> dict[str, Any]:
    return {
        "kind": "episode",
        "order_id": live["order_id"],
        "target": live["target"],
        "n_items": live["n_items"],
        "step_calls": live["episode_steps"],
        "placed": live["episode_placed"],
        "distinct_proposal_steps": live["episode_distinct"],
        "termination": cause,
    }


def rollout_tensors(actor, critic, rows: list[dict[str, Any]], live: dict[str, Any]) -> dict[str, torch.Tensor]:
    observation = torch.tensor([row["observation"] for row in rows], dtype=torch.float32)
    action = torch.tensor([row["action"] for row in rows], dtype=torch.long)
    reward = torch.tensor([row["reward"] for row in rows], dtype=torch.float32)
    old_log_prob = torch.tensor([row["old_log_prob"] for row in rows], dtype=torch.float32)
    value = torch.tensor([row["value"] for row in rows], dtype=torch.float32)
    terminated = torch.tensor([row["terminated"] for row in rows], dtype=torch.bool)
    truncated = torch.tensor([row["truncated"] for row in rows], dtype=torch.bool)
    next_value = torch.zeros(len(rows), dtype=torch.float32)
    for index in range(len(rows) - 1):
        next_value[index] = value[index + 1]
    if bool(truncated[-1].item()):
        with torch.no_grad():
            bootstrap = critic(torch.tensor(live["observation"], dtype=torch.float32).unsqueeze(0))[0, 0]
        if not torch.isfinite(bootstrap):
            raise FloatingPointError("bootstrap no finito")
        next_value[-1] = float(bootstrap)
    returns = compute_returns(reward, value, next_value, terminated, truncated, gamma=GAMMA, lam=GAE_LAMBDA)
    advantage = normalize_advantages(returns - value)
    return {
        "observation": observation,
        "action": action,
        "reward": reward,
        "old_log_prob": old_log_prob.detach(),
        "value": value.detach(),
        "returns": returns.detach(),
        "advantage": advantage.detach(),
    }


def apply_update(actor, critic, optimizer, batch: dict[str, torch.Tensor], generator: torch.Generator) -> dict[str, Any]:
    """Cuatro épocas sobre un rollout nuevo. No reutiliza rollouts anteriores."""

    if batch["observation"].shape[0] != ROLLOUT_DECISIONS:
        raise ValueError("la actualización exige un rollout de 512 decisiones")
    if ROLLOUT_DECISIONS % MINIBATCH != 0:
        raise ValueError("el rollout no es divisible en minibatches de 128")
    if VALUE_CLIPPING:
        raise RuntimeError("el clipping del valor no forma parte de este piloto")
    stored_old = batch["old_log_prob"].clone()
    adam_steps = 0
    entropies = []
    kls = []
    clips = []
    policy_losses = []
    value_mses = []
    nonfinite = 0
    count = batch["observation"].shape[0]
    for _epoch in range(EPOCHS):
        order = torch.randperm(count, generator=generator)
        for start in range(0, count, MINIBATCH):
            index = order[start : start + MINIBATCH]
            logits = actor(batch["observation"][index])
            new_log_prob = torch.log_softmax(logits, dim=-1).gather(1, batch["action"][index].unsqueeze(1)).squeeze(1)
            ratio = probability_ratio(new_log_prob, batch["old_log_prob"][index])
            policy = clipped_policy_loss(ratio, batch["advantage"][index], CLIP)
            prediction = critic(batch["observation"][index]).squeeze(1)
            mse = value_loss(prediction, batch["returns"][index])
            probabilities = torch.softmax(logits, dim=-1)
            entropy = -(probabilities * torch.log_softmax(logits, dim=-1)).sum(-1).mean()
            loss = policy + VALUE_COEF * mse - ENTROPY_COEF * entropy
            if not torch.isfinite(loss):
                nonfinite += 1
                break
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                list(actor.parameters()) + list(critic.parameters()),
                GRAD_CLIP,
                norm_type=GRAD_NORM_TYPE,
            )
            optimizer.step()
            adam_steps += 1
            outside = (ratio < 1.0 - CLIP) | (ratio > 1.0 + CLIP)
            entropies.append(float(entropy.detach()))
            kls.append(float((batch["old_log_prob"][index] - new_log_prob.detach()).mean()))
            clips.append(float(outside.float().mean()))
            policy_losses.append(float(policy.detach()))
            value_mses.append(float(mse.detach()))
        if nonfinite:
            break
    if not torch.equal(batch["old_log_prob"], stored_old):
        raise RuntimeError("la log_prob antigua fue modificada")
    def _mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    return {
        "adam_steps": adam_steps,
        "minibatches": adam_steps,
        "epochs": EPOCHS,
        "entropy": _mean(entropies),
        "approx_kl": _mean(kls),
        "clip_fraction": _mean(clips),
        "policy_loss": _mean(policy_losses),
        "value_mse": _mean(value_mses),
        "value_loss": None if not value_mses else VALUE_COEF * (_mean(value_mses) or 0.0),
        "nonfinite": nonfinite,
        "reward_sum": float(batch["reward"].sum()),
        "reward_mean": float(batch["reward"].mean()),
    }


def save_checkpoint(path: Path, actor, critic, optimizer, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "actor": actor.state_dict(),
            "critic": critic.state_dict(),
            "optimizer": optimizer.state_dict(),
            "payload": payload,
        },
        path,
    )


def load_actor(path: Path):
    blob = torch.load(path, map_location="cpu", weights_only=False)
    actor = build_actor()
    actor.load_state_dict(blob["actor"])
    actor.eval()
    return actor


def logits_of(actor, observation: list[float]) -> list[float]:
    with torch.no_grad():
        row = torch.tensor(observation, dtype=torch.float32).unsqueeze(0)
        return [float(value) for value in actor(row)[0]]


def run_budget(
    *,
    seed: int,
    actor,
    critic,
    optimizer,
    live: dict[str, Any],
    start_episode: Callable[[], dict[str, Any]],
    deadline: float,
    clock: Clock,
    on_update: Callable[[dict[str, Any]], None],
    on_episode: Callable[[dict[str, Any]], None],
    on_finished: Callable[[dict[str, Any], str], None] | None = None,
    checkpoint_path: Path,
) -> dict[str, Any]:
    action_generator = torch.Generator()
    action_generator.manual_seed(seed)
    update_generator = torch.Generator()
    update_generator.manual_seed(seed)
    decisions = 0
    distinct = 0
    updates = 0
    adam_steps = 0
    nonfinite = 0
    status = "completa"
    torch.set_num_threads(1)
    while updates < ROLLOUTS_PER_SEED and decisions < DECISIONS_PER_SEED:
        if clock() >= deadline:
            status = "incompleta_reloj"
            break
        remaining = DECISIONS_PER_SEED - decisions
        rollout = collect_rollout(
            live,
            actor,
            critic,
            action_generator,
            n_steps=min(ROLLOUT_DECISIONS, remaining),
            deadline=deadline,
            clock=clock,
            start_episode=start_episode,
            on_finished=on_finished,
        )
        for episode in rollout["episodes"]:
            on_episode(episode)
        got = len(rollout["rows"])
        decisions += got
        distinct += rollout["distinct_proposal_decisions"]
        if not rollout["complete"]:
            status = "incompleta_reloj" if clock() >= deadline else "incompleta_parcial"
            break
        if clock() >= deadline:
            status = "incompleta_reloj"
            break
        before_actor = {key: value.detach().clone() for key, value in actor.state_dict().items()}
        before_critic = {key: value.detach().clone() for key, value in critic.state_dict().items()}
        before_optimizer = copy.deepcopy(optimizer.state_dict())
        batch = rollout_tensors(actor, critic, rollout["rows"], live)
        metrics = apply_update(actor, critic, optimizer, batch, update_generator)
        adam_steps += int(metrics["adam_steps"])
        nonfinite += int(metrics["nonfinite"])
        if metrics["nonfinite"]:
            actor.load_state_dict(before_actor)
            critic.load_state_dict(before_critic)
            optimizer.load_state_dict(before_optimizer)
            status = "incompleta_no_finito"
            on_update({**metrics, "update": updates, "decisions": decisions, "status": status})
            break
        updates += 1
        record = {
            "kind": "update",
            "update": updates,
            "decisions": decisions,
            "adam_steps": metrics["adam_steps"],
            "entropy": metrics["entropy"],
            "approx_kl": metrics["approx_kl"],
            "clip_fraction": metrics["clip_fraction"],
            "policy_loss": metrics["policy_loss"],
            "value_mse": metrics["value_mse"],
            "value_loss": metrics["value_loss"],
            "reward_sum": metrics["reward_sum"],
            "reward_mean": metrics["reward_mean"],
            "nonfinite": metrics["nonfinite"],
            "elapsed_seconds": None,
        }
        on_update(record)
        save_checkpoint(
            checkpoint_path,
            actor,
            critic,
            optimizer,
            {
                "seed": seed,
                "decisions": decisions,
                "updates": updates,
                "adam_steps": adam_steps,
                "status": "en_curso",
            },
        )
    if updates == ROLLOUTS_PER_SEED and decisions == DECISIONS_PER_SEED and status == "completa":
        final_status = "completa"
    elif status == "completa":
        final_status = "incompleta"
    else:
        final_status = status
    open_episode = None
    if live.get("env") is not None and not live.get("terminated"):
        open_episode = _episode_record(live, "corte_de_presupuesto")
        on_episode(open_episode)
    return {
        "status": final_status,
        "decisions": decisions,
        "updates": updates,
        "adam_steps": adam_steps,
        "nonfinite": nonfinite,
        "distinct_proposal_decisions": distinct,
        "open_episode": open_episode,
        "equal_budget": final_status == "completa",
    }
