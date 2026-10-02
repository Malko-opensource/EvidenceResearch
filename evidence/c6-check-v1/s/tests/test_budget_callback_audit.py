"""Actual C control-flow/CPU budget audit with labeled provider fixtures.

These exercise the concrete callback, not a mocked scorer or real model trial.
"""
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.comparison_arms import ImprovedArm
from evidence_research.evaluation import _failure_score
from evidence_research.model import PreregisteredResourcesExhausted
from evidence_research.store import Store, sha256_file
from evidence_research.verifier import verify
from tests.test_comparison_arms import FixtureProvider, proposal, public_payload


class ActualImprovedBudgetBranchTests(unittest.TestCase):
    def check_branch(self, *, model_limit, cpu_limit, expected_reason):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary).resolve() / "C";providers = []
            payload = public_payload(calls=model_limit)
            payload["resource_envelope"].pop("success_criterion")
            payload["resource_envelope"]["actual_cpu_executions_per_unit"] = cpu_limit

            def factory(**kwargs):
                provider = FixtureProvider(**kwargs, responses=[proposal(1)])
                providers.append(provider);return provider

            callback = ImprovedArm(factory)
            with self.assertRaises(PreregisteredResourcesExhausted) as caught:callback(payload, output)
            runs = Store(output / "research").list_runs()
            self.assertEqual(len(runs),1)
            self.assertIsNotNone(Store(output / "research").state()["best"])
            run = runs[0];folder = Path(run["run_dir"])
            result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
            self.assertTrue(verify(run["spec"],result,folder)["valid"])
            tracked = [folder / name for name in ("registered_spec.json","result.json","verification.json","manifest.json")]
            tracked.extend(path for path in (output / "model").rglob("*") if path.is_file())
            before = {str(path):sha256_file(path) for path in tracked}
            request_count = sum(len(provider.prompts) for provider in providers)
            self.assertEqual(request_count,1)
            score = _failure_score({"unit_id":"actual-callback-fixture"},"C",output,caught.exception)
            self.assertEqual(score["status"],"registered_resources_exhausted")
            self.assertFalse(score["task_success"])
            self.assertIsNone(score["provider_calls"])
            self.assertTrue(score["evidence"]["failure_files"])
            # A terminal budget status stays terminal on resume. The original
            # verified best is preserved for later authorized research work.
            with self.assertRaises(PreregisteredResourcesExhausted):callback(payload,output)
            self.assertEqual(sum(len(provider.prompts) for provider in providers),request_count)
            self.assertEqual(len(Store(output / "research").list_runs()),1)
            self.assertEqual(before,{str(path):sha256_file(path) for path in tracked})
            def contains_reason(value):
                if isinstance(value,dict):return value.get("stop_reason") == expected_reason or any(contains_reason(item) for item in value.values())
                if isinstance(value,list):return any(contains_reason(item) for item in value)
                return False
            receipts = [json.loads(path.read_text(encoding="utf-8")) for path in output.glob("*.json")]
            self.assertTrue(any(contains_reason(receipt) for receipt in receipts),
                            "The original exhaustion reason must be durable outside an exception string.")

    def test_model_request_limit_is_terminal_budget_failure_with_preserved_best(self):
        self.check_branch(model_limit=1,cpu_limit=3,expected_reason="preregistered_per_unit_proposal_resources_exhausted")

    def test_cpu_execution_limit_is_terminal_budget_failure_without_extra_model_request(self):
        self.check_branch(model_limit=3,cpu_limit=1,expected_reason="preregistered_per_unit_cpu_resources_exhausted")


if __name__ == "__main__":unittest.main()
