#!/usr/bin/env python3
"""Regenera docs/algorithm_catalog.md desde el registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from packing_services.algorithms.registry import get_default_registry
from packing_services.domain.enums import AlgorithmStatus


def main() -> None:
    registry = get_default_registry()
    all_meta = registry.list_metadata()
    implemented = len(registry.list_metadata(status=AlgorithmStatus.IMPLEMENTED))
    adapters = len(registry.list_metadata(status=AlgorithmStatus.ADAPTER))
    future = len(registry.list_metadata(status=AlgorithmStatus.FUTURE))

    lines = [
        "# Catálogo de algoritmos",
        "",
        "Documento hijo de [`../README.md`](../README.md). Índice: [`README.md`](README.md).",
        "Se regenera con `python scripts/regenerate_algorithm_catalog.py`.",
        "",
        (
            f"Resumen: **{len(all_meta)} algoritmos** — "
            f"{implemented} implementados, {adapters} adaptadores, {future} futuros."
        ),
        "",
        "| name | display_name | family | status | problem_types |",
        "|------|--------------|--------|--------|---------------|",
    ]
    for meta in sorted(all_meta, key=lambda m: (m.status.value, m.name)):
        pts = ", ".join(p.value for p in meta.problem_types)
        lines.append(
            f"| `{meta.name}` | {meta.display_name} | "
            f"{meta.algorithm_family.value} | {meta.status.value} | {pts} |"
        )
    lines.append("")
    out = ROOT / "docs" / "algorithm_catalog.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({implemented} implemented / {len(all_meta)} total)")


if __name__ == "__main__":
    main()
