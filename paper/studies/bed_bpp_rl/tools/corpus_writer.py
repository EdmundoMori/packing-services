"""Escritura atómica y manifiesto portable confirmado (R02A).

Modelo de escritura: un único escritor del manifiesto por corpus (bloqueo
exclusivo por fichero ``.writer.lock``). No hay fusión concurrente: productores
paralelos deben serializarse o coordinar un único escritor. La escritura
garantiza ``fsync`` del payload y ``os.replace`` atómico del episodio y del
manifiesto; no promete durabilidad absoluta ante caída de host a mitad de la
secuencia (p. ej. episodio escrito y crash antes del manifiesto → el episodio
queda huérfano y no cuenta como confirmado).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from episode_validation import validate_episode_document


class CorpusWriteError(RuntimeError):
    pass


MANIFEST_NAME = "manifest.json"
LOCK_NAME = ".writer.lock"


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _atomic_write_bytes(path, text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_tmp_name(name: str) -> bool:
    return name.endswith(".tmp") or ".tmp." in name or name.startswith(".")


class CorpusStore:
    """Raíz de corpus portable con manifiesto relativo + SHA256."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.manifest_path = self.root / MANIFEST_NAME
        self.lock_path = self.root / LOCK_NAME

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self) -> None:
        self.ensure()
        deadline = time.monotonic() + 30.0
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f"pid={os.getpid()}\n")
                return
            except FileExistsError:
                if time.monotonic() > deadline:
                    raise CorpusWriteError(
                        "no se pudo adquirir .writer.lock (modelo single-writer)"
                    )
                time.sleep(0.05)

    def _release_lock(self) -> None:
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {
                "schema_version": 2,
                "kind": "bed_bpp_rl_corpus_manifest_r02a",
                "writer_model": "single_writer_exclusive_lock",
                "durability_note": (
                    "fsync+atomic replace del episodio y del manifiesto; "
                    "no durabilidad absoluta ante crash de host; "
                    "solo archivos listados y con SHA256 coincidente son confirmados"
                ),
                "confirmed_files": [],
            }
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def resolve_relpath(self, relpath: str) -> Path:
        if not isinstance(relpath, str) or not relpath or relpath.startswith("/"):
            raise CorpusWriteError("relpath debe ser relativo no vacío")
        if ".." in Path(relpath).parts or _is_tmp_name(Path(relpath).name):
            raise CorpusWriteError(f"relpath ilegal: {relpath}")
        path = (self.root / relpath).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise CorpusWriteError("ruta fuera del corpus") from exc
        return path

    def publish_episode(self, relpath: str, episode_doc: dict[str, Any]) -> dict[str, Any]:
        validated = validate_episode_document(episode_doc)
        path = self.resolve_relpath(relpath)
        self._acquire_lock()
        try:
            if path.exists():
                raise CorpusWriteError(f"clave duplicada: {relpath}")
            manifest = self._load_manifest()
            existing = {row["relpath"] for row in manifest.get("confirmed_files", [])}
            if relpath in existing:
                raise CorpusWriteError(f"episodio duplicado en manifiesto: {relpath}")
            _atomic_write_json(path, validated)
            entry = {
                "relpath": relpath,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            manifest.setdefault("confirmed_files", []).append(entry)
            manifest["schema_version"] = 2
            manifest["kind"] = "bed_bpp_rl_corpus_manifest_r02a"
            manifest["writer_model"] = "single_writer_exclusive_lock"
            _atomic_write_json(self.manifest_path, manifest)
            return entry
        finally:
            self._release_lock()

    def confirmed_entry(self, relpath: str) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        manifest = self._load_manifest()
        for row in manifest.get("confirmed_files", []):
            if row.get("relpath") == relpath:
                return row
        return None


class EpisodeRecorder:
    """Acumula transiciones en memoria y publica el episodio de una vez."""

    def __init__(
        self,
        *,
        episode_id: str,
        order_id: str,
        target_id: str,
        environment_version: str,
        engine_commit: str,
        behavior_policy: str,
        behavior_seed: int | None,
        hashes: dict[str, Any] | None = None,
    ) -> None:
        self.episode_id = episode_id
        self.meta = {
            "order_id": order_id,
            "target_id": target_id,
            "environment_version": environment_version,
            "engine_commit": engine_commit,
            "behavior_policy": behavior_policy,
            "behavior_seed": behavior_seed,
            "hashes": hashes or {},
        }
        self._rows: list[dict[str, Any]] = []
        self._closed = False
        self._published = False
        self._artifacts: dict[str, Any] | None = None

    def set_artifacts(self, artifacts: dict[str, Any]) -> None:
        self._artifacts = artifacts

    def add_step(
        self,
        *,
        observation: list[float],
        observation_next: list[float],
        action: int,
        action_mask: list[bool],
        action_mask_next: list[bool],
        reward: float,
        rule_proposals: Any,
        chosen_geometry: Any,
    ) -> None:
        if self._closed or self._published:
            raise CorpusWriteError("episodio cerrado o ya publicado")
        if type(action) is not int:
            raise CorpusWriteError("action debe ser int estricto al registrar")
        self._rows.append(
            {
                "observation": list(observation),
                "observation_next": list(observation_next),
                "action": action,
                "action_mask": list(action_mask),
                "action_mask_next": list(action_mask_next),
                "reward": float(reward),
                "terminated": False,
                "truncated": False,
                "episode_id": self.episode_id,
                "step_index": len(self._rows),
                "rule_proposals": rule_proposals,
                "chosen_geometry": chosen_geometry,
                "end_reason": None,
                **self.meta,
            }
        )

    def close(
        self,
        *,
        terminated: bool,
        truncated: bool,
        end_reason: str | None,
        summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._closed:
            raise CorpusWriteError("close repetido")
        if type(terminated) is not bool or type(truncated) is not bool:
            raise CorpusWriteError("terminated/truncated deben ser bool estrictos")
        if terminated and truncated:
            raise CorpusWriteError("terminated y truncated excluyentes")
        self._closed = True
        if self._rows:
            self._rows[-1]["terminated"] = terminated
            self._rows[-1]["truncated"] = truncated
            self._rows[-1]["end_reason"] = end_reason
        document = {
            "schema_version": 2,
            "kind": "bed_bpp_rl_episode_r02a",
            "episode_id": self.episode_id,
            "n_transitions": len(self._rows),
            "terminated": terminated,
            "truncated": truncated,
            "end_reason": end_reason,
            "summary": summary or {},
            "transitions": list(self._rows),
            "meta": dict(self.meta),
            "artifacts": self._artifacts,
            "physical_stability_verified": None,
        }
        return validate_episode_document(document)

    def publish(self, store: CorpusStore, relpath: str, episode_doc: dict[str, Any]) -> None:
        if self._published:
            raise CorpusWriteError("ya publicado")
        store.publish_episode(relpath, episode_doc)
        self._published = True


# Compatibilidad R02: helpers que delegan en CorpusStore.
def is_confirmed_episode(path: Path, manifest_path: Path) -> bool:
    """Compatibilidad limitada: preferir CorpusStore + relpath."""

    if not path.is_file() or _is_tmp_name(path.name):
        return False
    root = manifest_path.parent.resolve()
    store = CorpusStore(root)
    try:
        relpath = str(path.resolve().relative_to(root))
    except ValueError:
        return False
    entry = store.confirmed_entry(relpath)
    if entry is None:
        return False
    if entry.get("size_bytes") != path.stat().st_size:
        return False
    return entry.get("sha256") == _sha256_file(path)
