"""Holdout de producto: offline vs online sobre los cinco pedidos reservados."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packing_services.benchmark.holdout_offline_online import (
    HOLDOUT_ENGINES,
    HOLDOUT_ORDER_IDS,
    RANKING_HOLDOUT,
    RANKING_HOLDOUT_MULTI,
    HoldoutEngine,
    _multi_ranking_key,
    run_holdout_offline_online,
    run_holdout_order,
    summarize_holdout,
)
from packing_services.datasets.bed_bpp import TARGET_SIZES_MM
from packing_services.domain.enums import PackingMode, ProblemType
from packing_services.domain.models import Metrics
from packing_services.schemas.responses import BenchmarkEngineResult
from packing_services.online.learned.production import (
    CINTA_MODEL_PATH,
    DEFAULT_MODEL_PATH,
    PRODUCT_HOLDOUT_ORDER_IDS,
)

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "examples" / "5_bed-bpp.json"
SMALLEST = "00100408"

# El heurístico con lookahead p=3 cuesta minutos por pedido; los tests usan el
# subconjunto barato y la corrida completa queda para el script.
CHEAP_ENGINES: tuple[HoldoutEngine, ...] = tuple(
    e
    for e in HOLDOUT_ENGINES
    if not (e.algorithm == "online_3d_bpp_heuristic" and e.variant == "p3s2")
)


def _orders() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def _skip_without_production_models() -> None:
    pytest.importorskip("torch")
    for relative in (DEFAULT_MODEL_PATH, CINTA_MODEL_PATH):
        if not (REPO / relative).is_file():
            pytest.skip(f"falta checkpoint de producción {relative}")


def test_holdout_ids_are_the_reserved_five():
    assert HOLDOUT_ORDER_IDS == tuple(sorted(PRODUCT_HOLDOUT_ORDER_IDS))
    assert len(HOLDOUT_ORDER_IDS) == 5
    orders = _orders()
    assert set(HOLDOUT_ORDER_IDS) == set(orders)


def test_engine_labels_are_unique_and_cover_both_modes():
    labels = [e.label for e in HOLDOUT_ENGINES]
    assert len(labels) == len(set(labels))
    modes = {e.mode for e in HOLDOUT_ENGINES}
    assert modes == {PackingMode.OFFLINE, PackingMode.ONLINE}


def test_every_learned_engine_has_a_heuristic_at_the_same_budget():
    """La comparación es a igual información (p, s), no a igual nombre."""

    def budget(engine: HoldoutEngine) -> tuple:
        return (engine.parameters["lookahead_p"], engine.parameters["select_s"])

    learned = {
        budget(e) for e in HOLDOUT_ENGINES if e.algorithm == "drl_policy_3d_bpp"
    }
    greedy = {
        budget(e) for e in HOLDOUT_ENGINES if e.algorithm == "online_3d_bpp_heuristic"
    }
    assert learned
    assert learned == greedy


def test_offline_engines_carry_no_model_path():
    for engine in HOLDOUT_ENGINES:
        if engine.mode == PackingMode.OFFLINE:
            assert "model_path" not in engine.parameters


def test_learned_engines_point_at_production_checkpoints():
    paths = {
        e.parameters["model_path"]
        for e in HOLDOUT_ENGINES
        if e.algorithm == "drl_policy_3d_bpp"
    }
    assert paths == {DEFAULT_MODEL_PATH, CINTA_MODEL_PATH}


def test_order_runs_share_input_validator_and_metrics():
    _skip_without_production_models()
    response = run_holdout_order(_orders(), SMALLEST, engines=CHEAP_ENGINES)
    details = response.details
    assert details["order_id"] == SMALLEST
    assert details["is_product_holdout"] is True
    assert details["n_items"] == 26
    assert details["target"] == "euro-pallet"
    assert details["container_size"] == list(TARGET_SIZES_MM["euro-pallet"])
    assert details["engines_error"] == 0
    assert len(response.results) == len(CHEAP_ENGINES)
    assert set(response.ranking) == {r.engine for r in response.results}

    total_items = {
        r.metrics.items_packed + r.metrics.items_unpacked for r in response.results
    }
    assert total_items == {26}


def test_mode_decides_sort_strategy():
    _skip_without_production_models()
    response = run_holdout_order(_orders(), SMALLEST, engines=CHEAP_ENGINES)
    for result in response.results:
        expected = (
            "input_order"
            if result.details["packing_mode"] == PackingMode.ONLINE.value
            else "volume_desc"
        )
        assert result.details["sort_strategy"] == expected


def test_load_envelope_is_derived_and_bounded():
    _skip_without_production_models()
    response = run_holdout_order(_orders(), SMALLEST, engines=CHEAP_ENGINES)
    container = response.details["container_size"]
    for result in response.results:
        height = result.details["load_height_mm"]
        envelope = result.details["envelope_utilization"]
        assert 0.0 < height <= container[2]
        # El envolvente ocupado nunca es mayor que el contenedor completo.
        assert envelope >= result.metrics.volume_utilization


def test_target_override_forces_the_same_container_everywhere():
    _skip_without_production_models()
    offline_only = tuple(
        e for e in HOLDOUT_ENGINES if e.mode == PackingMode.OFFLINE
    )
    responses = run_holdout_offline_online(
        _orders(),
        order_ids=("00100001", SMALLEST),
        engines=offline_only,
        target="euro-pallet",
    )
    sizes = {tuple(r.details["container_size"]) for r in responses}
    assert sizes == {TARGET_SIZES_MM["euro-pallet"]}


def test_native_target_is_respected_per_order():
    """00100001 es rollcontainer y 00100408 euro-pallet en el propio BED-BPP."""

    offline_only = tuple(
        e for e in HOLDOUT_ENGINES if e.mode == PackingMode.OFFLINE
    )
    responses = run_holdout_offline_online(
        _orders(),
        order_ids=("00100001", SMALLEST),
        engines=offline_only,
    )
    by_order = {r.details["order_id"]: r.details for r in responses}
    assert by_order["00100001"]["target"] == "rollcontainer"
    assert by_order[SMALLEST]["target"] == "euro-pallet"
    assert by_order["00100001"]["container_size"] == list(
        TARGET_SIZES_MM["rollcontainer"]
    )


def test_summary_counts_one_win_per_order():
    _skip_without_production_models()
    responses = run_holdout_offline_online(
        _orders(),
        order_ids=(SMALLEST,),
        engines=CHEAP_ENGINES,
    )
    summary = summarize_holdout(responses)
    assert summary["orders_total"] == 1
    assert summary["orders"] == [SMALLEST]
    assert len(summary["engines"]) == len(CHEAP_ENGINES)
    assert sum(row["wins"] for row in summary["engines"]) == 1
    for row in summary["engines"]:
        assert row["orders"] == 1
        assert 0.0 <= row["mean_volume_utilization"] <= 1.0


def test_single_container_keeps_the_original_ranking_criterion():
    """La tabla de un contenedor no debe cambiar: ya está publicada."""

    offline_only = tuple(e for e in HOLDOUT_ENGINES if e.mode == PackingMode.OFFLINE)
    response = run_holdout_order(_orders(), SMALLEST, engines=offline_only)
    assert response.details["benchmark_group"] == "HOLDOUT_OFFLINE_VS_ONLINE"
    assert response.details["containers_available"] == 1
    assert response.ranking_explanation == RANKING_HOLDOUT
    for result in response.results:
        assert result.metrics.containers_used <= 1


def test_two_containers_are_identical_replicas_with_distinct_ids():
    offline_only = tuple(e for e in HOLDOUT_ENGINES if e.mode == PackingMode.OFFLINE)
    single = run_holdout_order(_orders(), SMALLEST, engines=offline_only)
    double = run_holdout_order(
        _orders(), SMALLEST, engines=offline_only, containers=2
    )
    assert double.details["containers_available"] == 2
    assert double.details["benchmark_group"] == "HOLDOUT_OFFLINE_VS_ONLINE_MULTI"
    assert double.ranking_explanation == RANKING_HOLDOUT_MULTI
    # Mismo destino y mismas dimensiones: el segundo pallet es una réplica.
    assert double.details["container_size"] == single.details["container_size"]
    assert double.details["container_id"].startswith(single.details["container_id"])
    assert double.details["n_items"] == single.details["n_items"]


def test_multi_ranking_prefers_the_complete_order_over_fewer_pallets():
    """Dejar carga en el muelle no puede ganarle a abrir el segundo pallet."""

    complete_two_pallets = BenchmarkEngineResult(
        engine="completo-2-pallets",
        status="success",
        is_valid=True,
        metrics=Metrics(items_packed=26, items_unpacked=0, containers_used=2),
    )
    partial_one_pallet = BenchmarkEngineResult(
        engine="parcial-1-pallet",
        status="success",
        is_valid=True,
        metrics=Metrics(items_packed=20, items_unpacked=6, containers_used=1),
    )
    ordered = sorted(
        [partial_one_pallet, complete_two_pallets], key=_multi_ranking_key
    )
    assert [r.engine for r in ordered] == ["completo-2-pallets", "parcial-1-pallet"]


def test_multi_ranking_prefers_fewer_pallets_when_both_are_complete():
    one = BenchmarkEngineResult(
        engine="un-pallet",
        status="success",
        is_valid=True,
        metrics=Metrics(items_packed=26, items_unpacked=0, containers_used=1),
    )
    two = BenchmarkEngineResult(
        engine="dos-pallets",
        status="success",
        is_valid=True,
        metrics=Metrics(items_packed=26, items_unpacked=0, containers_used=2),
    )
    ordered = sorted([two, one], key=_multi_ranking_key)
    assert [r.engine for r in ordered] == ["un-pallet", "dos-pallets"]


def test_summary_reports_the_multi_container_group():
    offline_only = tuple(e for e in HOLDOUT_ENGINES if e.mode == PackingMode.OFFLINE)
    responses = run_holdout_offline_online(
        _orders(),
        order_ids=(SMALLEST,),
        engines=offline_only,
        containers=2,
    )
    summary = summarize_holdout(responses)
    assert summary["benchmark_group"] == "HOLDOUT_OFFLINE_VS_ONLINE_MULTI"
    assert summary["containers_available"] == 2
    for row in summary["engines"]:
        assert row["containers_used"] in (1, 2)


def test_unknown_engine_reports_error_without_breaking_the_table():
    bogus = (
        HoldoutEngine(
            PackingMode.OFFLINE,
            ProblemType.THREE_D_BPP,
            "motor_inexistente",
        ),
    )
    response = run_holdout_order(_orders(), SMALLEST, engines=bogus)
    assert response.details["engines_error"] == 1
    assert response.results[0].is_valid is False
    assert "no encontrado" in (response.results[0].error or "")
