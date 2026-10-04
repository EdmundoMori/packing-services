"""Entorno mínimo: reset, step y parada en el primer ítem sin candidata."""

from __future__ import annotations

import time
import weakref
from pathlib import Path
from typing import Any

from compact_study import (
    COMPACT_FLAGS,
    SUFFIX_REASON,
    TERMINAL_REASON,
    prepare_imports,
)
from observation import encode_observation
from rules import current_max_height, propose_rules, redundancy


class RuleSelectionEnv:
    def __init__(self) -> None:
        self.problem: Any = None
        self.session: Any = None
        self._mask: Any = None
        self._constraints: Any = None
        self._remaining: list[Any] = []
        self._unpacked: list[Any] = []
        self._rewards: list[float] = []
        self._decisions: list[dict[str, Any]] = []
        self._terminated = True
        self._bin_volume = 0.0
        self._closed_sessions: list[weakref.ReferenceType] = []
        self._cached: tuple[str, list[Any]] | None = None
        self.candidate_seconds = 0.0
        self.candidate_generations = 0

    def close(self) -> None:
        if self.session is not None:
            self._closed_sessions.append(weakref.ref(self.session))
        self.session = None
        self._mask = None
        self._remaining = []
        self.problem = None
        self._cached = None

    def reset(self, problem: Any) -> tuple[list[float], dict[str, Any]]:
        self.close()
        self._assert_contract(problem)
        prepare_imports()
        from packing_services.algorithms._constructive import order_items
        from packing_services.domain.enums import SortStrategy
        from packing_services.online.mask import ValidatorMask
        from packing_services.online.params import resolve_selection, support_threshold
        from packing_services.online.session import ExtremePointOnlineSession

        self.problem = problem
        self._constraints = problem.constraints
        params = dict(problem.algorithm.parameters)
        container = problem.containers[0]
        dims = container.dimensions
        self._bin_volume = float(dims.length) * float(dims.width) * float(dims.height)
        self.session = ExtremePointOnlineSession(
            problem.containers,
            selection=resolve_selection(params),
        )
        self._mask = ValidatorMask(
            problem,
            min_support_ratio=support_threshold(params, self._constraints.basic_stability),
        )
        self._remaining = order_items(list(problem.items), SortStrategy.INPUT_ORDER)
        self._unpacked = []
        self._rewards = []
        self._decisions = []
        self._terminated = False
        self._cached = None
        self.candidate_seconds = 0.0
        self.candidate_generations = 0
        observation, info = self._view(action=None, reward=0.0, placed=False)
        if not self._legal(self._remaining[0]):
            self._stop_current()
            observation, info = self._view(action=None, reward=0.0, placed=False)
        return observation, info

    def step(self, action: int) -> tuple[list[float], float, bool, dict[str, Any]]:
        if self._terminated:
            raise RuntimeError("el episodio ya terminó")
        if action not in (0, 1, 2):
            raise ValueError("la acción debe ser 0, 1 o 2")
        current = self._remaining[0]
        options = self._legal(current)
        proposals = propose_rules(options, self.session)
        if not options:
            self._stop_current()
            observation, info = self._view(action=action, reward=0.0, placed=False)
            return observation, 0.0, True, info
        chosen = proposals[action]["option"]
        candidate = chosen.candidate
        placed_volume = (
            float(candidate.dimensions.length)
            * float(candidate.dimensions.width)
            * float(candidate.dimensions.height)
        )
        reward = placed_volume / self._bin_volume
        self.session.commit(candidate, chosen.item)
        self._cached = None
        self._rewards.append(reward)
        self._remaining = self._remaining[1:]
        self._decisions.append(
            {
                "action": action,
                "rule": proposals[action]["rule"],
                "redundancy": redundancy(proposals),
                "n_candidates": len(options),
            }
        )
        if not self._remaining:
            self._terminated = True
        observation, info = self._view(action=action, reward=reward, placed=True)
        return observation, reward, self._terminated, info

    def geometric_utilization(self) -> float:
        return sum(self._rewards)

    def solution(self, *, algorithm_name: str, display_name: str, description: str) -> Any:
        prepare_imports()
        from packing_services.algorithms.base import build_solution
        from packing_services.algorithms.online_3d_bpp_heuristic import METADATA

        metadata = METADATA.model_copy(
            update={
                "name": algorithm_name,
                "display_name": display_name,
                "description": description,
            }
        )
        return build_solution(
            problem=self.problem,
            metadata=metadata,
            packed_items=list(self.session.packed),
            unpacked_items=list(self._unpacked),
            execution_time_seconds=0.0,
        )

    def capture(
        self,
        *,
        order_id: str,
        orders_path: Path,
        orders_sha256: str,
        description: str = "Episodio del estudio de selección de reglas.",
    ) -> dict[str, Any]:
        from pilot_problems import capture_document

        document = capture_document(
            self.problem,
            self.solution(
                algorithm_name="rl_rule_selection",
                display_name="Selección de reglas",
                description=description,
            ),
            method="rl_rule_selection",
            order_id=order_id,
            orders_path=orders_path,
            orders_sha256=orders_sha256,
            checkpoint_path=orders_path,
        )
        document["physical_stability_verified"] = None
        document["reward_sum"] = self.geometric_utilization()
        document["decisions"] = self._decisions
        return document

    def released_sessions(self) -> int:
        return sum(ref() is None for ref in self._closed_sessions)

    def _assert_contract(self, problem: Any) -> None:
        observed = {key: getattr(problem.constraints, key) for key in COMPACT_FLAGS}
        if observed != COMPACT_FLAGS:
            raise ValueError("las restricciones no son las del contrato compacto")
        params = dict(problem.algorithm.parameters)
        if int(params.get("lookahead_p")) != 1 or int(params.get("select_s")) != 1:
            raise ValueError("el contrato exige p=1 y s=1")
        if params.get("sort_strategy") != "input_order":
            raise ValueError("el contrato exige la secuencia original")
        if len(problem.containers) != 1:
            raise ValueError("el contrato exige un contenedor")

    def _legal(self, item: Any) -> list[Any]:
        if self._cached is not None and self._cached[0] == item.id:
            return self._cached[1]
        prepare_imports()
        from packing_services.online.types import StepOption

        started = time.perf_counter()
        options = []
        for candidate in self.session.candidates(item, self._constraints):
            if self._mask.allows(candidate, item, self.session, self._constraints):
                options.append(StepOption(item=item, candidate=candidate, buffer_index=0))
        self.candidate_seconds += time.perf_counter() - started
        self.candidate_generations += 1
        self._cached = (item.id, options)
        return options

    def _stop_current(self) -> None:
        prepare_imports()
        from packing_services.domain.models import UnpackedItem

        current = self._remaining[0]
        self._unpacked.append(UnpackedItem(item_id=current.id, reason=TERMINAL_REASON))
        for pending in self._remaining[1:]:
            self._unpacked.append(UnpackedItem(item_id=pending.id, reason=SUFFIX_REASON))
        self._remaining = []
        self._terminated = True
        self._cached = None

    def _view(self, *, action: int | None, reward: float, placed: bool) -> tuple[list[float], dict[str, Any]]:
        if self._terminated or not self._remaining:
            proposals = propose_rules([], self.session)
            observation = encode_observation(
                container=self.problem.containers[0],
                item=None,
                session=self.session,
                proposals=proposals,
                skyline=current_max_height(self.session),
                orientations=[],
            )
        else:
            current = self._remaining[0]
            options = self._legal(current)
            proposals = propose_rules(options, self.session)
            observation = encode_observation(
                container=self.problem.containers[0],
                item=current,
                session=self.session,
                proposals=proposals,
                skyline=current_max_height(self.session),
                orientations=self.session.orientations_for(current, self._constraints),
            )
        info = {
            "terminated": self._terminated,
            "action": action,
            "reward": reward,
            "placed": placed,
            "decision_redundancy": self._decisions[-1]["redundancy"] if self._decisions else None,
            "redundancy": redundancy(proposals),
            "proposals": [
                {
                    "rule": row["rule"],
                    "action": row["action"],
                    "candidate_index": row["candidate_index"],
                    "geometry": row["geometry"],
                }
                for row in proposals
            ],
            "physical_stability_verified": None,
        }
        return observation, info
