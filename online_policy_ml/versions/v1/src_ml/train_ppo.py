"""Fine-tuning PPO del actor mlp_v1 sobre el bucle online de producción.

Recompensa densa (volumen del ítem / volumen del contenedor) y penalización
solo al descartar. El critic no se exporta: el ``.pt`` sigue siendo
``Linear(35,H)→ReLU→Linear(H,1)``. El rollout replica el bucle para muestrear.
"""

from __future__ import annotations

from typing import Any

from packing_services.algorithms._constructive import order_items
from packing_services.algorithms.base import build_solution
from packing_services.algorithms.online_3d_bpp_heuristic import Online3DBPPHeuristic
from packing_services.domain.enums import SortStrategy
from packing_services.domain.models import PackingProblem, UnpackedItem
from packing_services.online.budget import InformationBudget
from packing_services.online.features import FEATURE_DIM, encode_option
from packing_services.online.mask import ValidatorMask
from packing_services.online.params import resolve_selection, support_threshold
from packing_services.online.session import ExtremePointOnlineSession
from packing_services.online.types import StepOption

from config import (
    HIDDEN_SIZE,
    PPO_CLIP,
    PPO_ENTROPY_COEF,
    PPO_GAMMA,
    PPO_INNER_EPOCHS,
    PPO_LR,
    PPO_MAX_GRAD,
    PPO_OUTER_EPOCHS,
    PPO_ROLLOUTS,
    PPO_UNPACK_PENALTY,
    PPO_VALUE_COEF,
    SEED,
    SELECTION,
)
from evaluate import evaluate_orders
from methodology import MethodologyError, assert_holdout_excluded, compare_paired
from train_mlp import build_mlp_v1


def _require_torch():
    try:
        import torch
        from torch import nn
        from torch.nn import functional as F
        from torch.distributions import Categorical
    except ImportError as exc:
        raise ImportError(
            "PPO requiere PyTorch: pip install torch (o packing-services[torch])"
        ) from exc
    return torch, nn, F, Categorical


def load_actor_from_pt(path, hidden_size: int = HIDDEN_SIZE):
    torch, _nn, _F, _Cat = _require_torch()
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict) or "state_dict" not in payload:
        raise MethodologyError(f"{path} no es un checkpoint mlp_v1 del contrato v1")
    hidden = int(payload.get("hidden_size", hidden_size))
    actor = build_mlp_v1(hidden)
    actor.load_state_dict(payload["state_dict"])
    actor.eval()
    return actor, hidden


def build_critic(hidden_size: int = HIDDEN_SIZE):
    _torch, nn, _F, _Cat = _require_torch()
    critic = nn.Sequential(
        nn.Linear(FEATURE_DIM, hidden_size),
        nn.ReLU(),
        nn.Linear(hidden_size, 1),
    )
    nn.init.zeros_(critic[-1].weight)
    nn.init.zeros_(critic[-1].bias)
    return critic


def _bin_volume(problem: PackingProblem) -> float:
    return float(sum(c.length * c.width * c.height for c in problem.containers))


def place_reward(item, bin_volume: float) -> float:
    """Recompensa densa GOPT: volumen del ítem / volumen del contenedor."""

    return float(item.volume) / max(bin_volume, 1.0)


def discard_penalty(item, bin_volume: float, *, unpack_penalty: float = PPO_UNPACK_PENALTY) -> float:
    return unpack_penalty * (float(item.volume) / max(bin_volume, 1.0))


def terminal_reward(solution, *, unpack_penalty: float = PPO_UNPACK_PENALTY) -> float:
    """Resumen de episodio (no se usa para aprender). Conservado por los tests."""

    del unpack_penalty
    return float(solution.metrics.volume_utilization)


def _assign_returns(steps: list[dict[str, Any]], gamma: float) -> None:
    ret = 0.0
    for step in reversed(steps):
        ret = float(step["reward"]) + gamma * ret
        step["return"] = ret


def _actor_logits(actor, torch, features):
    logits = actor(features).squeeze(-1)
    if logits.ndim == 0:
        logits = logits.unsqueeze(0)
    return logits


