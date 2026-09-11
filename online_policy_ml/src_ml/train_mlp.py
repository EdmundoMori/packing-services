"""Ajuste mlp_v1: arquitectura EXACTA del loader de producción."""

from __future__ import annotations

from typing import Any, Literal

from packing_services.online.features import FEATURE_DIM

from config import HIDDEN_SIZE, MLP_WEIGHT_DECAY, SEED

SelectBest = Literal["val_acc", "val_loss"]


def _require_torch():
    try:
        import torch
        from torch import nn
        from torch.nn import functional as F
    except ImportError as exc:
        raise ImportError(
            "mlp_v1 requiere PyTorch: pip install torch  (o packing-services[torch])"
        ) from exc
    return torch, nn, F


def build_mlp_v1(hidden_size: int = HIDDEN_SIZE):
    _torch, nn, _F = _require_torch()
    del _torch
    model = nn.Sequential(
        nn.Linear(FEATURE_DIM, hidden_size),
        nn.ReLU(),
        nn.Linear(hidden_size, 1),
    )
    nn.init.zeros_(model[-1].weight)
    nn.init.zeros_(model[-1].bias)
    return model


def fit_mlp(
    train_transitions: list[dict[str, Any]],
    val_transitions: list[dict[str, Any]] | None = None,
    *,
    hidden_size: int = HIDDEN_SIZE,
    epochs: int = 10,
    lr: float = 1e-3,
    seed: int = SEED,
    clip_grad: float = 1.0,
    weight_decay: float = MLP_WEIGHT_DECAY,
    select_best: SelectBest = "val_acc",
) -> dict[str, Any]:
    torch, nn, F = _require_torch()
    torch.manual_seed(seed)
    model = build_mlp_v1(hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    history: list[dict[str, float]] = []
    best_state = None
    best_acc = -1.0
    best_loss = float("inf")
    best_epoch = 0

    def epoch_metrics(transitions: list[dict[str, Any]], train: bool) -> tuple[float, float]:
        model.train() if train else model.eval()
        total_loss = 0.0
        total_acc = 0.0
        n = 0
        ctx = torch.enable_grad() if train else torch.no_grad()
        with ctx:
            for tr in transitions:
                features = torch.tensor(tr["features"], dtype=torch.float32)
                label = torch.tensor(int(tr["label"]), dtype=torch.long)
                logits = model(features).squeeze(-1)
                if logits.ndim == 0:
                    logits = logits.unsqueeze(0)
                loss = F.cross_entropy(logits.unsqueeze(0), label.unsqueeze(0))
                if train:
                    optimizer.zero_grad()
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), clip_grad)
                    optimizer.step()
                total_loss += float(loss.item())
                total_acc += float(int(torch.argmax(logits).item() == int(tr["label"])))
                n += 1
        return total_loss / max(n, 1), total_acc / max(n, 1)

    for epoch in range(epochs):
        perm = torch.randperm(len(train_transitions)).tolist()
        shuffled = [train_transitions[i] for i in perm]
        tr_loss, tr_acc = epoch_metrics(shuffled, train=True)
        row: dict[str, float] = {
            "epoch": float(epoch + 1),
            "train_loss": tr_loss,
            "train_acc": tr_acc,
        }
        if val_transitions:
            val_loss, val_acc = epoch_metrics(val_transitions, train=False)
            row["val_loss"] = val_loss
            row["val_acc"] = val_acc
            improved = False
            if select_best == "val_acc":
                if val_acc > best_acc + 1e-12 or (
                    abs(val_acc - best_acc) <= 1e-12 and val_loss < best_loss
                ):
                    improved = True
            elif val_loss < best_loss:
                improved = True
            if improved:
                best_acc = val_acc
                best_loss = val_loss
                best_epoch = epoch + 1
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        history.append(row)

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    return {
        "model": model,
        "hidden_size": hidden_size,
        "history": history,
        "state_dict": {k: v.detach().cpu() for k, v in model.state_dict().items()},
        "best_epoch": best_epoch,
        "best_val_acc": best_acc if best_state is not None else None,
        "best_val_loss": best_loss if best_state is not None else None,
        "select_best": select_best,
        "lr": lr,
        "weight_decay": weight_decay,
    }
