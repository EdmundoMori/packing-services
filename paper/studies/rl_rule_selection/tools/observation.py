"""Observación del estado presente, del ítem actual y de las tres propuestas.

No incluye el sufijo, identificadores ni la cantidad de ítems restantes.
"""

from __future__ import annotations

from typing import Any

from rules import RULE_NAMES

_ITEM_NAMES = (
    "item_l_n",
    "item_w_n",
    "item_h_n",
    "item_vol_n",
    "item_weight_n",
    "item_can_rotate",
)
_STATE_NAMES = (
    "used_height_n",
    "n_packed_n",
    "loaded_weight_n",
)
_PROPOSAL_NAMES = (
    "pos_x_n",
    "pos_y_n",
    "pos_z_n",
    "ori_l_n",
    "ori_w_n",
    "ori_h_n",
    "support_ratio",
    "top_z_n",
    "height_increase_n",
)
FEATURE_NAMES = (
    *_ITEM_NAMES,
    *_STATE_NAMES,
    *[f"{rule}_{name}" for rule in RULE_NAMES for name in _PROPOSAL_NAMES],
)
OBS_DIM = len(FEATURE_NAMES)
PACKED_SCALE = 1000.0
WEIGHT_SCALE_KG = 1000.0


def _ratio(value: float, scale: float) -> float:
    if scale <= 0:
        raise ValueError("la escala del contenedor no es positiva")
    return float(value) / float(scale)


def encode_observation(
    *,
    container: Any,
    item: Any | None,
    session: Any,
    proposals: list[dict[str, Any]],
    skyline: float,
    orientations: list[Any],
) -> list[float]:
    length = float(container.dimensions.length)
    width = float(container.dimensions.width)
    height = float(container.dimensions.height)
    container_volume = length * width * height
    values: list[float] = []
    if item is None:
        values.extend([0.0] * len(_ITEM_NAMES))
    else:
        unique = {
            (float(dims.length), float(dims.width), float(dims.height))
            for dims in orientations
        }
        values.extend(
            [
                _ratio(item.length, length),
                _ratio(item.width, width),
                _ratio(item.height, height),
                _ratio(item.volume, container_volume),
                _ratio(item.weight, WEIGHT_SCALE_KG),
                1.0 if len(unique) > 1 else 0.0,
            ]
        )
    loaded = sum(float(packed.weight) for packed in session.packed)
    values.extend(
        [
            _ratio(skyline, height),
            len(session.packed) / PACKED_SCALE,
            _ratio(loaded, WEIGHT_SCALE_KG),
        ]
    )
    by_action = {row["action"]: row for row in proposals}
    for action in range(len(RULE_NAMES)):
        row = by_action.get(action)
        option = None if row is None else row["option"]
        if option is None:
            values.extend([0.0] * len(_PROPOSAL_NAMES))
            continue
        candidate = option.candidate
        top = float(candidate.position.z) + float(candidate.dimensions.height)
        increase = max(float(skyline), top) - float(skyline)
        values.extend(
            [
                _ratio(candidate.position.x, length),
                _ratio(candidate.position.y, width),
                _ratio(candidate.position.z, height),
                _ratio(candidate.dimensions.length, length),
                _ratio(candidate.dimensions.width, width),
                _ratio(candidate.dimensions.height, height),
                float(candidate.support_ratio),
                _ratio(top, height),
                _ratio(increase, height),
            ]
        )
    if len(values) != OBS_DIM:
        raise RuntimeError("la observación no tiene la dimensión fijada")
    return values