def rollout_episode(
    problem: PackingProblem,
    actor,
    critic,
    *,
    lookahead_p: int,
    select_s: int,
    deterministic: bool = False,
    unpack_penalty: float = PPO_UNPACK_PENALTY,
    gamma: float = PPO_GAMMA,
) -> dict[str, Any]:
    torch, _nn, _F, Categorical = _require_torch()
    constraints = problem.constraints
    bin_volume = _bin_volume(problem)
    params = {
        **problem.algorithm.parameters,
        "lookahead_p": lookahead_p,
        "select_s": select_s,
    }
    budget = InformationBudget.from_parameters(params)
    selection = resolve_selection(params) or SELECTION
    min_support = support_threshold(params, constraints.basic_stability)
    session = ExtremePointOnlineSession(problem.containers, selection=selection)
    mask = ValidatorMask(problem, min_support_ratio=min_support)
    remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
    unpacked: list[UnpackedItem] = []
    steps: list[dict[str, Any]] = []

    actor.eval()
    critic.eval()
    while remaining:
        select_s_now, observe_p = budget.window(len(remaining))
        selectable = remaining[:select_s_now]
        preview = remaining[:observe_p]
        options: list[StepOption] = []
        for buffer_index, item in enumerate(selectable):
            for cand in session.candidates(item, constraints):
                if mask.allows(cand, item, session, constraints):
                    options.append(
                        StepOption(item=item, candidate=cand, buffer_index=buffer_index)
                    )
        if not options:
            skipped = remaining.pop(0)
            unpacked.append(
                UnpackedItem(
                    item_id=skipped.id,
                    reason="No hay colocación legal con el presupuesto de información actual",
                )
            )
            if steps:
                steps[-1]["reward"] -= discard_penalty(
                    skipped, bin_volume, unpack_penalty=unpack_penalty
                )
            continue

        rows = [
            encode_option(
                opt,
                session=session,
                preview=preview,
                remaining_count=len(remaining),
            )
            for opt in options
        ]
        features = torch.tensor(rows, dtype=torch.float32)
        with torch.no_grad():
            logits = _actor_logits(actor, torch, features)
            dist = Categorical(logits=logits)
            if deterministic:
                action = torch.argmax(logits)
            else:
                action = dist.sample()
            log_prob = dist.log_prob(action)
            value = critic(features.mean(dim=0)).squeeze()

        idx = int(action.item())
        chosen = options[idx]
        session.commit(chosen.candidate, chosen.item)
        remaining = [it for it in remaining if it.id != chosen.item.id]
        steps.append(
            {
                "features": features,
                "action": idx,
                "log_prob": float(log_prob.item()),
                "value": float(value.item()),
                "reward": place_reward(chosen.item, bin_volume),
            }
        )

    solution = build_solution(
        problem=problem,
        metadata=Online3DBPPHeuristic.metadata,
        packed_items=session.packed,
        unpacked_items=unpacked,
        execution_time_seconds=0.0,
    )
    _assign_returns(steps, gamma)
    return {
        "steps": steps,
        "reward": float(sum(s["reward"] for s in steps)),
        "volume_utilization": float(solution.metrics.volume_utilization),
        "items_packed": int(solution.metrics.items_packed),
        "items_unpacked": int(solution.metrics.items_unpacked),
        "is_valid": bool(solution.validation_report and solution.validation_report.is_valid),
    }


def _ppo_update(
    actor,
    critic,
    steps: list[dict[str, Any]],
    *,
    optimizer,
    clip: float,
    entropy_coef: float,
    value_coef: float,
    inner_epochs: int,
    max_grad: float,
) -> dict[str, float]:
    torch, nn, F, Categorical = _require_torch()
    if not steps:
        return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

    rewards = torch.tensor([s["return"] for s in steps], dtype=torch.float32)
    old_logp = torch.tensor([s["log_prob"] for s in steps], dtype=torch.float32)
    old_value = torch.tensor([s["value"] for s in steps], dtype=torch.float32)
    adv = rewards - old_value
    if adv.numel() > 1:
        adv = (adv - adv.mean()) / (adv.std(unbiased=False) + 1e-8)

    last = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
    actor.train()
    critic.train()
    for _ in range(inner_epochs):
        policy_acc = 0.0
        value_acc = 0.0
        ent_acc = 0.0
        optimizer.zero_grad()
        for i, step in enumerate(steps):
            features = step["features"]
            logits = _actor_logits(actor, torch, features)
            dist = Categorical(logits=logits)
            action = torch.tensor(step["action"], dtype=torch.long)
            new_logp = dist.log_prob(action)
            ratio = torch.exp(new_logp - old_logp[i])
            surr1 = ratio * adv[i]
            surr2 = torch.clamp(ratio, 1.0 - clip, 1.0 + clip) * adv[i]
            policy_loss = -torch.min(surr1, surr2)
            value = critic(features.mean(dim=0)).squeeze()
            value_loss = F.mse_loss(value, rewards[i])
            entropy = dist.entropy()
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy
            loss.backward()
            policy_acc += float(policy_loss.item())
            value_acc += float(value_loss.item())
            ent_acc += float(entropy.item())
        nn.utils.clip_grad_norm_(
            list(actor.parameters()) + list(critic.parameters()),
            max_grad,
        )
        optimizer.step()
        n = max(len(steps), 1)
        last = {
            "policy_loss": policy_acc / n,
            "value_loss": value_acc / n,
            "entropy": ent_acc / n,
        }
    return last


