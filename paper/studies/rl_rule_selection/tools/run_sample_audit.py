"""Escribe la auditoría de exposición y el manifiesto de train."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sample_audit import write_audits  # noqa: E402

STUDY = HERE.parent


def main() -> int:
    audit, train = write_audits()
    public = dict(audit)
    public.pop("excluded_ids", None)
    public["n_excluded_ids"] = audit["union_unique"]
    (STUDY / "exposure_audit.json").write_text(
        json.dumps(public, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (STUDY / "train_manifest.json").write_text(
        json.dumps(train, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "n_train": train["n_train"],
                "dropped_clones": len(train["dropped_clones"]),
                "preflight_orders": [row["order_id"] for row in train["preflight_orders"]],
                "remaining_in_pool_by_target": audit["remaining_in_pool_by_target"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
