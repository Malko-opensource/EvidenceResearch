"""Proposal fixtures exercise callback contracts; no actual LLM comparison claims."""
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.comparison_arms import ImprovedArm
from evidence_research.model import PreregisteredResourcesExhausted
from evidence_research.evaluation import _audit_model_evidence, _audit_telemetry, adjudicate_numeric_review
from evidence_research.store import Store, atomic_json, fingerprint, sha256_file
from evidence_research.tasks import TASK_VERSION, split_manifest, task_data
from evidence_research.report_contract import verify_report_contract


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
        result = verify_report_contract(Path(response["report_contract_path"]), arm_output=self.output,
            spec=spec, verification=json.loads((selected / "verification.json").read_text(encoding="utf-8")), selected_run_dir=selected)
        self.assertTrue(result["valid"], result["reasons"])
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
            judgments = []
            for item in inventory["items"]:
                hint = indexed[item["claim_id"]]
                if hint["metric"]:
                    judgment = {"claim_id": item["claim_id"], "kind": "measured", "metric": hint["metric"],
                        "run_dir": hint["run_dir"], "rationale": "Fixture independent verifier recomputes metric from artifacts"}
                else:
                    # These fixtures contain registered literal config/provenance
                    # and a frozen source synopsis, not simulated performance.
                    judgment = {"claim_id": item["claim_id"], "kind": "method", "source_path": hint["source_path"],
                        "source_sha256": hint["source_sha256"], "rationale": "Fixture literal/source metadata independently classified against companion"}
                judgments.append(judgment)
            adjudicate_numeric_review(inventory_path, judgments, review_path, reviewer_role="independent_verifier")
        response = ImprovedArm(self.factory([proposal(2)]), independent_reviewer)(public_payload(), self.output)
        counters, _ = _audit_telemetry(response, self.output)
        self.assertTrue(counters["whole_report_numeric_audit_complete"])
        self.assertFalse(response["independent_review_pending"])
        self.assertEqual(counters["unsupported_claims"], 0)
        self.assertEqual(response["model_execution_kind"], "simulation_fixture")
        self.assertTrue((self.output / "companion-review.json").exists())

    def test_malformed_and_duplicate_proposals_receive_corrective_feedback(self):
        responses = [{"candidates": "invalid shape"}, proposal(1), proposal(1), proposal(2)]
        result = ImprovedArm(self.factory(responses))(public_payload(calls=4), self.output)
        self.assertEqual(result["stop_reason"], "preregistered_public_target_met")
        prompts = self.providers[0].prompts
        self.assertIn("correct", prompts[1]["proposal_feedback"][0]["rejected"][0]["reason"])
        self.assertEqual(prompts[3]["proposal_feedback"][2]["duplicate_configs"], [{"degree": 1, "alpha": 0.0}])
        self.assertEqual(prompts[3]["actual_cpu_attempts_to_date"], 1)
        self.assertEqual(len(Store(self.output / "research").list_runs()), 2)

    def test_explicit_no_justified_hypothesis_stops_after_verified_evidence(self):
        payload = public_payload(calls=4)
        payload["resource_envelope"].pop("success_criterion")
        result = ImprovedArm(self.factory([proposal(1), {"candidates": [], "stop_reason": "No justified fresh candidate from available evidence."}]))(payload, self.output)
        self.assertTrue(result["stop_reason"].startswith("model_no_justified_new_experiment:"))
        self.assertEqual(len(self.providers[0].prompts), 2)

    def test_registered_cpu_limit_stops_before_extra_model_call(self):
        payload = public_payload(calls=4)
        payload["resource_envelope"]["actual_cpu_executions_per_unit"] = 1
        with self.assertRaises(PreregisteredResourcesExhausted):
            ImprovedArm(self.factory([proposal(1)]))(payload, self.output)
        receipt = json.loads((self.output / "registered-resource-exhaustion.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["stop_reason"], "preregistered_per_unit_cpu_resources_exhausted")
        self.assertEqual(len(self.providers[0].prompts), 1)

    def test_registered_resource_budget_exhaustion_retains_best(self):
        with self.assertRaises(PreregisteredResourcesExhausted):
            ImprovedArm(self.factory([proposal(1)]))(public_payload(calls=1), self.output)
        receipt = json.loads((self.output / "registered-resource-exhaustion.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["stop_reason"], "preregistered_per_unit_proposal_resources_exhausted")
        self.assertEqual(len(self.providers[0].prompts), 1)
        self.assertEqual(len(Store(self.output / "research").list_runs()), 1)


if __name__ == "__main__":
    unittest.main()
