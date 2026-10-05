"""Reutilización exacta del preflight publicado (16 continuaciones).

No altera la evidencia publicada. Si la compatibilidad falla, detiene la etapa.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from labeling_contracts import (
    EXPECTED_PROTOCOL_INTERNAL_DIGEST,
    PREFLIGHT_REUSE_ORDER_IDS,
    PUBLISHED_PREFLIGHT_WALL_SECONDS,
    file_sha256,
)


def _action_key(action: list[Any]) -> tuple[Any, ...]:
    return tuple(action)


class PreflightReuseIndex:
    def __init__(self, preflight_dir: Path, *, protocol: dict[str, Any], study_dir: Path) -> None:
        self.preflight_dir = preflight_dir
        self.protocol = protocol
        self.study_dir = study_dir
        self.verification = json.loads((preflight_dir / "preflight_verification.json").read_text(encoding="utf-8"))
        self._entries: dict[tuple[str, int, tuple[Any, ...]], dict[str, Any]] = {}
        self._state_meta: dict[tuple[str, int], dict[str, Any]] = {}
        self.reused = 0
        self.incompatible_attempts = 0
        self._validate_published()
        self._index_orders()

    def _validate_published(self) -> None:
        if self.verification.get("status") != "completed":
            raise RuntimeError("preflight publicado no completed")
        if int(self.verification.get("continuations_used", -1)) != 16:
            raise RuntimeError("preflight no tiene 16 continuaciones")
        if int(self.verification.get("unknown_returns", -1)) != 0:
            raise RuntimeError("preflight tiene retornos desconocidos")
        if abs(float(self.verification["wall_seconds"]) - PUBLISHED_PREFLIGHT_WALL_SECONDS) > 1e-12:
            raise RuntimeError("wall del preflight incongruente")
        if self.verification.get("protocol_sha256") != EXPECTED_PROTOCOL_INTERNAL_DIGEST:
            raise RuntimeError("protocol_sha256 del preflight incongruente")
        if self.verification.get("protocol_sha256") != self.protocol.get("sha256"):
            raise RuntimeError("preflight y protocolo no comparten digest interno")
        for relative, expected in self.protocol["code_hashes"].items():
            published = self.verification.get("code_hashes", {}).get(relative)
            current = file_sha256(self.study_dir / relative)
            if published != expected or current != expected:
                raise RuntimeError(f"hash de código incompatible para reuso: {relative}")
        found_ids = [row["order_id"] for row in self.verification.get("orders", [])]
        if found_ids != list(PREFLIGHT_REUSE_ORDER_IDS):
            raise RuntimeError(f"pedidos de preflight distintos: {found_ids}")

    def _index_orders(self) -> None:
        for order_id in PREFLIGHT_REUSE_ORDER_IDS:
            result_path = self.preflight_dir / "orders" / order_id / "result.json"
            if not result_path.is_file():
                raise RuntimeError(f"falta result.json de preflight: {order_id}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            for state in result.get("states", []):
                choice = int(state["choice_index"])
                self._state_meta[(order_id, choice)] = {
                    "current_item_id": state["current_item_id"],
                    "support_ids": state["support_ids"],
                    "greedy_key": state["greedy_key"],
                    "checkpoint_remaining_ids": state["checkpoint_remaining_ids"],
                    "support_contract": state["support_contract"],
                    "n_legal": state["n_legal"],
                }
                for index, alt in enumerate(state["alternatives"]):
                    capture_path = (
                        self.preflight_dir
                        / "orders"
                        / order_id
                        / "states"
                        / f"choice_{choice}"
                        / f"alt_{index}_capture.json"
                    )
                    if not capture_path.is_file():
                        raise RuntimeError(f"falta captura publicada: {capture_path}")
                    if alt.get("q_hat") is None or not alt.get("audited"):
                        raise RuntimeError(f"continuación de preflight incompleta: {order_id}/{choice}/{index}")
                    key = (order_id, choice, _action_key(alt["action"]))
                    self._entries[key] = {
                        "order_id": order_id,
                        "choice_index": choice,
                        "alt_index": index,
                        "action": list(alt["action"]),
                        "q_hat": alt["q_hat"],
                        "recomputed_u_geom": alt.get("recomputed_u_geom"),
                        "audited": True,
                        "capture_ok": True,
                        "geometry_valid": alt.get("geometry_valid"),
                        "action_matches_current_item_placement": alt.get("action_matches_current_item_placement"),
                        "audit_failure_types": list(alt.get("audit_failure_types") or []),
                        "capture_path": str(capture_path),
                        "source": "preflight_reused",
                        "reason": None,
                    }
        if len(self._entries) != 16:
            raise RuntimeError(f"índice de reuso tiene {len(self._entries)} entradas, se esperaban 16")

    def compatible_state(self, order_id: str, state: dict[str, Any]) -> bool:
        meta = self._state_meta.get((order_id, int(state["choice_index"])))
        if meta is None:
            return False
        if meta["current_item_id"] != state["current_item_id"]:
            self.incompatible_attempts += 1
            raise RuntimeError(f"current_item_id incompatible en {order_id}/{state['choice_index']}")
        if meta["support_ids"] != state["support_ids"]:
            self.incompatible_attempts += 1
            raise RuntimeError(f"S incompatible en {order_id}/{state['choice_index']}")
        if meta["greedy_key"] != state["greedy_key"]:
            self.incompatible_attempts += 1
            raise RuntimeError(f"greedy_key incompatible en {order_id}/{state['choice_index']}")
        if meta["checkpoint_remaining_ids"] != list(state["checkpoint"]["remaining_ids"]):
            self.incompatible_attempts += 1
            raise RuntimeError(f"sufijo incompatible en {order_id}/{state['choice_index']}")
        if meta["support_contract"] != state["support_contract"]:
            self.incompatible_attempts += 1
            raise RuntimeError(f"contrato S incompatible en {order_id}/{state['choice_index']}")
        return True

    def try_reuse(self, order_id: str, state: dict[str, Any], alternative: dict[str, Any]) -> dict[str, Any] | None:
        if order_id not in PREFLIGHT_REUSE_ORDER_IDS:
            return None
        if (order_id, int(state["choice_index"])) not in self._state_meta:
            return None
        if not self.compatible_state(order_id, state):
            return None
        key = (order_id, int(state["choice_index"]), _action_key(alternative["action"]))
        entry = self._entries.get(key)
        if entry is None:
            self.incompatible_attempts += 1
            raise RuntimeError(
                f"acción de S no está en preflight reutilizable: {order_id}/{state['choice_index']}/{alternative['action']}"
            )
        capture = json.loads(Path(entry["capture_path"]).read_text(encoding="utf-8"))
        self.reused += 1
        return {
            **alternative,
            "q_hat": entry["q_hat"],
            "recomputed_u_geom": entry["recomputed_u_geom"],
            "audited": True,
            "capture_ok": True,
            "geometry_valid": entry["geometry_valid"],
            "action_matches_current_item_placement": entry["action_matches_current_item_placement"],
            "audit_failure_types": list(entry["audit_failure_types"]),
            "capture": capture,
            "source": "preflight_reused",
            "reason": None,
            "continuation_seconds": 0.0,
            "capture_seconds": 0.0,
            "audit_seconds": 0.0,
            "preflight_capture_path": entry["capture_path"],
            "counted_once": True,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "preflight_wall_seconds_accounted_once": PUBLISHED_PREFLIGHT_WALL_SECONDS,
            "preflight_continuations_available": 16,
            "reused_continuations": self.reused,
            "incompatible_attempts": self.incompatible_attempts,
            "preflight_dir": str(self.preflight_dir),
            "orders": list(PREFLIGHT_REUSE_ORDER_IDS),
        }
