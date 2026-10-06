"""Cargador portable: comprueba SHA256 y solo campos agent-visible."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

from corpus_contract import AGENT_FIELDS, agent_view
from corpus_writer import CorpusStore, CorpusWriteError
from episode_validation import EpisodeValidationError, validate_episode_document


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_episode_from_store(store: CorpusStore, relpath: str) -> dict[str, Any]:
    """Carga un episodio confirmado verificando integridad del artefacto."""

    entry = store.confirmed_entry(relpath)
    if entry is None:
        raise ValueError(f"episodio no confirmado: {relpath}")
    path = store.resolve_relpath(relpath)
    if not path.is_file():
        raise ValueError(f"archivo ausente: {relpath}")
    size = path.stat().st_size
    if size != entry.get("size_bytes"):
        raise ValueError(f"tamaño modificado tras confirmación: {relpath}")
    digest = _sha256_file(path)
    if digest != entry.get("sha256"):
        raise ValueError(f"SHA256 modificado tras confirmación: {relpath}")
    document = json.loads(path.read_text(encoding="utf-8"))
    return validate_episode_document(document)


def load_episode(path: Path, *, manifest_path: Path) -> dict[str, Any]:
    """Compatibilidad: path absoluto/relativo bajo la raíz del manifiesto."""

    root = manifest_path.parent.resolve()
    store = CorpusStore(root)
    try:
        relpath = str(Path(path).resolve().relative_to(root))
    except ValueError as exc:
        raise ValueError(f"ruta fuera del corpus: {path}") from exc
    return load_episode_from_store(store, relpath)


def iter_agent_transitions_from_store(
    store: CorpusStore, relpath: str
) -> Iterator[dict[str, Any]]:
    document = load_episode_from_store(store, relpath)
    for row in document.get("transitions", []):
        view = agent_view(row)
        for key in view:
            if key not in AGENT_FIELDS:
                raise RuntimeError(f"fuga de auditoría en loader: {key}")
        yield view


def iter_agent_transitions(
    path: Path, *, manifest_path: Path
) -> Iterator[dict[str, Any]]:
    root = manifest_path.parent.resolve()
    store = CorpusStore(root)
    relpath = str(Path(path).resolve().relative_to(root))
    yield from iter_agent_transitions_from_store(store, relpath)


def agent_batch(path: Path, *, manifest_path: Path) -> list[dict[str, Any]]:
    return list(iter_agent_transitions(path, manifest_path=manifest_path))


def agent_batch_from_store(store: CorpusStore, relpath: str) -> list[dict[str, Any]]:
    return list(iter_agent_transitions_from_store(store, relpath))