def fit_ppo(
    orders: dict[str, Any],
    train_ids: list[str],
    val_ids: list[str],
    *,
    init_path,
    lookahead_p: int = 1,
    select_s: int = 1,
    outer_epochs: int = PPO_OUTER_EPOCHS,
    inner_epochs: int = PPO_INNER_EPOCHS,
    lr: float = PPO_LR,
    clip: float = PPO_CLIP,
    entropy_coef: float = PPO_ENTROPY_COEF,
    value_coef: float = PPO_VALUE_COEF,
    unpack_penalty: float = PPO_UNPACK_PENALTY,
    rollouts: int = PPO_ROLLOUTS,
    gamma: float = PPO_GAMMA,
    seed: int = SEED,
    hidden_size: int = HIDDEN_SIZE,
) -> dict[str, Any]:
    """Fine-tuning PPO. Val elige el actor; test y holdout no entran."""

    from problems import order_to_problem

    assert_holdout_excluded(train_ids, role="ppo_train")
    assert_holdout_excluded(val_ids, role="ppo_val")
    if not train_ids or not val_ids:
        raise MethodologyError("fit_ppo exige train y val no vacíos")

    torch, _nn, _F, _Cat = _require_torch()
    torch.manual_seed(seed)
    actor, hidden = load_actor_from_pt(init_path, hidden_size)
    critic = build_critic(hidden)
    optimizer = torch.optim.Adam(
        list(actor.parameters()) + list(critic.parameters()),
        lr=lr,
    )

    def pack_rows(order_ids: list[str], path: str) -> list[dict[str, Any]]:
        return evaluate_orders(
            orders,
            order_ids,
            engine="learned",
            lookahead_p=lookahead_p,
            select_s=select_s,
            model_path=path,
        )

    history: list[dict[str, Any]] = []
    best_state = {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()}
    best_val = -1.0
    best_epoch = 0

    from export_ckpt import export_mlp_pt
    from paths import REPORTS_DIR

    scratch = REPORTS_DIR / "_ppo_eval_actor.pt"
    export_mlp_pt(best_state, scratch, hidden_size=hidden)
    baseline_val = pack_rows(val_ids, str(scratch))
    best_val = float(sum(r["volume_utilization"] for r in baseline_val) / len(baseline_val))

    for epoch in range(1, outer_epochs + 1):
        batch_steps: list[dict[str, Any]] = []
        ep_rewards: list[float] = []
        for oid in train_ids:
            problem = order_to_problem(
                orders,
                oid,
                lookahead_p=lookahead_p,
                select_s=select_s,
                algorithm_name="drl_policy_3d_bpp",
                model_path=str(init_path),
            )
            for _ in range(max(int(rollouts), 1)):
                episode = rollout_episode(
                    problem,
                    actor,
                    critic,
                    lookahead_p=lookahead_p,
                    select_s=select_s,
                    deterministic=False,
                    unpack_penalty=unpack_penalty,
                    gamma=gamma,
                )
                ep_rewards.append(float(episode["reward"]))
                batch_steps.extend(episode["steps"])

        losses = _ppo_update(
            actor,
            critic,
            batch_steps,
            optimizer=optimizer,
            clip=clip,
            entropy_coef=entropy_coef,
            value_coef=value_coef,
            inner_epochs=inner_epochs,
            max_grad=PPO_MAX_GRAD,
        )
        export_mlp_pt(
            {k: v.detach().cpu() for k, v in actor.state_dict().items()},
            scratch,
            hidden_size=hidden,
        )
        val_rows = pack_rows(val_ids, str(scratch))
        val_util = float(sum(r["volume_utilization"] for r in val_rows) / len(val_rows))
        row = {
            "epoch": epoch,
            "train_reward": float(sum(ep_rewards) / max(len(ep_rewards), 1)),
            "val_util": val_util,
            "n_steps": len(batch_steps),
            **losses,
        }
        history.append(row)
        if val_util > best_val + 1e-12:
            best_val = val_util
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in actor.state_dict().items()}

    actor.load_state_dict(best_state)
    actor.eval()
    if scratch.is_file():
        scratch.unlink()
    return {
        "actor": actor,
        "critic": critic,
        "hidden_size": hidden,
        "state_dict": best_state,
        "history": history,
        "best_epoch": best_epoch,
        "best_val_util": best_val,
        "init_path": str(init_path),
        "lookahead_p": lookahead_p,
        "select_s": select_s,
        "lr": lr,
        "rollouts": rollouts,
        "gamma": gamma,
    }


def compare_ppo_to_baselines(
    ppo_rows: list[dict[str, Any]],
    heuristic_rows: list[dict[str, Any]],
    bc_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    vs_h = compare_paired(ppo_rows, heuristic_rows, label_a="ppo", label_b="heuristic")
    vs_bc = compare_paired(ppo_rows, bc_rows, label_a="ppo", label_b="imitation")
    return {
        "vs_heuristic": vs_h,
        "vs_imitation": vs_bc,
        "can_promote_over_heuristic": bool(vs_h["significant"] and vs_h["mean_delta"] > 0),
        "can_promote_over_imitation": bool(vs_bc["significant"] and vs_bc["mean_delta"] > 0),
    }
