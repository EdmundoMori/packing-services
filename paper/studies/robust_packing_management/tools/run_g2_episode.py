"""Ejecutor de episodio G2 con métodos M0–M3 (reutiliza transición G1)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from adapters import PolicySessionView, build_empty_session, commit_realized, rebuild_session_from_revealed, capture_equivalence, revealed_to_aabb
from episode import EpisodeResult, StepRecord
from geometry_contract import (
    AABBBox,
    AxisTriple,
    OrientedSizes,
    certificate_realized_safe_if_subseteq_envelope,
    envelope_exceeded,
    geometric_violation,
    validate_margin,
)
from info_separation import EpisodeSpec, PolicyObservation, RevealedBox


def run_method_episode(
    spec: EpisodeSpec,
    method_fn: Callable,
    *,
    method_id: str,
    timeout_s: float | None = None,
) -> EpisodeResult:
    t0 = time.perf_counter()
    truth = spec.truth()
    session = build_empty_session(spec.container_mm)
    revealed: list[RevealedBox] = []
    steps: list[StepRecord] = []
    index = 0
    V_nom = 0.0
    V_before = 0.0
    geom_fail = False
    n_env = 0
    termination = "completed"

    while index < len(spec.items):
        if timeout_s is not None and (time.perf_counter() - t0) > timeout_s:
            termination = "timeout"
            V_before = V_nom
            break
        it = spec.items[index]
        obs = PolicyObservation(
            container_mm=spec.container_mm,
            current_item_id=it.item_id,
            current_nominal_mm=it.nominal_mm,
            margin_mm=AxisTriple(0.0, 0.0, 0.0),
            revealed=tuple(revealed),
            remaining_count_including_current=len(spec.items) - index,
        )
        view = PolicySessionView(session, allow_rotation=spec.allow_rotation)
        margin, choice = method_fn(obs, view)
        margin = validate_margin(margin.as_tuple(), "margin")
        # Recompute n_candidates under chosen margin for logging
        obs_m = PolicyObservation(
            container_mm=obs.container_mm,
            current_item_id=obs.current_item_id,
            current_nominal_mm=obs.current_nominal_mm,
            margin_mm=margin,
            revealed=obs.revealed,
            remaining_count_including_current=obs.remaining_count_including_current,
        )
        n_cand = len(view.list_envelope_candidates(obs_m))
        if choice is None:
            steps.append(
                StepRecord(
                    item_id=it.item_id,
                    margin_mm=margin.as_tuple(),
                    event="no_candidate",
                    n_candidates=n_cand,
                )
            )
            V_before = V_nom
            termination = "no_candidate"
            break

        realized = truth.peek_realized(it.item_id)
        sized = OrientedSizes.from_catalogue(
            it.nominal_mm, margin, choice.orientation_order, realized=realized
        )
        assert sized.realized_oriented is not None
        flb = choice.flb_mm
        exceeded = envelope_exceeded(sized.realized_oriented, sized.envelope)
        occupied = revealed_to_aabb(revealed)
        geom = geometric_violation(AABBBox(flb, sized.realized_oriented), spec.container_mm, occupied)
        cert = certificate_realized_safe_if_subseteq_envelope(
            flb=flb,
            envelope=sized.envelope,
            realized_oriented=sized.realized_oriented,
            container=spec.container_mm,
            occupied_revealed=occupied,
        )
        if geom["geometric_failure"]:
            if exceeded:
                n_env += 1
            steps.append(
                StepRecord(
                    item_id=it.item_id,
                    margin_mm=margin.as_tuple(),
                    event="geometric_failure",
                    envelope_exceeded_flag=exceeded,
                    flb_mm=flb,
                    orientation_order=choice.orientation_order,
                    nominal_oriented=sized.nominal_oriented.as_tuple(),
                    envelope=sized.envelope.as_tuple(),
                    realized_oriented=sized.realized_oriented.as_tuple(),
                    certificate=cert,
                    n_candidates=n_cand,
                )
            )
            V_before = V_nom
            geom_fail = True
            termination = "geometric_failure"
            break

        if exceeded:
            n_env += 1
            event = "envelope_exceeded"
        else:
            event = "placed"
        revealed.append(
            RevealedBox(
                item_id=it.item_id,
                flb_mm=flb,
                realized_oriented_mm=sized.realized_oriented,
                nominal_mm=it.nominal_mm,
                orientation_order=choice.orientation_order,
                envelope_mm=sized.envelope,
                envelope_exceeded=exceeded,
            )
        )
        commit_realized(
            session,
            item_id=it.item_id,
            flb_mm=flb,
            realized_oriented=sized.realized_oriented,
            allow_rotation=spec.allow_rotation,
        )
        truth.mark_released(it.item_id)
        V_nom += it.nominal_mm.volume
        steps.append(
            StepRecord(
                item_id=it.item_id,
                margin_mm=margin.as_tuple(),
                event=event,
                envelope_exceeded_flag=exceeded,
                flb_mm=flb,
                orientation_order=choice.orientation_order,
                nominal_oriented=sized.nominal_oriented.as_tuple(),
                envelope=sized.envelope.as_tuple(),
                realized_oriented=sized.realized_oriented.as_tuple(),
                certificate=cert,
                n_candidates=n_cand,
            )
        )
        index += 1
    else:
        V_before = V_nom
        termination = "completed"

    vol_c = spec.container_mm.volume
    j_b = 0.0 if geom_fail else (V_nom / vol_c if vol_c > 0 else 0.0)
    rebuild_ok = None
    rebuild_note = None
    try:
        rebuilt = rebuild_session_from_revealed(
            spec.container_mm, revealed, allow_rotation=spec.allow_rotation
        )
        eq = capture_equivalence(rebuilt, revealed)
        rebuild_ok = bool(eq.get("matches"))
        if not rebuild_ok:
            rebuild_note = str(eq)
    except Exception as exc:  # noqa: BLE001
        rebuild_ok = False
        rebuild_note = f"bloqueo_rebuild: {exc}"

    return EpisodeResult(
        termination=termination,  # type: ignore[arg-type]
        steps=steps,
        placed_ids=[r.item_id for r in revealed],
        V_nom_mm3=V_nom,
        V_nom_before_failure_mm3=V_before,
        container_volume_mm3=vol_c,
        J_B=j_b,
        n_envelope_exceeded=n_env,
        geometric_failure=geom_fail,
        events=[s.event for s in steps],
        rebuild_ok=rebuild_ok,
        rebuild_note=rebuild_note,
    )


def persist_episode(
    out_dir: Path,
    *,
    meta: dict[str, Any],
    result: EpisodeResult,
    wall_s: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        **meta,
        "wall_seconds": wall_s,
        "termination": result.termination,
        "J_B": result.J_B,
        "V_nom_mm3": result.V_nom_mm3,
        "V_nom_before_failure_mm3": result.V_nom_before_failure_mm3,
        "container_volume_mm3": result.container_volume_mm3,
        "geometric_failure": result.geometric_failure,
        "n_envelope_exceeded": result.n_envelope_exceeded,
        "events": result.events,
        "placed_ids": result.placed_ids,
        "rebuild_ok": result.rebuild_ok,
        "rebuild_note": result.rebuild_note,
        "physical_stability_verified": None,
        "steps": [asdict(s) for s in result.steps],
        "failed_attempt": None,
    }
    if result.geometric_failure or result.termination == "no_candidate":
        payload["failed_attempt"] = asdict(result.steps[-1]) if result.steps else None
        payload["accepted_placements"] = [asdict(s) for s in result.steps[:-1]]
    else:
        payload["accepted_placements"] = [asdict(s) for s in result.steps]
    tmp = out_dir / "result.json.tmp"
    final = out_dir / "result.json"
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(final)
