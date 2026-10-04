"""Entradas del actor del piloto. No usa el encoder histórico.

Cada columna sale del contenedor, del estado ya colocado, del ítem actual
o de la candidata que se puntúa. No entra el sufijo, el pedido, el retorno,
la acción Greedy, el número de ítems que faltan ni nada calculado después
de continuar.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

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
    "n_packed_n",
    "loaded_weight_n",
    "used_height_n",
)

FEATURE_DIM = len(FEATURE_NAMES)
PACKED_SCALE = 50.0

FEATURE_FORMULAS: tuple[dict[str, str], ...] = (
    {"name": "item_l_n", "unit": "mm/mm", "formula": "longitud almacenada del ítem actual / longitud del contenedor"},
    {"name": "item_w_n", "unit": "mm/mm", "formula": "anchura almacenada del ítem actual / anchura del contenedor"},
    {"name": "item_h_n", "unit": "mm/mm", "formula": "altura almacenada del ítem actual / altura del contenedor"},
    {"name": "item_vol_n", "unit": "mm^3/mm^3", "formula": "volumen del ítem actual / volumen del contenedor"},
    {"name": "item_weight_n", "unit": "kg/kg", "formula": "peso del ítem actual / peso máximo del contenedor, o / 1 kg si ese máximo no es positivo"},
    {"name": "item_can_rotate", "unit": "0 o 1", "formula": "1 si el ítem actual admite todas las orientaciones; 0 en otro caso"},
    {"name": "pos_x_n", "unit": "mm/mm", "formula": "posición x de la candidata / longitud del contenedor"},
    {"name": "pos_y_n", "unit": "mm/mm", "formula": "posición y de la candidata / anchura del contenedor"},
    {"name": "pos_z_n", "unit": "mm/mm", "formula": "posición z de la candidata / altura del contenedor"},
    {"name": "ori_l_n", "unit": "mm/mm", "formula": "arista orientada de la candidata en x / longitud del contenedor"},
    {"name": "ori_w_n", "unit": "mm/mm", "formula": "arista orientada de la candidata en y / anchura del contenedor"},
    {"name": "ori_h_n", "unit": "mm/mm", "formula": "arista orientada vertical de la candidata / altura del contenedor"},
    {"name": "support_ratio", "unit": "fracción", "formula": "fracción de apoyo que el packer asigna a esta candidata en el estado presente"},
    {"name": "bin_index_n", "unit": "índice/contenedores", "formula": "índice del contenedor / número de contenedores de la sesión"},
    {"name": "n_packed_n", "unit": "conteo/50", "formula": "mínimo entre 1 y el número de ítems ya colocados dividido por 50"},
    {"name": "loaded_weight_n", "unit": "kg/kg", "formula": "peso ya cargado en el contenedor / el mismo denominador de item_weight_n"},
    {"name": "used_height_n", "unit": "mm/mm", "formula": "máxima z ya ocupada por cajas colocadas / altura del contenedor; la candidata puntuada no entra"},
)


def _div(num: float, den: float) -> float:
    if abs(den) < 1e-9:
        return 0.0
    return float(num) / float(den)


def encode_candidate(session: Any, item: Any, candidate: Any) -> list[float]:
    """Vector de 17 columnas. No lee el sufijo ni el resultado de continuar."""

    state = session.states[candidate.bin_index]
    container = state.container
    length = float(container.length)
    width = float(container.width)
    height = float(container.height)
    volume = max(float(container.volume), 1e-9)
    max_weight = container.max_weight if container.max_weight not in (None, 0) else 1.0
    used_height = 0.0
    for box in state.placed:
        used_height = max(used_height, float(box.max_corner[2]))
    n_bins = max(len(session.states), 1)
    vector = [
        _div(item.length, length),
        _div(item.width, width),
        _div(item.height, height),
        _div(item.volume, volume),
        _div(item.weight, max_weight),
        1.0 if item.allow_rotation else 0.0,
        _div(candidate.position.x, length),
        _div(candidate.position.y, width),
        _div(candidate.position.z, height),
        _div(candidate.dimensions.length, length),
        _div(candidate.dimensions.width, width),
        _div(candidate.dimensions.height, height),
        float(candidate.support_ratio),
        _div(candidate.bin_index, n_bins),
        min(len(session.packed) / PACKED_SCALE, 1.0),
        _div(state.loaded_weight, max_weight),
        _div(used_height, height),
    ]
    if len(vector) != FEATURE_DIM:
        raise RuntimeError(f"el contrato produjo {len(vector)} columnas")
    return vector


def feature_sha256(vector: list[float]) -> str:
    raw = json.dumps(vector, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
