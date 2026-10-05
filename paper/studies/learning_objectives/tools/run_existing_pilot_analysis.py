"""Ejecuta el análisis exploratorio sobre artefactos publicados. No empaqueta."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
REPO = STUDY.parents[2]
COUNTERFACTUAL = REPO / "paper" / "studies" / "counterfactual_ranking"

sys.path.insert(0, str(HERE))

from pilot_analysis import analyze_pilot  # noqa: E402
from pilot_reader import load_published_pilot  # noqa: E402


def main() -> int:
    pilot = load_published_pilot(COUNTERFACTUAL)
    report = analyze_pilot(pilot)
    report["source"] = {
        "study": str(COUNTERFACTUAL.relative_to(REPO)),
        "cases": "learning_packing/cases/*/result.json",
        "head_expected_for_this_step": "904038ff7f495510f1b8f3d398da3e4eb281a406",
    }
    out_dir = STUDY / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "02_existing_pilot_analysis.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(path), "aggregate": report["aggregate_equal_weight_per_seed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
