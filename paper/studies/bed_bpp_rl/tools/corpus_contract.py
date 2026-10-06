"""Contrato validable del corpus BED-BPP-RL (R02/R02A)."""

from __future__ import annotations

import math
from typing import Any

AGENT_FIELDS = (
    "observation",
    "observation_next",
    "action",
    "action_mask",
    "action_mask_next",
    "reward",
    "terminated",
    "truncated",
)

AUDIT_FIELDS = (
    "episode_id",
    "step_index",
    "order_id",
    "target_id",
    "environment_version",
    "engine_commit",
    "behavior_policy",
    "behavior_seed",
    "rule_proposals",
    "chosen_geometry",
    "end_reason",
    "hashes",
    "units",
    "notes",
)

# Campos expresamente permitidos en el callback de política (además de obs/máscara).
POLICY_PUBLIC_FIELDS: tuple[str, ...] = ()

FORBIDDEN_AGENT = (
    "future_item_dimensions",
    "remaining_count",
    "q_hat",
    "teacher_labels",
    "suffix_item_ids",
    "behavior_log_probs",
)

RULE_NAMES_EXPECTED = (
    "greedy_best_fit",
    "lowest_top",
    "least_height_increase",
)

OBS_DIM = 36
N_ACTIONS = 3

UNITS = {
    "length": "mm",
    "volume": "mm3",
    "weight": "kg",
    "time": "s",
    "reward": "dimensionless_volume_fraction",
}


def _finite_vector(values: Any, *, dim: int, name: str) -> list[float]:
    if not isinstance(values, (list, tuple)) or len(values) != dim:
        raise ValueError(f"{name}: se esperaban {dim} floats")
    out: list[float] = []
    for index, raw in enumerate(values):
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{name}[{index}] no numérico")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"{name}[{index}] no finito")
        out.append(number)
    return out


def _bool_mask(values: Any, *, name: str) -> list[bool]:
    if not isinstance(values, (list, tuple)) or len(values) != N_ACTIONS:
        raise ValueError(f"{name}: máscara de {N_ACTIONS} bool")
    out: list[bool] = []
    for raw in values:
        if type(raw) is not bool:
            raise ValueError(f"{name}: solo bool estrictos (no int)")
        out.append(raw)
    return out


def validate_transition(record: dict[str, Any]) -> dict[str, Any]:
    """Valida una transición. Rechaza tipos incorrectos; no repara inconsistencias."""

    if not isinstance(record, dict):
        raise ValueError("la transición debe ser un objeto")
    for key in FORBIDDEN_AGENT:
        if key in record:
            raise ValueError(f"campo prohibido en transición: {key}")

    obs = _finite_vector(record.get("observation"), dim=OBS_DIM, name="observation")
    obs_next = _finite_vector(
        record.get("observation_next"), dim=OBS_DIM, name="observation_next"
    )
    mask = _bool_mask(record.get("action_mask"), name="action_mask")
    mask_next = _bool_mask(record.get("action_mask_next"), name="action_mask_next")
    action = record.get("action")
    if type(action) is not int or action not in (0, 1, 2):
        raise ValueError("action debe ser int estricto en {0,1,2}")
    if mask[action] is not True:
        raise ValueError("action incompatible con action_mask")
    reward = record.get("reward")
    if isinstance(reward, bool) or not isinstance(reward, (int, float)):
        raise ValueError("reward no numérico")
    reward_f = float(reward)
    if not math.isfinite(reward_f):
        raise ValueError("reward no finito")
    terminated = record.get("terminated")
    truncated = record.get("truncated")
    if type(terminated) is not bool or type(truncated) is not bool:
        raise ValueError("terminated/truncated deben ser bool estrictos")
    if terminated and truncated:
        raise ValueError("terminated y truncated son mutuamente excluyentes")
    episode_id = record.get("episode_id")
    if not isinstance(episode_id, str) or not episode_id:
        raise ValueError("episode_id inválido")
    step_index = record.get("step_index")
    if type(step_index) is not int or step_index < 0:
        raise ValueError("step_index inválido")

    return {
        "observation": obs,
        "observation_next": obs_next,
        "action": action,
        "action_mask": mask,
        "action_mask_next": mask_next,
        "reward": reward_f,
        "terminated": terminated,
        "truncated": truncated,
        "episode_id": episode_id,
        "step_index": step_index,
        "order_id": record.get("order_id"),
        "target_id": record.get("target_id"),
        "environment_version": record.get("environment_version"),
        "engine_commit": record.get("engine_commit"),
        "behavior_policy": record.get("behavior_policy"),
        "behavior_seed": record.get("behavior_seed"),
        "rule_proposals": record.get("rule_proposals"),
        "chosen_geometry": record.get("chosen_geometry"),
        "end_reason": record.get("end_reason"),
        "hashes": record.get("hashes") or {},
        "units": record.get("units") or dict(UNITS),
        "notes": record.get("notes") or [],
        "off_policy_importance_supported": False,
        "physical_stability_verified": None,
    }


def agent_view(record: dict[str, Any]) -> dict[str, Any]:
    validated = validate_transition(record)
    return {key: validated[key] for key in AGENT_FIELDS}


def policy_public_view(_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Vista mínima para el callback de comportamiento (sin auditoría)."""

    del _info
    return {key: None for key in POLICY_PUBLIC_FIELDS}


def schema_document() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "kind": "bed_bpp_rl_corpus_contract_r02a",
        "agent_fields": list(AGENT_FIELDS),
        "audit_fields": list(AUDIT_FIELDS),
        "policy_public_fields": list(POLICY_PUBLIC_FIELDS),
        "forbidden_in_agent_channels": list(FORBIDDEN_AGENT),
        "obs_dim": OBS_DIM,
        "n_actions": N_ACTIONS,
        "units": dict(UNITS),
        "off_policy_importance_supported": False,
        "note": (
            "R02A: validación estructural común; manifiesto portable con SHA256; "
            "sin behavior_log_probs; sin off-policy por importancia."
        ),
    }
