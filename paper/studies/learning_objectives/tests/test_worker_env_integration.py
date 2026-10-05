"""Pruebas de integración: intérprete venv, preflight, integridad y puerta."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
REPO = Path(__file__).resolve().parents[4]
CF_TOOLS = Path(__file__).resolve().parents[2] / "counterfactual_ranking" / "tools"
PAPER_TOOLS = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(CF_TOOLS))
sys.path.insert(0, str(PAPER_TOOLS))
sys.path.insert(0, str(TOOLS))

from episode_analysis import (  # noqa: E402
    apply_development_gate,
    classify_episode,
    evaluation_integrity,
    filter_cases,
    planned_cases,
)
from worker_env import (  # noqa: E402
    environment_preflight,
    preserve_executable,
    probe_worker_interpreter,
    venv_python,
)
from campaign import recompute_u  # noqa: E402


class TestVenvInterpreterPreservation(unittest.TestCase):
    def test_venv_linked_to_base_but_absolute_keeps_identity(self) -> None:
        py = venv_python(REPO)
        self.assertTrue(py.exists() or py.is_symlink())
        self.assertIn(".venv", py.parts)
        resolved = py.resolve()
        absolute = Path(preserve_executable(py))
        self.assertEqual(absolute, py.absolute())
        self.assertNotEqual(str(absolute), str(resolved))
        self.assertEqual(resolved, Path("/usr/bin/python3.10"))

    def test_subprocess_preserves_venv_and_imports_torch(self) -> None:
        py = venv_python(REPO)
        probe = probe_worker_interpreter(
            py, cwd=REPO, extra_imports=["torch", "actor_policy_s", "actor_features"]
        )
        self.assertTrue(probe.get("ok"), probe)
        self.assertTrue(probe.get("in_venv"))
        self.assertTrue(probe["imports"].get("torch"))
        self.assertTrue(probe["imports"].get("actor_policy_s"))
        self.assertIn(".venv", Path(probe["invoked_python"]).parts)

    def test_resolve_would_lose_torch(self) -> None:
        resolved = str(venv_python(REPO).resolve())
        script = "import sys; print(sys.prefix); import torch"
        completed = subprocess.run(
            [resolved, "-c", script],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("ModuleNotFoundError", completed.stderr)


class TestEnvironmentPreflight(unittest.TestCase):
    def test_preflight_ok_on_real_venv(self) -> None:
        result = environment_preflight(REPO)
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["harness_failure"])

    def test_preflight_fails_before_grid_on_bad_python(self) -> None:
        with mock.patch("worker_env.venv_python", return_value=Path("/usr/bin/python3.10")):
            result = environment_preflight(REPO)
        self.assertFalse(result["ok"])
        self.assertTrue(result["harness_failure"])
        self.assertFalse(result["gate_applicable"])


class TestIntegrityAndGate(unittest.TestCase):
    def test_zero_captures_rejects_completeness(self) -> None:
        integrity = evaluation_integrity(
            n_keys_received=240,
            expected_keys=240,
            n_episodes_executed=0,
            n_audited_captures=0,
            method_failures=0,
            harness_failures=240,
            evaluator_errors=0,
            harness_preflight_ok=True,
        )
        self.assertTrue(integrity["keys_complete"])
        self.assertFalse(integrity["complete_audited_evaluation"])
        self.assertFalse(integrity["gate_applicable"])
        gate = apply_development_gate(
            [],
            {
                "preferences_minus_classification": {
                    "mean": 0.0,
                    "by_target": {"euro-pallet": {"mean": 0.0}, "rollcontainer": {"mean": 0.0}},
                }
            },
            evaluator_errors=0,
            missing_keys=0,
            remaining_seconds_for_test=20000,
            integrity=integrity,
        )
        self.assertFalse(gate["gate_applicable"])
        self.assertIn("evaluacion_incompleta", gate["decision"])
        self.assertNotEqual(gate["decision"], "no_avanzar_con_esta_configuracion")

    def test_method_failure_distinct_from_harness(self) -> None:
        method = classify_episode(
            status="timeout",
            raw_u_geom=None,
            geometry_valid=False,
            contrast_matches=False,
            error="timeout de 300 s",
        )
        harness = classify_episode(
            status="crash",
            raw_u_geom=None,
            geometry_valid=False,
            contrast_matches=False,
            error="ModuleNotFoundError: No module named 'torch'",
        )
        self.assertTrue(method["method_failure"])
        self.assertFalse(method["harness_failure"])
        self.assertEqual(method["effective_u_geom"], 0.0)
        self.assertTrue(method["in_denominator"])
        self.assertTrue(harness["harness_failure"])
        self.assertFalse(harness["method_failure"])
        self.assertIsNone(harness["effective_u_geom"])
        self.assertFalse(harness["in_denominator"])

    def test_gate_not_applicable_on_invalid_evaluation(self) -> None:
        integrity = evaluation_integrity(
            n_keys_received=0,
            expected_keys=240,
            n_episodes_executed=0,
            n_audited_captures=0,
            method_failures=0,
            harness_failures=0,
            evaluator_errors=0,
            harness_preflight_ok=False,
        )
        gate = apply_development_gate(
            [],
            {
                "preferences_minus_classification": {
                    "mean": 0.01,
                    "by_target": {"euro-pallet": {"mean": 0.01}, "rollcontainer": {"mean": 0.01}},
                }
            },
            evaluator_errors=0,
            missing_keys=240,
            remaining_seconds_for_test=20000,
            integrity=integrity,
        )
        self.assertFalse(gate["gate_applicable"])
        self.assertFalse(gate["passed"])

    def test_planned_filter_smoke_eight(self) -> None:
        orders = [
            {"order_id": "00107391", "split": "development", "target": "rollcontainer"},
            {"order_id": "00106955", "split": "development", "target": "euro-pallet"},
        ]
        cases = filter_cases(
            planned_cases(orders),
            arms={"greedy", "classification", "preferences", "return_difference"},
            seeds={11},
        )
        self.assertEqual(len(cases), 8)


class TestRealSubprocessSyntheticEpisode(unittest.TestCase):
    """Camino real de subprocess: intérprete venv + worker + captura/contraste/auditoría."""

    def test_greedy_and_actor_worker_produce_audited_capture(self) -> None:
        # Reponer paths por si otros tests los vacían
        for entry in (str(CF_TOOLS), str(PAPER_TOOLS), str(TOOLS)):
            if entry in sys.path:
                sys.path.remove(entry)
            sys.path.insert(0, entry)

        from labeling_contracts import verify_frozen_artifacts
        from labeling_io import atomic_write_json
        from model_spec import build_actor
        from pilot_metrics import contrast_capture
        from pilot_problems import prepare_imports, problem_snapshot
        from training_loop import configure_training_runtime, save_checkpoint

        prepare_imports()
        from compact_study import build_compact_problem
        from splits import load_orders

        configure_training_runtime()
        study = TOOLS.parent
        contracts = verify_frozen_artifacts(
            protocol_path=study / "protocol_frozen.json",
            sample_path=study / "sample_manifest.json",
            study_dir=study,
        )
        orders = load_orders(Path(contracts["dataset"]))
        order_id = "00107391"
        problem = build_compact_problem(orders, order_id)
        snap = problem_snapshot(problem)
        py = preserve_executable(venv_python(REPO))
        worker = str((TOOLS / "episode_worker.py").absolute())
        labels = study / "learning_labels_attempt03"
        norm = json.loads((labels / "normalization_train.json").read_text(encoding="utf-8"))
        stats = {"mean": norm["mean"], "scale": norm["scale"]}

        audit_path = PAPER_TOOLS / "audit_internal_solution.py"
        spec = importlib.util.spec_from_file_location("audit_int_test", audit_path)
        assert spec and spec.loader
        audit_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit_mod)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ckpt = tmp_path / "ckpt.pt"
            model = build_actor(11)
            save_checkpoint(
                ckpt,
                model,
                meta={"seed": 11, "arm": "classification", "epoch": 40, "n_optimizer_steps": 40},
            )

            for arm, checkpoint in (("greedy", None), ("classification", str(ckpt))):
                job = {
                    "order_id": order_id,
                    "arm": arm,
                    "seed": None if arm == "greedy" else 11,
                    "key": f"{arm}|{order_id}",
                    "dataset": str(contracts["dataset"]),
                    "dataset_sha256": contracts["dataset_sha256"],
                    "checkpoint": checkpoint,
                    "normalization": None if arm == "greedy" else stats,
                    "input_snapshot": snap,
                }
                job_path = tmp_path / f"job_{arm}.json"
                result_path = tmp_path / f"result_{arm}.json"
                atomic_write_json(job_path, job)
                completed = subprocess.run(
                    [py, "-u", worker, "--job", str(job_path), "--result", str(result_path)],
                    cwd=str(REPO),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=120,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(result_path.read_text(encoding="utf-8"))
                self.assertEqual(payload.get("status"), "ok", payload.get("error"))
                capture = payload.get("capture")
                self.assertIsInstance(capture, dict)
                contrast = contrast_capture(capture, snap, order_id=order_id, method=arm)
                self.assertTrue(contrast.get("matches"), contrast)
                audit = audit_mod.audit_document(capture)
                self.assertTrue(audit.get("internal_geometry_valid"), audit)
                u = recompute_u(capture)
                self.assertIsInstance(u, float)
                self.assertGreater(u, 0.0)


if __name__ == "__main__":
    unittest.main()
