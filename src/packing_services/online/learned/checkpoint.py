"""Checkpoint de política online (contrato de entrenamiento = inferencia).

Formato ``packing-services-online-policy`` v1:

- ``backend=linear``: JSON con ``weights`` (len = FEATURE_DIM) y ``bias``.
- ``backend=torch`` + ``architecture=mlp_v1``: dict guardado con ``torch.save``
  (``state_dict``, ``hidden_size``, ``feature_version``).

Un ``.pt`` de otro proyecto (PCT, GOPT, etc.) no es válido: hay que exportar
a este contrato tras entrenar con el simulador del repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...utils.errors import InvalidInputError
from ..features import FEATURE_DIM, FEATURE_NAMES, FEATURE_VERSION

CHECKPOINT_FORMAT = "packing-services-online-policy"
CHECKPOINT_VERSION = 1

_REPO_ROOT = Path(__file__).resolve().parents[4]


def resolve_model_path(raw: object) -> Path:
    """Resuelve ``model_path`` (absoluto, cwd o raíz del repo)."""

    if raw is None or str(raw).strip() == "":
        raise InvalidInputError(
            "drl_policy_3d_bpp requiere parameters.model_path con el checkpoint "
            f"({CHECKPOINT_FORMAT} v{CHECKPOINT_VERSION})."
        )
    text = str(raw).strip()
    path = Path(text).expanduser()
    candidates = [path]
    if not path.is_absolute():
        candidates.append(Path.cwd() / path)
        candidates.append(_REPO_ROOT / path)
        candidates.append(_REPO_ROOT / "examples" / path.name)
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()
    raise InvalidInputError(
        f"No se encontró el modelo en {text!r}. "
        "Use una ruta absoluta, o relativa a la raíz del repo / examples/."
    )


def greedy_like_linear_document() -> dict[str, Any]:
    """Checkpoint linear que imita EP best-fit (útil para probar el execute)."""

    weights = [0.0] * FEATURE_DIM
    names = list(FEATURE_NAMES)
    weights[names.index("rank_0")] = -1.0
    weights[names.index("support_ratio")] = 0.25
    return {
        "format": CHECKPOINT_FORMAT,
        "version": CHECKPOINT_VERSION,
        "backend": "linear",
        "architecture": "linear_v1",
        "feature_version": FEATURE_VERSION,
        "feature_dim": FEATURE_DIM,
        "feature_names": names,
        "weights": weights,
        "bias": 0.0,
        "notes": (
            "Placeholder de pipeline. Sustituya por pesos entrenados con el "
            "mismo feature_version. No es un modelo industrial."
        ),
    }


def load_checkpoint_document(path: Path) -> dict[str, Any]:
    """Lee JSON o ``torch.save`` y valida el encabezado del contrato."""

    suffix = path.suffix.lower()
    if suffix in {".pt", ".pth", ".ckpt"}:
        payload = _load_torch_file(path)
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidInputError(
                f"No se pudo leer el checkpoint {path}: {exc}"
            ) from exc
    if not isinstance(payload, dict):
        raise InvalidInputError(
            f"El archivo {path} no es un dict de checkpoint {CHECKPOINT_FORMAT}."
        )
    if payload.get("format") != CHECKPOINT_FORMAT:
        raise InvalidInputError(
            f"{path} no es {CHECKPOINT_FORMAT}. "
            "Los pesos de papers (PCT/GOPT/O3DBP-grid) no se cargan tal cual; "
            "exporte un checkpoint de este contrato tras el entrenamiento."
        )
    if int(payload.get("version", 0)) != CHECKPOINT_VERSION:
        raise InvalidInputError(
            f"version de checkpoint no soportada: {payload.get('version')!r} "
            f"(se espera {CHECKPOINT_VERSION})."
        )
    feat = int(payload.get("feature_version", 0))
    if feat != FEATURE_VERSION:
        raise InvalidInputError(
            f"feature_version={feat} no coincide con el encoder actual "
            f"({FEATURE_VERSION}, dim={FEATURE_DIM})."
        )
    return payload


def _load_torch_file(path: Path) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise InvalidInputError(
            "El checkpoint es PyTorch (.pt) pero torch no está instalado. "
            "pip install 'packing-services[torch]', o use un JSON linear "
            "packing-services-online-policy."
        ) from exc
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    except Exception as exc:
        raise InvalidInputError(
            f"No se pudo cargar {path} con torch.load: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise InvalidInputError(
            f"{path} no contiene un dict {CHECKPOINT_FORMAT} (¿pesos de otro proyecto?)."
        )
    return payload
