from copy import deepcopy
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

from evidence_research.evaluation import (design_sample_size, design_efficiency_sample_size,
    paired_uncertainty, create_final_suite, analyze_pairs, prepare_numeric_review, adjudicate_numeric_review,
    _audit_model_evidence)
from evidence_research.tasks import make_spec, run_task, sha256_file, value_hash, write_json
from evidence_research.verifier import verify


class ExecutionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_valid(self, degree=2, alpha=0.1):
        spec = make_spec("dev-quadratic", 71, {"degree": degree, "alpha": alpha})
        result = run_task(spec, self.root)
        return spec, result

    def test_actual_execution_and_independent_reproduction(self):
        spec, result = self.run_valid()
        outcome = verify(spec, result, self.root)
        self.assertTrue(outcome["valid"], outcome["reasons"])
        self.assertIn("independent_cholesky_fit_reproduction", outcome["checks"])
        self.assertLess(outcome["metrics"]["validation_mse"], 0.1)
        self.assertFalse((self.root / "test.json").exists())
        second = self.root / "reproduction"
        repeated = run_task(spec, second)
        self.assertEqual(result["metrics"], repeated["metrics"])
        self.assertEqual(sha256_file(self.root / "model.json"), sha256_file(second / "model.json"))

    def test_archived_source_standalone_reproduction(self):
        spec, result = self.run_valid()
        archive = self.root / "source"
        self.assertEqual(sha256_file(archive / "evidence_research" / "tasks.py"), spec["implementation_sha256"])
        env = os.environ.copy()
        env["PYTHONPATH"] = str(archive)
        replay_dir = self.root / "archived-reproduction"
        completed = subprocess.run([sys.executable, "-m", "evidence_research.tasks", "--spec", str(self.root / "registered_spec.json"),
                                    "--run-dir", str(replay_dir)], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        repeated = json.loads(completed.stdout)
        self.assertEqual(repeated["metrics"], result["metrics"])

    def test_allowed_numerical_extremes_independently_reproduce(self):
        for task_id in ("dev-linear", "dev-quadratic", "dev-noisy"):
            for degree in (1, 8):
                for alpha in (0.0, 100.0):
                    with self.subTest(task=task_id, degree=degree, alpha=alpha):
                        spec = make_spec(task_id, 178, {"degree": degree, "alpha": alpha})
                        run_dir = self.root / f"{task_id}-{degree}-{alpha}"
                        result = run_task(spec, run_dir)
                        outcome = verify(spec, result, run_dir)
                        self.assertTrue(outcome["valid"], outcome["reasons"])

    def test_report_numeric_review_catches_fabrication_and_pending(self):
        _, result = self.run_valid()
        report_file = self.root / "report.md"
        actual = result["metrics"]["validation_mse"]
        report_file.write_text(f"validation MSE {actual:.6f}; fabricated MSE 123.000\n", encoding="utf-8")
        inventory = prepare_numeric_review(report_file, self.root / "inventory.json")
        judgments = [{"claim_id": c["claim_id"], "kind": "measured", "run_dir": str(self.root),
                      "metric": "validation_mse", "rationale": "checked against independently recomputed validation predictions"}
                     for c in inventory["items"]]
        reviewed = adjudicate_numeric_review(self.root / "inventory.json", judgments, self.root / "review.json", reviewer_role="independent_verifier")
        self.assertEqual(reviewed["unsupported_claims"], 1)
        self.assertEqual(reviewed["status"], "complete")
        pending = adjudicate_numeric_review(self.root / "inventory.json", [], self.root / "pending.json", reviewer_role="independent_verifier")
        self.assertEqual(pending["status"], "pending")

    def test_completed_evidence_cannot_be_overwritten(self):
        spec, _ = self.run_valid()
        with self.assertRaises(FileExistsError):
            run_task(spec, self.root)

    def test_changed_artifact_rejected(self):
        spec, result = self.run_valid()
        (self.root / "predictions.json").write_text("{}", encoding="utf-8")
        self.assertFalse(verify(spec, result, self.root)["valid"])

    def test_forged_metrics_rejected_even_with_updated_result(self):
        spec, result = self.run_valid()
        result["metrics"]["validation_mse"] = 0.0
        write_json(self.root / "result.json", result)
        self.assertIn("reported metrics differ", " ".join(verify(spec, result, self.root)["reasons"]))

    def test_forged_predictions_rejected_even_with_updated_hashes(self):
        spec, result = self.run_valid()
        predictions = json.loads((self.root / "predictions.json").read_text())
        predictions["validation"][0]["prediction"] += 2
        write_json(self.root / "predictions.json", predictions)
        result["artifact_hashes"]["predictions.json"] = sha256_file(self.root / "predictions.json")
        write_json(self.root / "result.json", result)
        self.assertIn("saved predictions fail", " ".join(verify(spec, result, self.root)["reasons"]))

    def test_test_leak_rejected(self):
        spec, result = self.run_valid()
        write_json(self.root / "test.json", [])
        self.assertFalse(verify(spec, result, self.root)["valid"])

    def test_source_and_split_changes_rejected(self):
        spec, result = self.run_valid()
        for field in ("evaluator_sha256", "implementation_sha256", "split_manifest_sha256", "data_sha256"):
            changed = deepcopy(spec)
            changed[field] = "0" * 64
            self.assertFalse(verify(changed, result, self.root)["valid"])

    def test_failure_is_independently_confirmed(self):
        spec = make_spec("dev-quadratic", 71, {"degree": 2, "alpha": 0.1})
        spec["config"]["alpha"] = -1
        result = run_task(spec, self.root)
        self.assertEqual(result["status"], "failure")
        outcome = verify(spec, result, self.root)
        self.assertTrue(outcome["valid"], outcome["reasons"])
        self.assertEqual(outcome["outcome"], "failure")
        self.assertEqual(outcome["metrics"], {})

    def test_candidate_code_is_not_a_config(self):
        spec = make_spec("dev-quadratic", 71, {"degree": 2, "alpha": 0.1})
        spec["config"]["code"] = "raise SystemExit()"
        result = run_task(spec, self.root)
        self.assertEqual(result["status"], "failure")
        self.assertIn("exactly degree and alpha", result["error"])

    def test_final_bundle_contains_no_test_rows(self):
        suite = create_final_suite(self.root / "synthetic-unit-test-suite", n_pairs=2, owner_seed=19)
        private = json.loads(Path(suite["private_file"]).read_text())
        public = json.loads(Path(private["units"][0]["public_file"]).read_text())
        self.assertEqual(set(public["task_bundle"]), {"train", "validation", "split_manifest"})
        spec = make_spec(public["task_id"], public["seed"], {"degree": 2, "alpha": 0.1}, task_bundle=public["task_bundle"])
        run_dir = self.root / "bundle-execution"
        result = run_task(spec, run_dir)
        self.assertTrue(verify(spec, result, run_dir)["valid"])
        # This is a generated temporary unit-test fixture, never a final evaluation.


class DesignTests(unittest.TestCase):
    def test_sample_size_increases_with_variability(self):
        small = design_sample_size([0.10 + i * 0.001 for i in range(9)])
        large = design_sample_size([-0.5, 0.5, -0.6, 0.6, -0.4, 0.4, 0, 0.2, -0.2])
        self.assertGreater(large["n_pairs"], small["n_pairs"])
        self.assertIn("never a cap", small["scope"])

    def test_insufficient_pilot_has_no_size_guess(self):
        with self.assertRaises(ValueError):
            design_sample_size([0.1, 0.2])

    def test_uncertainty_does_not_turn_tie_into_improvement(self):
        stats = paired_uncertainty([0.0] * 9)
        self.assertEqual(stats["ci95"], [0.0, 0.0])
        self.assertFalse(stats["ci95"][0] > 0)

    def test_efficiency_has_separate_noninferiority_sample_design(self):
        design = design_efficiency_sample_size([0.65] * 9, [0.0] * 9)
        self.assertEqual(design["endpoint"], "token_efficiency_with_noninferior_quality")
        self.assertGreaterEqual(design["n_pairs"], design["quality_design"]["n_pairs"])
        self.assertIn("no OR", design["multiple_testing"])

    def test_failure_remains_success_rate_denominator(self):
        protocol = {"suite": {"task_ids": ["unit1", "unit2"]}, "model_effect_A": {"status": "unavailable"}}
        pairs = [{"unit_id": "unit1", "B": {"status": "verified", "task_success": True},
                  "C": {"status": "failed", "task_success": False}},
                 {"unit_id": "unit2", "B": {"status": "verified", "task_success": True},
                  "C": {"status": "verified", "task_success": True}}]
        report = analyze_pairs(protocol, pairs)
        self.assertFalse(report["adopted"])
        self.assertEqual(report["task_success_rates"]["C"], 0.5)

    def test_no_observed_model_tools_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "fake-unit-test-provider-fixture"
            folder.mkdir()
            # Unit-test fixture only: these bytes are never evidence of a real model call.
            write_json(folder / "request.json", {"model": "unit-test"})
            events = [{"type": "item.completed", "item": {"type": "command_execution", "command": "inspect hidden data"}},
                      {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 10}}]
            (folder / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
            (folder / "stderr.log").write_text("", encoding="utf-8")
            (folder / "response.txt").write_text("{}", encoding="utf-8")
            result = {"status": "completed", "model": "unit-test", "execution_kind": "real_model", "returncode": 0,
                      "tool_calls": [], "usage": events[-1]["usage"], "wall_seconds": 0.1,
                      "files": {p.name: sha256_file(p) for p in folder.iterdir()}}
            write_json(folder / "result.json", result)
            with self.assertRaisesRegex(ValueError, "tool access"):
                _audit_model_evidence([str(folder)], root, "unit-test")


if __name__ == "__main__":
    unittest.main()
