"""Export al contrato packing-services-online-policy v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packing_services.online.features import FEATURE_DIM, FEATURE_NAMES, FEATURE_VERSION
from packing_services.online.learned.checkpoint import CHECKPOINT_FORMAT, CHECKPOINT_VERSION

from config import HIDDEN_SIZE


def export_linear_json(
    weights: list[float],
    bias: float,
    path: Path,
    *,
    notes: str = "",
) -> dict[str, Any]:
    if len(weights) != FEATURE_DIM:
        raise ValueError(f"weights len={len(weights)}; se espera {FEATURE_DIM}")
    doc = {
        "format": CHECKPOINT_FORMAT,
        "version": CHECKPOINT_VERSION,
        "backend": "linear",
        "architecture": "linear_v1",
        "feature_version": FEATURE_VERSION,
        "feature_dim": FEATURE_DIM,
        "feature_names": list(FEATURE_NAMES),
        "weights": [float(w) for w in weights],
        "bias": float(bias),
        "notes": notes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return doc


def export_mlp_pt(
    state_dict: dict[str, Any],
    path: Path,
    *,
    hidden_size: int = HIDDEN_SIZE,
    extra: dict[str, Any] | None = None,
) -> Path:
    try:
        import torch
    except ImportError as exc:
        raise ImportError("export .pt requiere torch") from exc
    payload = {
        "format": CHECKPOINT_FORMAT,
        "version": CHECKPOINT_VERSION,
        "backend": "torch",
        "architecture": "mlp_v1",
        "feature_version": FEATURE_VERSION,
        "hidden_size": int(hidden_size),
        "state_dict": state_dict,
    }
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    return path
