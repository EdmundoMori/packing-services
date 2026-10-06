"""Cargador de entrenamiento: solo campos agent-visible."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from corpus_contract import AGENT_FIELDS, agent_view, validate_transition
from corpus_writer import is_confirmed_episode


def load_episode(path: Path, *, manifest_path: Path) -> dict[str, Any]:
    if not is_confirmed_episode(path, manifest_path):
        raise ValueError(f"episodio no confirmado o incompleto: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    for row in document.get("transitions", []):
        validate_transition(row)
    return document


def iter_agent_transitions(
    path: Path, *, manifest_path: Path
) -> Iterator[dict[str, Any]]:
    document = load_episode(path, manifest_path=manifest_path)
    for row in document.get("transitions", []):
        view = agent_view(row)
        # Garantiza ausencia de auditoría
        for key in list(view):
            if key not in AGENT_FIELDS:
                raise RuntimeError(f"fuga de auditoría en loader: {key}")
        yield view


def agent_batch(path: Path, *, manifest_path: Path) -> list[dict[str, Any]]:
    return list(iter_agent_transitions(path, manifest_path=manifest_path))
