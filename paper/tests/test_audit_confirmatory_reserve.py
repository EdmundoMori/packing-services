"""Clasificación sintética de la reserva y del registro de exposición."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


reserve = _load("audit_confirmatory_reserve")
registry = _load("audit_exposure_registry")


class ReserveTests(unittest.TestCase):
    def test_categories_keep_string_ids_and_do_not_call_the_set_clean(self):
        result = reserve.classify_reserve(
            ["00100", "00012", "00007", "00008"],
            {"00100": "euro-pallet", "00012": "euro-pallet", "00007": "rollcontainer", "00008": "euro-pallet"},
            {"scale.train": ["00999"], "working.val": ["00100"], "missing.train": None},
            {"report_eval": ["00012"]},
        )
        self.assertEqual(result["crosses_with_train_or_val"]["ids"], ["00100"])
        self.assertEqual(result["historical_evaluation"]["ids"], ["00012"])
        self.assertEqual(result["uncertain_exposure"]["ids"], ["00008"])
        self.assertEqual(result["non_euro"]["rollcontainer"], ["00007"])
        self.assertFalse(result["called_clean"])
        self.assertIn("missing.train", result["train_val_manifests_missing"])
        self.assertTrue(result["uncertain_exposure"]["ids"][0].startswith("00"))

    def test_missing_full_test_is_not_an_empty_reserve(self):
        result = reserve.classify_reserve(None, {}, {}, {})
        self.assertEqual(result["evidence"], "faltante")
        self.assertIsNone(result["full_test_n"])
        self.assertNotIn("limpio", json.dumps(result))


class RegistryTests(unittest.TestCase):
    def test_evaluation_rows_are_not_a_split_manifest(self):
        payload = {"rows": [{"order_id": "00100", "engine": "heuristic", "volume_utilization": 0.5}]}
        classified = registry.classify_payload("artifacts/reports/05_rl_ppo.json", payload)
        self.assertIn("evaluacion_registrada", classified["demonstrates"])
        self.assertNotIn("pertenencia_entrenamiento", classified["demonstrates"])
        self.assertEqual(classified["ids"]["evaluacion"], ["00100"])

    def test_split_object_is_membership(self):
        classified = registry.classify_payload(
            "data/splits/full_split.json",
            {"train": ["00100"], "val": ["00012"], "test": ["00007"]},
        )
        self.assertEqual(classified["evidence_type"], "manifiesto")
        self.assertIn("pertenencia_entrenamiento", classified["demonstrates"])
        self.assertEqual(classified["ids"]["manifiesto_train"], ["00100"])


if __name__ == "__main__":
    unittest.main()
