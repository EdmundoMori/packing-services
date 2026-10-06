"""Rollout sintético → documento de episodio validable (R02)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from corpus_writer import EpisodeRecorder
from environment import ENVIRONMENT_VERSION, ENGINE_REQUIRED_COMMIT, BedBppRlEnv

Policy = Callable[[list[float], list[bool], dict[str, Any]], int]


def fixed_action(action: int) -> Policy:
    def _policy(_obs: list[float], _mask: list[bool], _info: dict[str, Any]) -> int:
        return action

    return _policy


def _chosen_geometry(info_before: dict[str, Any], action: int) -> Any:
    proposals = info_before.get("proposals") or []
    if 0 <= action < len(proposals):
        return proposals[action].get("geometry")
    return None


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
    """Ejecuta un episodio y cierra el recorder de forma consistente.

    Truncación se fija solo en ``close`` (última transición), sin reescritura
    retrospectiva de ficheros ya publicados.
    """

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
        document = recorder.close(
            terminated=bool(info.get("terminated")),
            truncated=bool(info.get("truncated")),
            end_reason=info.get("end_reason") or env.summary.end_reason,
            summary=env.summary.as_dict(),
        )
        return document, env, recorder

    while True:
        mask = list(info["action_mask"])
        action = choose(observation, mask, info)
        geometry = _chosen_geometry(info, action)
        observation_next, reward, terminated, truncated, info_next = env.step(action)
        if info_next.get("placed"):
            recorder.add_step(
                observation=observation,
                observation_next=observation_next,
                action=action,
                action_mask=mask,
                action_mask_next=list(info_next["action_mask"]),
                reward=reward,
                rule_proposals=info.get("proposals"),
                chosen_geometry=geometry,
            )
        observation = observation_next
        info = info_next
        if terminated or truncated:
            break

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
    path: Path,
    manifest_path: Path,
) -> None:
    recorder.publish(path, document, manifest_path=manifest_path)
