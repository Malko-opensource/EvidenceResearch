"""Independent evaluator contract checks, excluded from final agent comparison."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
spec = importlib.util.spec_from_file_location("fixed_evaluation", EVAL / "fixed_validator.py")
evaluator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluator)


class FixedEvaluationTests(unittest.TestCase):
    def test_independent_known_numeric_examples(self):
        rows = [{"group": "x", "value": str(10**12 + d), "weight": "1"} for d in (-2, 0, 2)]
        result = evaluator.weighted_reference(rows)
        self.assertEqual(result["groups"]["x"]["mean"], 10**12)
        self.assertAlmostEqual(result["groups"]["x"]["variance"], 8 / 3)
        result = evaluator.window_reference([{"timestamp": "0", "value": "2"},
                                             {"timestamp": "3", "value": "8"}])
        self.assertEqual(result["samples"][-1], {"timestamp": 3.0, "count": 1, "mean": 8.0})

    def test_whole_row_dedup_cannot_pass(self):
        rows = [{"event_id": "e1", "group": "a", "timestamp": "1", "value": "10"},
                {"event_id": "e1", "group": "a", "timestamp": "2", "value": "20"}]
        self.assertEqual(evaluator.event_reference(rows),
                         {"groups": {"a": {"count": 1, "mean": 20.0}}, "rejected": 0, "duplicates": 1})
        completed = subprocess.run([sys.executable, "-I", str(EVAL / "fixed_validator.py"),
                                    "--worker", str(EVAL / "tasks/M1/solution.py")],
                                   input=json.dumps(rows), text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(evaluator.matches(json.loads(completed.stdout), evaluator.event_reference(rows)))

    def test_worker_accepts_hashed_blob_extension(self):
        parent = ROOT / "tests" / ".runs"
        parent.mkdir(exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="evaluator-", dir=parent)).resolve()
        try:
            source = temporary / "preserved.blob"
            source.write_text("def summarize(rows):\n    return {'groups': {'a': 2.0}}\n", encoding="utf-8")
            completed = subprocess.run([sys.executable, "-I", str(EVAL / "fixed_validator.py"),
                                        "--worker", str(source)], input="[]", text=True, capture_output=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout), {"groups": {"a": 2.0}})
        finally:
            self.assertTrue(temporary.is_relative_to(parent.resolve()))
            shutil.rmtree(temporary)

    def test_numeric_claims_and_extra_fields_are_not_accepted(self):
        self.assertFalse(evaluator.matches({"groups": {}, "rejected": 0, "success": True},
                                          {"groups": {}, "rejected": 0}))
        self.assertFalse(evaluator.matches(float("nan"), 0.0))
        self.assertFalse(evaluator.matches(True, 1))

    def test_real_development_bundle_passes_and_prior_failure_is_preserved(self):
        parent = ROOT / "tests" / ".runs"
        parent.mkdir(exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="bundle-", dir=parent)).resolve()
        try:
            for task_id, expected_pass in (("D", True), ("M_PRIOR", False)):
                job = temporary / task_id
                job.mkdir()
                for name in ('solution.py', 'input.csv'):
                    shutil.copyfile(EVAL / 'tasks' / task_id / name, job / name)
                completed = subprocess.run([sys.executable, str(EVAL / 'task.py'), task_id],
                                           cwd=job, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                artifact_names = ('solution.py', 'input.csv', 'result.json', 'invocations.jsonl')
                bundle = {'registration': {'spec': {'task_id': task_id}},
                          'artifacts': {name: str(job / name) for name in artifact_names}}
                (job / 'bundle.json').write_text(json.dumps(bundle), encoding='utf-8')
                completed = subprocess.run([sys.executable, str(EVAL / 'fixed_validator.py'), str(job / 'bundle.json')],
                                           capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertEqual(result['metrics']['pass_rate'] == 1.0, expected_pass)
                self.assertFalse(result['details']['reported_run_metrics_used'])
        finally:
            self.assertTrue(temporary.is_relative_to(parent.resolve()))
            shutil.rmtree(temporary)


if __name__ == "__main__":
    unittest.main()
