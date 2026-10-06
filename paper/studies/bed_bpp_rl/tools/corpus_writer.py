"""Escritura atómica de episodios y manifiesto confirmado (R02)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from corpus_contract import validate_transition


class CorpusWriteError(RuntimeError):
    pass


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


class EpisodeRecorder:
    """Acumula transiciones en memoria y publica el episodio de una vez.

    No reescribe transiciones ya publicadas: el flag truncated se asigna al
    cerrar, antes del único write atómico del episodio.
    """

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
        self._rows.append(
            {
                "observation": list(observation),
                "observation_next": list(observation_next),
                "action": int(action),
                "action_mask": list(action_mask),
                "action_mask_next": list(action_mask_next),
                "reward": float(reward),
                "terminated": False,
                "truncated": False,
                "episode_id": self.episode_id,
                "step_index": len(self._rows),
                "rule_proposals": rule_proposals,
                "chosen_geometry": chosen_geometry,
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
        if terminated and truncated:
            raise CorpusWriteError("terminated y truncated excluyentes")
        self._closed = True
        if self._rows:
            self._rows[-1]["terminated"] = bool(terminated)
            self._rows[-1]["truncated"] = bool(truncated)
            self._rows[-1]["end_reason"] = end_reason
        validated = [validate_transition(row) for row in self._rows]
        return {
            "schema_version": 1,
            "kind": "bed_bpp_rl_episode_r02",
            "episode_id": self.episode_id,
            "n_transitions": len(validated),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "end_reason": end_reason,
            "summary": summary or {},
            "transitions": validated,
            "meta": dict(self.meta),
            "physical_stability_verified": None,
        }

    def publish(self, path: Path, episode_doc: dict[str, Any], *, manifest_path: Path) -> None:
        if self._published:
            raise CorpusWriteError("ya publicado")
        if path.exists():
            raise CorpusWriteError(f"clave duplicada: {path}")
        _atomic_write_json(path, episode_doc)
        self._published = True
        _update_manifest(manifest_path, path)


def _update_manifest(manifest_path: Path, episode_path: Path) -> None:
    manifest: dict[str, Any]
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "schema_version": 1,
            "kind": "bed_bpp_rl_corpus_manifest_r02",
            "confirmed_episodes": [],
        }
    rel = str(episode_path)
    if rel in manifest["confirmed_episodes"]:
        raise CorpusWriteError(f"episodio duplicado en manifiesto: {rel}")
    # Solo contar ficheros confirmados existentes y no .tmp
    if episode_path.suffix == ".tmp" or ".tmp." in episode_path.name:
        raise CorpusWriteError("archivo temporal no es experiencia válida")
    if not episode_path.is_file():
        raise CorpusWriteError("el episodio no existe tras la escritura")
    manifest["confirmed_episodes"].append(rel)
    _atomic_write_json(manifest_path, manifest)


def is_confirmed_episode(path: Path, manifest_path: Path) -> bool:
    if not path.is_file() or path.suffix == ".tmp" or ".tmp" in path.name:
        return False
    if not manifest_path.is_file():
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return str(path) in manifest.get("confirmed_episodes", [])
