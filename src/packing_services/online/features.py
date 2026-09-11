"""Vector de estado v1 para puntuar candidatas legales (entrenamiento = inferencia).

Un checkpoint debe declarar ``feature_version=1`` y un vector del mismo
``FEATURE_DIM``. El modelo solo puntúa opciones ya legales; no propone poses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from collections.abc import Sequence

from ..domain.models import Item
from .types import StepOption

if TYPE_CHECKING:
    from .session import ExtremePointOnlineSession

PREVIEW_SLOTS = 3

FEATURE_NAMES: tuple[str, ...] = (
    "item_l_n",
    "item_w_n",
    "item_h_n",
    "item_vol_n",
    "item_weight_n",
    "item_can_rotate",
    "pos_x_n",
    "pos_y_n",
    "pos_z_n",
    "ori_l_n",
    "ori_w_n",
    "ori_h_n",
    "support_ratio",
    "bin_index_n",
    "rank_0",
    "rank_1",
    "rank_2",
    "rank_3",
    "n_packed_n",
    "loaded_weight_n",
    "used_height_n",
    "remaining_n",
    "buffer_index_n",
    "preview_0_l_n",
    "preview_0_w_n",
    "preview_0_h_n",
    "preview_0_vol_n",
    "preview_1_l_n",
    "preview_1_w_n",
    "preview_1_h_n",
    "preview_1_vol_n",
    "preview_2_l_n",
    "preview_2_w_n",
    "preview_2_h_n",
    "preview_2_vol_n",
)

FEATURE_DIM = len(FEATURE_NAMES)
FEATURE_VERSION = 1


def _safe_div(num: float, den: float) -> float:
    if abs(den) < 1e-9:
        return 0.0
    return float(num) / float(den)


def encode_option(
    option: StepOption,
    *,
    session: ExtremePointOnlineSession,
    preview: Sequence[Item],
    remaining_count: int,
) -> list[float]:
    """Codifica una opción legal. Longitud fija ``FEATURE_DIM``."""

    item = option.item
    cand = option.candidate
    state = session.states[cand.bin_index]
    c = state.container
    L, W, H = c.length, c.width, c.height
    vol_c = max(c.volume, 1e-9)
    max_w = c.max_weight if c.max_weight not in (None, 0) else 1.0

    used_height = 0.0
    for box in state.placed:
        used_height = max(used_height, box.max_corner[2])

    ranks = [float(v) for v in cand.rank_key[:4]]
    while len(ranks) < 4:
        ranks.append(0.0)

    others = [it for it in preview if it.id != item.id][:PREVIEW_SLOTS]
    preview_feats: list[float] = []
    for slot in range(PREVIEW_SLOTS):
        if slot < len(others):
            nxt = others[slot]
            preview_feats.extend(
                [
                    _safe_div(nxt.length, L),
                    _safe_div(nxt.width, W),
                    _safe_div(nxt.height, H),
                    _safe_div(nxt.volume, vol_c),
                ]
            )
        else:
            preview_feats.extend([0.0, 0.0, 0.0, 0.0])

    n_bins = max(len(session.states), 1)
    vector = [
        _safe_div(item.length, L),
        _safe_div(item.width, W),
        _safe_div(item.height, H),
        _safe_div(item.volume, vol_c),
        _safe_div(item.weight, max_w),
        1.0 if item.allow_rotation else 0.0,
        _safe_div(cand.position.x, L),
        _safe_div(cand.position.y, W),
        _safe_div(cand.position.z, H),
        _safe_div(cand.dimensions.length, L),
        _safe_div(cand.dimensions.width, W),
        _safe_div(cand.dimensions.height, H),
        float(cand.support_ratio),
        _safe_div(cand.bin_index, n_bins),
        ranks[0],
        ranks[1],
        ranks[2],
        ranks[3],
        min(len(session.packed) / 50.0, 1.0),
        _safe_div(state.loaded_weight, max_w),
        _safe_div(used_height, H),
        min(max(remaining_count, 0) / 50.0, 1.0),
        min(option.buffer_index / 5.0, 1.0),
        *preview_feats,
    ]
    if len(vector) != FEATURE_DIM:
        raise RuntimeError(
            f"encode_option produjo {len(vector)} features; se esperaban {FEATURE_DIM}"
        )
    return vector
