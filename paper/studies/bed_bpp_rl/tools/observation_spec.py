"""Especificación de las 36 características de observación (R02).

Reexporta el encoder histórico de rl_rule_selection sin modificarlo.
Documenta nombres, orden, fórmulas, escalas y valores terminales.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_RULE_TOOLS = Path(__file__).resolve().parents[2] / "rl_rule_selection" / "tools"
_PAPER_TOOLS = Path(__file__).resolve().parents[3] / "tools"
for _entry in (str(_PAPER_TOOLS), str(_RULE_TOOLS)):
    if _entry in sys.path:
        sys.path.remove(_entry)
    sys.path.insert(0, _entry)

from observation import (  # noqa: E402
    FEATURE_NAMES,
    OBS_DIM,
    PACKED_SCALE,
    WEIGHT_SCALE_KG,
    encode_observation,
)
from rules import RULE_NAMES  # noqa: E402

assert OBS_DIM == 36
assert len(FEATURE_NAMES) == 36

DTYPE = "float64_python_list_serialized_as_float"

# Fórmulas alineadas con encode_observation (rl_rule_selection), no alteradas.
FEATURE_SPEC: list[dict[str, Any]] = [
    {
        "index": 0,
        "name": "item_l_n",
        "formula": "item.length / container.length",
        "unit": "mm/mm",
        "scale": "container.length",
        "terminal_value": 0.0,
        "meaning": "Longitud almacenada del ítem actual normalizada; 0 si no hay ítem actual.",
    },
    {
        "index": 1,
        "name": "item_w_n",
        "formula": "item.width / container.width",
        "unit": "mm/mm",
        "scale": "container.width",
        "terminal_value": 0.0,
        "meaning": "Anchura almacenada del ítem actual normalizada.",
    },
    {
        "index": 2,
        "name": "item_h_n",
        "formula": "item.height / container.height",
        "unit": "mm/mm",
        "scale": "container.height",
        "terminal_value": 0.0,
        "meaning": "Altura almacenada del ítem actual normalizada.",
    },
    {
        "index": 3,
        "name": "item_vol_n",
        "formula": "item.volume / (L*W*H)",
        "unit": "mm3/mm3",
        "scale": "bin_volume",
        "terminal_value": 0.0,
        "meaning": "Volumen del ítem / volumen del bin.",
    },
    {
        "index": 4,
        "name": "item_weight_n",
        "formula": "item.weight / WEIGHT_SCALE_KG",
        "unit": "kg/kg",
        "scale": WEIGHT_SCALE_KG,
        "terminal_value": 0.0,
        "meaning": "Peso del ítem / 1000 kg (escala fija del encoder histórico).",
    },
    {
        "index": 5,
        "name": "item_can_rotate",
        "formula": "1 if >1 distinct orientations else 0",
        "unit": "{0,1}",
        "scale": None,
        "terminal_value": 0.0,
        "meaning": "Indica si el ítem admite más de una orientación distinta.",
    },
    {
        "index": 6,
        "name": "used_height_n",
        "formula": "skyline / container.height",
        "unit": "mm/mm",
        "scale": "container.height",
        "terminal_value": "skyline/H (estado packed; puede ser >0)",
        "meaning": "Altura máxima ocupada (skyline) / H; en terminal refleja el packing actual.",
    },
    {
        "index": 7,
        "name": "n_packed_n",
        "formula": "len(session.packed) / PACKED_SCALE",
        "unit": "count/count",
        "scale": PACKED_SCALE,
        "terminal_value": "n_packed/1000",
        "meaning": "Número de cajas colocadas / 1000.",
    },
    {
        "index": 8,
        "name": "loaded_weight_n",
        "formula": "sum(packed.weight) / WEIGHT_SCALE_KG",
        "unit": "kg/kg",
        "scale": WEIGHT_SCALE_KG,
        "terminal_value": "loaded/1000",
        "meaning": "Peso acumulado colocado / 1000 kg.",
    },
]

_PROPOSAL = (
    ("pos_x_n", "candidate.x / L", "mm/mm", "FLB x normalizado de la propuesta"),
    ("pos_y_n", "candidate.y / W", "mm/mm", "FLB y normalizado"),
    ("pos_z_n", "candidate.z / H", "mm/mm", "FLB z normalizado"),
    ("ori_l_n", "oriented.length / L", "mm/mm", "Arista orientada en x / L"),
    ("ori_w_n", "oriented.width / W", "mm/mm", "Arista orientada en y / W"),
    ("ori_h_n", "oriented.height / H", "mm/mm", "Arista orientada en z / H"),
    ("support_ratio", "candidate.support_ratio", "fraction", "Soporte asignado por el packer"),
    ("top_z_n", "(z+h) / H", "mm/mm", "Cima de la propuesta / H"),
    ("height_increase_n", "(max(skyline, top)-skyline)/H", "mm/mm", "Incremento de skyline / H"),
)

_idx = 9
for rule in RULE_NAMES:
    for name, formula, unit, meaning in _PROPOSAL:
        FEATURE_SPEC.append(
            {
                "index": _idx,
                "name": f"{rule}_{name}",
                "formula": formula,
                "unit": unit,
                "scale": "see formula",
                "terminal_value": 0.0,
                "meaning": f"{meaning} para la regla {rule}; 0 si no hay propuesta.",
                "rule": rule,
            }
        )
        _idx += 1

assert _idx == 36
assert [row["name"] for row in FEATURE_SPEC] == list(FEATURE_NAMES)

EXCLUDES = (
    "future_item_dimensions",
    "remaining_item_count",
    "suffix_ids",
    "returns_or_q_hat",
    "teacher_labels",
    "item_identifiers_in_observation",
)

LAYERS = {
    "simulator_internal": (
        "remaining item queue, session packed state, mask, constraints, "
        "full legal candidate list, unpacked reasons"
    ),
    "agent_observation": "36-D present summary FEATURE_NAMES; not claimed Markov-sufficient",
    "audit": (
        "order_id, geometries, end_reason, hashes, capture AABB, "
        "physical_stability_verified=null"
    ),
}


def observation_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "bed_bpp_rl_observation_spec_r02",
        "dim": OBS_DIM,
        "dtype": DTYPE,
        "feature_names": list(FEATURE_NAMES),
        "features": FEATURE_SPEC,
        "excludes": list(EXCLUDES),
        "layers": LAYERS,
        "encoder_source": "paper/studies/rl_rule_selection/tools/observation.py",
        "markov_sufficiency_claimed": False,
        "packed_scale": PACKED_SCALE,
        "weight_scale_kg": WEIGHT_SCALE_KG,
        "rules": list(RULE_NAMES),
    }


__all__ = [
    "FEATURE_NAMES",
    "FEATURE_SPEC",
    "OBS_DIM",
    "PACKED_SCALE",
    "WEIGHT_SCALE_KG",
    "RULE_NAMES",
    "encode_observation",
    "observation_manifest",
    "EXCLUDES",
    "LAYERS",
    "DTYPE",
]
