"""Proposal fixtures exercise callback contracts; no actual LLM comparison claims."""
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.comparison_arms import ImprovedArm
from evidence_research.evaluation import _audit_model_evidence, _audit_telemetry, adjudicate_numeric_review
from evidence_research.store import Store, atomic_json, fingerprint, sha256_file
from evidence_research.tasks import TASK_VERSION, split_manifest, task_data


def public_payload(calls=3):
    data = task_data("dev-quadratic", 7)
    return {"arm": "C", "model_id": "fixture-model", "baseline_provenance": None,
        "resource_envelope": {"proposal_calls_per_unit": calls, "reasoning_effort": None,
            "device": "cpu", "tools": ["trusted polynomial ridge"], "network": False,
            "success_criterion": {"direction": "min", "threshold": 0.03}},
        "public_task": {"task_id": "dev-quadratic", "seed": 7, "task_version": TASK_VERSION,
            "objective": "minimize validation MSE", "metric": "validation_mse",
            "allowed_config": {"degree": "1..8", "alpha": "0..100"},
            "task_bundle": {"train": data["train"], "validation": data["validation"],
                            "split_manifest": split_manifest("dev-quadratic", 7)}}}


def proposal(degree, alpha=0):
    return {"candidates": [{"hypothesis": f"Fixture polynomial degree {degree}",
        "config": {"degree": degree, "alpha": alpha},
        "assessment": {"relevance": 1.0, "evidence_strength": 0.3, "uncertainty": 0.5,
                       "normalized_cost": 0.0, "rationale": "Explicit simulation fixture"},
        "selection_reason": "Explicit simulation fixture"}], "stop_reason": None}


class FixtureProvider:
    execution_kind = "simulation_fixture"
    def __init__(self, evidence_dir, model, reasoning_effort=None, public_dir=None, responses=None):
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.model = model
        self.responses = responses
        self.last_evidence = None
        self.prompts = []

    def complete(self, prompt, *, call_id, json_response=False):
        self.prompts.append(json.loads(prompt))
        response = self.responses.pop(0)
        folder = self.evidence_dir / call_id
        folder.mkdir()
        atomic_json(folder / "request.json", {"model": self.model, "prompt": prompt})
        atomic_json(folder / "response.json", response)
        self.last_evidence = {"execution_kind": self.execution_kind, "fingerprint": fingerprint(prompt),
            "usage": {"input_tokens": 1, "output_tokens": 1}, "wall_seconds": 0.0,
            "evidence_record": {"directory": str(folder), "result_sha256": "fixture-only"}}
        atomic_json(folder / "result.json", {**self.last_evidence, "model": self.model,
            "status": "completed", "returncode": 0})
        return response


class ImprovedCallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "C"
        self.providers = []

    def tearDown(self):
        self.temp.cleanup()

    def factory(self, responses):
        def create(**kwargs):
            provider = FixtureProvider(**kwargs, responses=responses)
            self.providers.append(provider)
            return provider
        return create

    def test_public_bundle_memory_and_cached_resume(self):
        arm = ImprovedArm(self.factory([proposal(1), proposal(2)]))
        payload = public_payload()
        response = arm(payload, self.output)
        self.assertEqual(response["model_execution_kind"], "simulation_fixture")
        self.assertTrue(response["independent_review_pending"])
        selected = Path(response["selected_run_dir"])
        spec = json.loads((selected / "registered_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["config"], {"degree": 2, "alpha": 0.0})
        self.assertEqual(spec["task_bundle"], payload["public_task"]["task_bundle"])
        self.assertFalse((selected / "test.json").exists())
        prompts = self.providers[0].prompts
        self.assertEqual(prompts[1]["verified_memory"][0]["outcome"], "failure")
        self.assertIn("validation_mse", prompts[1]["verified_memory"][0]["metrics"])
        self.assertEqual(len(prompts), 2)
        cached = arm(payload, self.output)
        self.assertTrue(cached["resumed_without_execution"])
        self.assertEqual(len(self.providers), 1)
        counters, _ = _audit_telemetry(response, self.output)
        self.assertFalse(counters["whole_report_numeric_audit_complete"])
        self.assertEqual(counters["verified_memory_hits"], 1)
        self.assertEqual(counters["duplicate_executions"], 0)
        with self.assertRaises(ValueError):
            _audit_model_evidence(response["model_evidence_dirs"], self.output, "fixture-model")

    def test_no_private_payload_and_no_fabricated_target(self):
        payload = public_payload()
        payload["public_task"]["private_file"] = "must never be read"
        with self.assertRaises(ValueError):
            ImprovedArm(self.factory([]))(payload, self.output)
        self.assertEqual(self.providers, [])

    def test_independent_report_adjudication_is_injected(self):
        def independent_reviewer(inventory_path, review_path):
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            hints = json.loads((inventory_path.parent / "claim-evidence-hints.json").read_text(encoding="utf-8"))["hints"]
            indexed = {item["claim_id"]: item for item in hints}
            judgments = [{"claim_id": item["claim_id"], "kind": "measured",
                "metric": indexed[item["claim_id"]]["metric"], "run_dir": indexed[item["claim_id"]]["run_dir"],
                "rationale": "Fixture independent verifier recomputes metric from artifacts"}
                for item in inventory["items"]]
            adjudicate_numeric_review(inventory_path, judgments, review_path, reviewer_role="independent_verifier")
        response = ImprovedArm(self.factory([proposal(2)]), independent_reviewer)(public_payload(), self.output)
        counters, _ = _audit_telemetry(response, self.output)
        self.assertTrue(counters["whole_report_numeric_audit_complete"])
        self.assertFalse(response["independent_review_pending"])
        self.assertEqual(counters["unsupported_claims"], 0)
        self.assertEqual(response["model_execution_kind"], "simulation_fixture")

    def test_registered_resource_budget_exhaustion_retains_best(self):
        response = ImprovedArm(self.factory([proposal(1)]))(public_payload(calls=1), self.output)
        self.assertEqual(response["stop_reason"], "preregistered_per_unit_proposal_resources_exhausted")
        self.assertEqual(len(self.providers[0].prompts), 1)
        self.assertEqual(len(Store(self.output / "research").list_runs()), 1)


if __name__ == "__main__":
    unittest.main()
