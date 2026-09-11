"""Checkpoints de producción para ``drl_policy_3d_bpp``.

Rutas relativas a la raíz del repo. El execute las resuelve con
``resolve_model_path``. No reentrenar aquí: son artefactos ya exportados.
"""

from __future__ import annotations

from typing import Any

# O3DBP / default online (p=1, s=1) — model_path principal.
DEFAULT_MODEL_PATH = "online_policy_ml/artifacts/models/mlp_v1_p1s1.pt"
DEFAULT_LOOKAHEAD_P = 1
DEFAULT_SELECT_S = 1

# Cinta receding-horizon (p=3, s=2).
CINTA_MODEL_PATH = "online_policy_ml/artifacts/models/mlp_v1_p3s2.pt"
CINTA_LOOKAHEAD_P = 3
CINTA_SELECT_S = 2

# Linear sin torch, mismo régimen p=1 s=1.
LINEAR_MODEL_PATH = "online_policy_ml/artifacts/models/linear_v1.json"

# Placeholder de smoke (NO es el modelo industrial).
PLACEHOLDER_LINEAR_PATH = "examples/online_policy_linear_v1.json"

# ``examples/5_bed-bpp.json``: holdout de producto. Nunca train/tune.
PRODUCT_HOLDOUT_ORDER_IDS = frozenset(
    {
        "00100001",
        "00100002",
        "00100003",
        "00100004",
        "00100408",
    }
)


def default_learned_parameters() -> dict[str, Any]:
    """Defaults de API / web-demo para el execute online aprendido."""
    return {
        "sort_strategy": "input_order",
        "lookahead_p": DEFAULT_LOOKAHEAD_P,
        "select_s": DEFAULT_SELECT_S,
        "selection": "best_fit",
        "model_path": DEFAULT_MODEL_PATH,
    }


def cinta_learned_parameters() -> dict[str, Any]:
    """Régimen cinta (receding-horizon) promocionado en fase 5."""
    return {
        "sort_strategy": "input_order",
        "lookahead_p": CINTA_LOOKAHEAD_P,
        "select_s": CINTA_SELECT_S,
        "selection": "best_fit",
        "model_path": CINTA_MODEL_PATH,
    }
