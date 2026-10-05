"""Bucle de entrenamiento emparejado (3 brazos × semillas). No empaqueta episodios.

Un paso Adam por época; media aritmética con peso uno por estado; permutaciones
compartidas por semilla entre brazos. No selecciona por development.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

import torch
from torch import nn
from torch.nn.utils import clip_grad_norm_

from model_spec import (
    ARMS,
    TRAINING_CONFIG,
    adam_for,
    build_actor,
    configure_torch_runtime,
    initialization_sha256,
    paired_actors,
)
from torch_losses import loss_for_arm_torch


class PairingError(RuntimeError):
    """La pareja no comparte inicialización o permutaciones."""


class TrainingBudgetExceeded(RuntimeError):
    """Se agotó el presupuesto de pared de entrenamiento."""


def epoch_permutations(n_states: int, epochs: int, seed: int) -> list[list[int]]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    permutations = []
    for _epoch in range(epochs):
        permutations.append(torch.randperm(n_states, generator=generator).tolist())
    return permutations


def permutation_sha256(permutations: list[list[int]]) -> str:
    raw = json.dumps(permutations, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clone_initialized(model: nn.Module) -> nn.Module:
    cloned = copy.deepcopy(model)
    cloned.load_state_dict(copy.deepcopy(model.state_dict()))
    return cloned


def weights_equal(left: nn.Module, right: nn.Module) -> bool:
    left_state = left.state_dict()
    right_state = right.state_dict()
    if left_state.keys() != right_state.keys():
        return False
    return all(torch.equal(left_state[name], right_state[name]) for name in left_state)


def forward_logits(model: nn.Module, features: torch.Tensor) -> torch.Tensor:
    return model(features).reshape(-1)


def train_arm(
    model: nn.Module,
    states: list[dict[str, Any]],
    permutations: list[list[int]],
    arm: str,
    *,
    deadline: float | None = None,
    on_epoch: Callable[[int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    optimizer = adam_for(model)
    history: list[dict[str, Any]] = []
    if not states:
        raise ValueError("sin estados")
    for epoch, permutation in enumerate(permutations, start=1):
        if deadline is not None and time.perf_counter() > deadline:
            raise TrainingBudgetExceeded(f"presupuesto agotado antes de época {epoch}")
        optimizer.zero_grad(set_to_none=True)
        losses = []
        for index in permutation:
            state = states[index]
            logits = forward_logits(model, state["features"])
            losses.append(loss_for_arm_torch(arm, logits, state["q_hats"]))
        objective = torch.stack([loss.reshape(()) for loss in losses]).mean()
        if not torch.isfinite(objective):
            raise FloatingPointError(f"pérdida no finita en {arm} época {epoch}")
        objective.backward()
        grad_norm = clip_grad_norm_(
            model.parameters(),
            max_norm=float(TRAINING_CONFIG["grad_clip_max_norm"]),
            norm_type=float(TRAINING_CONFIG["grad_clip_norm_type"]),
            error_if_nonfinite=bool(TRAINING_CONFIG["grad_clip_error_if_nonfinite"]),
        )
        optimizer.step()
        row = {
            "epoch": epoch,
            "arm": arm,
            "loss": float(objective.detach().cpu()),
            "grad_norm_before_clip": float(grad_norm),
            "optimizer_steps": epoch,
            "finite": True,
        }
        history.append(row)
        if on_epoch is not None:
            on_epoch(epoch, row)
    return history


def paired_start(seed: int) -> tuple[dict[str, nn.Module], str, dict[str, bool]]:
    actors = paired_actors(seed)
    source_hash = initialization_sha256(actors[ARMS[0]])
    equalities: dict[str, bool] = {}
    for arm in ARMS:
        equalities[arm] = weights_equal(actors[ARMS[0]], actors[arm])
        if not equalities[arm]:
            raise PairingError(f"semilla {seed}: brazo {arm} no comparte inicialización")
        if initialization_sha256(actors[arm]) != source_hash:
            raise PairingError(f"semilla {seed}: hash de init distinto en {arm}")
    # torch.equal explícito entre todos los pares
    for left in ARMS:
        for right in ARMS:
            if left >= right:
                continue
            if not weights_equal(actors[left], actors[right]):
                raise PairingError(f"torch.equal falló {left} vs {right} seed={seed}")
    return actors, source_hash, equalities


def save_checkpoint(path: Path, model: nn.Module, *, meta: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "meta": meta,
    }
    torch.save(payload, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def load_checkpoint_logits(path: Path, features: torch.Tensor) -> list[float]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = build_actor(0)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    with torch.no_grad():
        return forward_logits(model, features).detach().cpu().tolist()


def run_seed_arms(
    *,
    seed: int,
    states: list[dict[str, Any]],
    output_seed_dir: Path,
    deadline: float | None = None,
) -> dict[str, Any]:
    configure_torch_runtime()
    epochs = int(TRAINING_CONFIG["epochs"])
    permutations = epoch_permutations(len(states), epochs, seed)
    actors, init_hash, equalities = paired_start(seed)
    perm_hash = permutation_sha256(permutations)
    output_seed_dir.mkdir(parents=True, exist_ok=True)
    (output_seed_dir / "permutations.json").write_text(
        json.dumps({"seed": seed, "sha256": perm_hash, "permutations": permutations}, indent=2) + "\n",
        encoding="utf-8",
    )
    report: dict[str, Any] = {
        "seed": seed,
        "initialization_sha256": init_hash,
        "torch_equal_across_arms": equalities,
        "permutation_sha256": perm_hash,
        "n_states": len(states),
        "epochs": epochs,
        "arms": {},
    }
    for arm in ARMS:
        arm_dir = output_seed_dir / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        history = train_arm(
            actors[arm],
            states,
            permutations,
            arm,
            deadline=deadline,
        )
        wall = time.perf_counter() - started
        ckpt = arm_dir / "checkpoint_epoch_40.pt"
        ckpt_hash = save_checkpoint(
            ckpt,
            actors[arm],
            meta={
                "seed": seed,
                "arm": arm,
                "epoch": 40,
                "initialization_sha256": init_hash,
                "permutation_sha256": perm_hash,
                "n_optimizer_steps": len(history),
            },
        )
        (arm_dir / "history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        report["arms"][arm] = {
            "wall_seconds": wall,
            "n_optimizer_steps": len(history),
            "checkpoint": str(ckpt),
            "checkpoint_sha256": ckpt_hash,
            "final_loss": history[-1]["loss"] if history else None,
            "all_finite": all(row["finite"] for row in history),
        }
    return report
