"""Pruebas del diseño de preflight (static-only; sin pedidos reales)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parent
_STUDY = _TOOLS.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from preflight_selection import select_by_item_count_quantiles, synthetic_metadata_pool
from run_preflight_real import load_protocol, main, run_static_only


def test_protocol_json_valid():
    path = _STUDY / "preflight_real_protocol.json"
    document = load_protocol(path)
    assert document["sample_design"]["n_orders"] == 4
    assert document["policies"]["max_episodes"] == 16
    assert document["budgets_proposed_before_execution"]["concurrency"] == 1
    assert document["not_executed_in_r03_preparation"] is True


def test_selection_rule_deterministic_and_balanced():
    pool = synthetic_metadata_pool()
    a = select_by_item_count_quantiles(pool, excluded_ids={"E010"})
    b = select_by_item_count_quantiles(pool, excluded_ids={"E010"})
    assert a == b
    assert a["n_orders"] == 4
    targets = {row["target"] for row in a["selected"]}
    assert targets == {"euro-pallet", "rollcontainer"}
    for target, pair in a["by_target"].items():
        assert pair[0]["n_items"] <= pair[1]["n_items"]
        assert pair[0]["role"] == "lower_quantile"
        assert pair[1]["role"] == "upper_quantile"


def test_static_only_cli(capsys):
    code = main(["--static-only", "--protocol", str(_STUDY / "preflight_real_protocol.json")])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["real_orders_packed"] is False
    assert out["training_executed"] is False
    assert out["planned_episodes"] == 16
    assert out["selection"]["n_orders"] == 4


def test_real_mode_blocked():
    code = main(["--protocol", str(_STUDY / "preflight_real_protocol.json")])
    assert code == 2
