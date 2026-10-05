"""Pruebas de que etiquetado y despliegue usan la misma fuente de S."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1]
TOOLS = HERE / "tools"
if str(TOOLS) in sys.path:
    sys.path.remove(str(TOOLS))
sys.path.insert(0, str(TOOLS))

import candidate_support  # noqa: E402
import pipeline  # noqa: E402
import support_api  # noqa: E402
from losses import TIE_COEFFICIENT  # noqa: E402


def _option(index: int, x: float, y: float, z: float, l: float, w: float, h: float):
    candidate = SimpleNamespace(
        bin_index=0,
        position=SimpleNamespace(x=x, y=y, z=z),
        dimensions=SimpleNamespace(length=l, width=w, height=h),
    )
    return SimpleNamespace(candidate=candidate, item=f"item-{index}")


class PipelineWiringTests(unittest.TestCase):
    def test_single_source_symbols(self) -> None:
        self.assertIs(pipeline.SUPPORT_BUILDER, candidate_support.build_candidate_support)
        self.assertIs(pipeline.SUPPORT_BUILDER_FROM_OPTIONS, candidate_support.build_candidate_support_from_options)
        self.assertIs(support_api.build_S, candidate_support.build_candidate_support)
        self.assertIs(support_api.build_S_from_options, candidate_support.build_candidate_support_from_options)

    def test_labeling_and_deployment_same_S(self) -> None:
        options = [
            _option(0, 0, 0, 0, 10, 10, 10),
            _option(1, 1, 0, 0, 20, 10, 10),
            _option(2, 2, 0, 0, 10, 20, 10),
            _option(3, 3, 0, 0, 10, 10, 20),
            _option(4, 4, 0, 0, 15, 15, 15),
        ]
        greedy = options[0]
        labeled = pipeline.labeling_select_support(options, greedy)
        # deployment scores only |S| logits
        logits = [0.1, 0.9, 0.2, 0.3][: len(labeled)]
        chosen = pipeline.deployment_select_action(options, greedy, logits)
        self.assertEqual(len(labeled), len(logits))
        self.assertIs(chosen, labeled[1])

    def test_preference_tie_coefficient_is_one(self) -> None:
        self.assertEqual(TIE_COEFFICIENT, 1.0)


if __name__ == "__main__":
    unittest.main()
