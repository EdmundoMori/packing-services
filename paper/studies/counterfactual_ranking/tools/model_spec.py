"""Arquitectura congelada. Construir el módulo no entrena."""

from __future__ import annotations

import torch
from torch import nn

INPUT_DIM = 17
HIDDEN_DIM = 64

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
    "shuffle": False,
    "state_order": "orden de train del protocolo y, dentro de cada pedido, índice de elección ascendente",
    "checkpoint": "última época",
    "seed_selection": False,
    "hyperparameter_search": False,
    "dropout": 0.0,
    "last_layer_init": "peso y sesgo a cero después de la inicialización de la primera capa",
    "first_layer_init": "reset_parameters de torch.nn.Linear, con la semilla fijada antes de construir las dos capas",
    "loss_reduction": "media aritmética por estado, el mismo peso en los dos brazos",
    "training_executed_by_this_module": False,
}


def configure_torch_runtime() -> None:
    torch.set_num_threads(int(TRAINING_CONFIG["torch_num_threads"]))
    torch.set_num_interop_threads(int(TRAINING_CONFIG["torch_num_interop_threads"]))


def build_actor(seed: int) -> nn.Sequential:
    """MLP compartida. La segunda capa queda a cero. No hay paso de optimización."""

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
    """Constructor explícito. Llamarlo no ejecuta las 40 épocas."""

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
