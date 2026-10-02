"""Pruebas sintéticas del auditor de splits. No lee el dataset real."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "tools" / "audit_split_exposure.py"
    spec = importlib.util.spec_from_file_location("audit_split_exposure", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


audit_mod = _load()


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class SplitExposureTests(unittest.TestCase):
    def test_intersections_duplicates_and_leading_zeros(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            full = {
                "train": ["00100", "00100", "00012", "00100408"],
                "val": ["00100408"],
                "test": ["00007"],
            }
            working = {"train": ["00100"], "val": ["00999"], "test": ["00007"]}
            scale = {"train": ["00100", "00012"], "val": ["00100408"], "test": ["00007"]}
            _write(root / "data/splits/full_split.json", full)
            _write(root / "data/splits/working_split.json", working)
            _write(root / "data/splits/scale_split.json", scale)
            _write(root / "data/splits/blocked_demo_ids.json", {"order_ids": ["00100408"]})
            _write(root / "data/train/order_ids.json", ["00100"])
            _write(root / "data/val/order_ids.json", ["00999"])
            _write(root / "data/test/order_ids.json", ["00007"])
            _write(root / "data/scale/train/order_ids.json", ["00100", "00012"])
            _write(root / "data/scale/val/order_ids.json", ["00100408"])
            _write(root / "data/scale/test/order_ids.json", ["00007"])
            _write(root / "data/holdout_producto/order_ids.json", ["00100408"])
            report = {
                "working_ids": working,
                "scale_ids": scale,
                "blocked_demo_ids": ["00100408"],
            }
            _write(root / "artifacts/reports/01_splits.json", report)
            _write(
                root / "artifacts/reports/05_rl_ppo.json",
                {"rows": [{"order_id": "00100408"}, {"order_id": "00100408"}]},
            )
            _write(
                root / "artifacts/reports/06_evaluar_holdout.json",
                {"holdout": {"order_ids": ["00100408"]}, "scale_val": {"order_ids": ["00100408"]}},
            )
            _write(root / "artifacts/reports/09_homologar_pct.json", {"order_ids": ["00100408"]})
            _write(root / "artifacts/reports/10_comparar_pct.json", {"shared": ["00100408"]})
            result = audit_mod.audit(root)
            self.assertIn("00100", result["duplicates_within_splits"]["manifest_full.train"])
            shared = result["intersections"]["manifest_working.train ∩ manifest_scale.train"]
            self.assertEqual(shared["ids"], ["00100"])
            self.assertIsInstance(shared["ids"][0], str)
            self.assertTrue(shared["ids"][0].startswith("00"))
            self.assertIn("manifest_full.train", result["exposure"]["A_pertenencia_entrenamiento"]["observado_en"])
            self.assertIn("05_rows", result["exposure"]["B_validacion_o_seleccion"]["observado_en"])
            self.assertTrue(result["exposure"]["D_exposicion_desconocida"]["pkl_no_leidos"])

    def test_missing_files_do_not_invent_independence(self):
        with tempfile.TemporaryDirectory() as folder:
            result = audit_mod.audit(Path(folder))
            self.assertTrue(result["missing_files"])
            self.assertEqual(result["focus_locations"], [])
            self.assertIn("no demuestra", result["exposure"]["A_pertenencia_entrenamiento"]["conclusion"])
            self.assertNotIn("independiente", json.dumps(result["exposure"]))

    def test_different_cuts_keep_full_ids_and_missing_is_not_empty(self):
        lists = {name: [] for name in audit_mod.partition_names()}
        lists["manifest_working.train"] = ["00100", "00012"]
        lists["manifest_working.val"] = ["00007"]
        lists["manifest_working.test"] = ["00008"]
        lists["manifest_scale.train"] = ["00012"]
        lists["manifest_scale.val"] = ["00100"]
        lists["manifest_scale.test"] = ["00009"]
        lists["manifest_full.train"] = ["00100", "00012", "00020"]
        lists["manifest_full.val"] = ["00007", "00021"]
        lists["manifest_full.test"] = ["00008", "00009"]
        lists["manifest_scale.test"] = None
        result = audit_mod.partition_cross_audit(lists)
        self.assertEqual(result["n_pairs"], 36)
        leak = result["pairs"]["manifest_working.train ∩ manifest_scale.val"]
        self.assertEqual(leak["status"], "requiere_investigar")
        self.assertEqual(leak["ids"], ["00100"])
        self.assertIsInstance(leak["ids"][0], str)
        self.assertTrue(leak["ids"][0].startswith("00"))
        missing = result["pairs"]["manifest_working.test ∩ manifest_scale.test"]
        self.assertEqual(missing["evidence"], "faltante")
        self.assertIsNone(missing["n"])
        self.assertNotEqual(missing.get("status"), "sin_cruce_observado")
        expected = result["pairs"]["manifest_working.train ∩ manifest_full.train"]
        self.assertEqual(expected["status"], "solapamiento_esperado")
        self.assertTrue(expected["subset_contained_in_full"])
        same = result["pairs"]["manifest_working.train ∩ manifest_scale.train"]
        self.assertEqual(same["ids"], ["00012"])


if __name__ == "__main__":
    unittest.main()
