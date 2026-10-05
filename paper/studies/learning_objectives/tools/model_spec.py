"""Arquitectura y Adam del protocolo. Construir el módulo no entrena."""

from __future__ import annotations

import copy
import hashlib

import torch
from torch import nn

INPUT_DIM = 17
HIDDEN_DIM = 64
ARMS = ("classification", "preferences", "return_difference")

TRAINING_CONFIG = {
    "seeds": [11, 23, 37],
    "epochs": 40,
    "optimizer": "Adam",
    "learning_rate": 0.001,
    "betas": [0.9, 0.999],
    "eps": 1e-8,
    "weight_decay": 1e-4,
    "decoupled_weight_decay": False,
    "amsgrad": False,
    "maximize": False,
    "capturable": False,
    "differentiable": False,
    "foreach": False,
    "fused": False,
    "grad_clip_max_norm": 1.0,
    "grad_clip_norm_type": 2.0,
    "grad_clip_error_if_nonfinite": True,
    "device": "cpu",
    "dtype": "float32",
    "torch_num_threads": 1,
    "torch_num_interop_threads": 1,
    "batching": "un paso por época con la media aritmética de todos los estados de train",
    "checkpoint": "época 40",
    "seed_selection": False,
    "early_stopping": False,
    "last_layer_init": "cero",
    "arms": list(ARMS),
    "training_executed_by_this_module": False,
}


def configure_torch_runtime() -> None:
    torch.set_num_threads(int(TRAINING_CONFIG["torch_num_threads"]))
    torch.set_num_interop_threads(int(TRAINING_CONFIG["torch_num_interop_threads"]))


def build_actor(seed: int) -> nn.Sequential:
    torch.manual_seed(int(seed))
    first = nn.Linear(INPUT_DIM, HIDDEN_DIM, bias=True, dtype=torch.float32)
    second = nn.Linear(HIDDEN_DIM, 1, bias=True, dtype=torch.float32)
    with torch.no_grad():
        second.weight.zero_()
        second.bias.zero_()
    model = nn.Sequential(first, nn.ReLU(), second)
    model.to(device="cpu")
    return model


def adam_for(model: nn.Module) -> torch.optim.Adam:
    return torch.optim.Adam(
        model.parameters(),
        lr=float(TRAINING_CONFIG["learning_rate"]),
        betas=(float(TRAINING_CONFIG["betas"][0]), float(TRAINING_CONFIG["betas"][1])),
        eps=float(TRAINING_CONFIG["eps"]),
        weight_decay=float(TRAINING_CONFIG["weight_decay"]),
        amsgrad=bool(TRAINING_CONFIG["amsgrad"]),
        foreach=bool(TRAINING_CONFIG["foreach"]),
        maximize=bool(TRAINING_CONFIG["maximize"]),
        capturable=bool(TRAINING_CONFIG["capturable"]),
        differentiable=bool(TRAINING_CONFIG["differentiable"]),
        fused=bool(TRAINING_CONFIG["fused"]),
        decoupled_weight_decay=bool(TRAINING_CONFIG["decoupled_weight_decay"]),
    )


def paired_actors(seed: int) -> dict[str, nn.Module]:
    """Tres brazos con la misma inicialización. No entrena."""

    source = build_actor(seed)
    actors = {}
    for arm in ARMS:
        cloned = copy.deepcopy(source)
        cloned.load_state_dict(copy.deepcopy(source.state_dict()))
        actors[arm] = cloned
    return actors


def initialization_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()
