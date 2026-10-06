"""Rollout sintético → documento de episodio validable (R02A)."""

from __future__ import annotations

from typing import Any, Callable

from corpus_contract import policy_public_view
from corpus_writer import CorpusStore, EpisodeRecorder
from environment import ENVIRONMENT_VERSION, ENGINE_REQUIRED_COMMIT, BedBppRlEnv

# Callback: observación, máscara y campos públicos expresamente permitidos.
Policy = Callable[[list[float], list[bool], dict[str, Any]], int]


def fixed_action(action: int) -> Policy:
    if type(action) is not int:
        raise TypeError("fixed_action exige int estricto")

    def _policy(_obs: list[float], _mask: list[bool], _public: dict[str, Any]) -> int:
        return action

    return _policy


def _chosen_geometry(audit: dict[str, Any], action: int) -> Any:
    proposals = audit.get("proposals") or []
    if 0 <= action < len(proposals):
        return proposals[action].get("geometry")
    return None


def audit_channel(info: dict[str, Any]) -> dict[str, Any]:
    """Ruta separada de auditoría para el recorder (no para la política)."""

    return {
        "proposals": info.get("proposals"),
        "decision_redundancy": info.get("decision_redundancy"),
        "redundancy": info.get("redundancy"),
        "end_reason": info.get("end_reason"),
        "environment_version": info.get("environment_version"),
        "physical_stability_verified": info.get("physical_stability_verified"),
    }


def build_episode_artifacts(env: BedBppRlEnv, problem: Any) -> dict[str, Any]:
    """Snapshot + placements persistibles para verificación sin env vivo."""

    container = problem.containers[0]
    dims = container.dimensions
    constraints = problem.constraints
    input_items = [
        {
            "id": str(item.id),
            "length": float(item.length),
            "width": float(item.width),
            "height": float(item.height),
            "weight": float(item.weight),
            "allowed_orientations": str(
                getattr(item, "allowed_orientations", "all") or "all"
            ),
            "sequence_index": index,
        }
        for index, item in enumerate(problem.items)
    ]
    placements: list[dict[str, Any]] = []
    if env.session is not None:
        for packed in env.session.packed:
            placements.append(
                {
                    "item_id": str(packed.item_id),
                    "container_id": str(packed.container_id),
                    "x": float(packed.position.x),
                    "y": float(packed.position.y),
                    "z": float(packed.position.z),
                    "l": float(packed.orientation.length),
                    "w": float(packed.orientation.width),
                    "h": float(packed.orientation.height),
                }
            )
    unpacked = [
        {"item_id": str(row.item_id), "reason": str(row.reason)}
        for row in getattr(env, "_unpacked", [])
    ]
    return {
        "bin_lwh_mm": [float(dims.length), float(dims.width), float(dims.height)],
        "container_id": str(container.id),
        "allow_rotation": bool(constraints.allow_rotation),
        "input_items": input_items,
        "placements": placements,
        "unpacked": unpacked,
        "environment_version": ENVIRONMENT_VERSION,
        "engine_commit": ENGINE_REQUIRED_COMMIT,
    }


def run_and_record(
    problem: Any,
    *,
    episode_id: str,
    order_id: str,
    target_id: str,
    behavior_policy: str,
    behavior_seed: int | None,
    policy: Policy | None = None,
    decision_budget: int | None = None,
    hashes: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], BedBppRlEnv, EpisodeRecorder]:
    """Ejecuta un episodio; la política no recibe el info de auditoría completo."""

    choose = policy or fixed_action(0)
    env = BedBppRlEnv()
    recorder = EpisodeRecorder(
        episode_id=episode_id,
        order_id=order_id,
        target_id=target_id,
        environment_version=ENVIRONMENT_VERSION,
        engine_commit=ENGINE_REQUIRED_COMMIT,
        behavior_policy=behavior_policy,
        behavior_seed=behavior_seed,
        hashes=hashes,
    )
    observation, info = env.reset(problem, decision_budget=decision_budget)
    if info.get("terminated") or info.get("truncated"):
        recorder.set_artifacts(build_episode_artifacts(env, problem))
        document = recorder.close(
            terminated=bool(info.get("terminated")),
            truncated=bool(info.get("truncated")),
            end_reason=info.get("end_reason") or env.summary.end_reason,
            summary=env.summary.as_dict(),
        )
        return document, env, recorder

    while True:
        mask = list(info["action_mask"])
        public = policy_public_view(info)
        audit = audit_channel(info)
        action = choose(observation, mask, public)
        if type(action) is not int:
            raise TypeError("la política debe devolver int estricto")
        geometry = _chosen_geometry(audit, action)
        observation_next, reward, terminated, truncated, info_next = env.step(action)
        if info_next.get("placed"):
            recorder.add_step(
                observation=observation,
                observation_next=observation_next,
                action=action,
                action_mask=mask,
                action_mask_next=list(info_next["action_mask"]),
                reward=reward,
                rule_proposals=audit.get("proposals"),
                chosen_geometry=geometry,
            )
        observation = observation_next
        info = info_next
        if terminated or truncated:
            break

    recorder.set_artifacts(build_episode_artifacts(env, problem))
    document = recorder.close(
        terminated=bool(env.summary.terminated),
        truncated=bool(env.summary.truncated),
        end_reason=env.summary.end_reason,
        summary=env.summary.as_dict(),
    )
    return document, env, recorder


def publish_episode(
    recorder: EpisodeRecorder,
    document: dict[str, Any],
    *,
    store: CorpusStore | None = None,
    relpath: str | None = None,
    path: Any = None,
    manifest_path: Any = None,
) -> None:
    """Publica en CorpusStore (preferido) o compat path/manifest R02."""

    if store is not None:
        if not relpath:
            raise ValueError("relpath obligatorio con CorpusStore")
        recorder.publish(store, relpath, document)
        return
    if path is None or manifest_path is None:
        raise ValueError("store+relpath o path+manifest_path")
    from pathlib import Path

    root = Path(manifest_path).parent
    corpus = CorpusStore(root)
    rel = str(Path(path).resolve().relative_to(root.resolve()))
    recorder.publish(corpus, rel, document)
