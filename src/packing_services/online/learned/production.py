"""Checkpoints de producción para ``drl_policy_3d_bpp``.

Rutas relativas a la raíz del repo. El execute las resuelve con
``resolve_model_path``. No reentrenar aquí: son artefactos ya exportados.
"""

from __future__ import annotations

from typing import Any

# Política aprendida de producción: RL (PPO v1). La imitación quedó en versions/v1.
DEFAULT_MODEL_PATH = "online_policy_ml/artifacts/models/mlp_v1_p1s1_ppo.pt"
DEFAULT_LOOKAHEAD_P = 1
DEFAULT_SELECT_S = 1
IMITATION_MODEL_PATH = "online_policy_ml/artifacts/models/mlp_v1_p1s1.pt"

# Cinta receding-horizon (p=3, s=2).
CINTA_MODEL_PATH = "online_policy_ml/artifacts/models/mlp_v1_p3s2.pt"
CINTA_LOOKAHEAD_P = 3
CINTA_SELECT_S = 2

PPO_MODEL_PATH = DEFAULT_MODEL_PATH
PPO_LOOKAHEAD_P = 1
PPO_SELECT_S = 1

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
    """Defaults de API / web-demo: política aprendida = RL (PPO)."""
    return rl_learned_parameters()


def rl_learned_parameters() -> dict[str, Any]:
    """Preset RL: PPO warm-start del mlp_v1_p1s1. No es un algoritmo nuevo."""
    return {
        "sort_strategy": "input_order",
        "lookahead_p": PPO_LOOKAHEAD_P,
        "select_s": PPO_SELECT_S,
        "selection": "best_fit",
        "policy": "rl",
        "model_path": PPO_MODEL_PATH,
    }


def apply_policy_preset(params: dict[str, Any]) -> dict[str, Any]:
    """Resuelve ``policy=rl`` (única política aprendida expuesta).

    ``imitation`` / ``p2o`` / ``bc`` ya no se ofrecen: el corte está en
    ``online_policy_ml/versions/v1``. Si el cliente envía ``model_path``,
    se respeta.
    """

    from ...utils.errors import InvalidInputError
    from .checkpoint import resolve_model_path

    out = dict(params)
    raw = str(out.get("policy") or "rl").strip().lower()
    if raw in {"imitation", "bc", "p2o"}:
        raise InvalidInputError(
            "parameters.policy=imitation ya no está disponible en el servicio. "
            "Use policy=rl (PPO). El corte P2O está en "
            "online_policy_ml/versions/v1."
        )
    if raw not in {"rl", "ppo"}:
        raise InvalidInputError(
            f"parameters.policy={raw!r} no es válido. Use 'rl'."
        )
    out.setdefault("model_path", PPO_MODEL_PATH)
    out.setdefault("lookahead_p", PPO_LOOKAHEAD_P)
    out.setdefault("select_s", PPO_SELECT_S)
    out["policy"] = "rl"
    try:
        resolve_model_path(out["model_path"])
    except InvalidInputError as exc:
        raise InvalidInputError(
            "policy=rl requiere el checkpoint PPO "
            f"({PPO_MODEL_PATH}). El de v1 está en artifacts/models/; "
            f"entrenos nuevos en versions/v2 ({exc})."
        ) from exc
    return out


def cinta_learned_parameters() -> dict[str, Any]:
    """Régimen cinta (receding-horizon) promocionado en fase 5."""
    return {
        "sort_strategy": "input_order",
        "lookahead_p": CINTA_LOOKAHEAD_P,
        "select_s": CINTA_SELECT_S,
        "selection": "best_fit",
        "model_path": CINTA_MODEL_PATH,
    }
