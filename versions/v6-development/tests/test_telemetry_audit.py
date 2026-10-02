"""Counter attacks use actual trusted CPU tasks and labeled model fixtures.

No real model calls, withheld owner outcomes or framework-effect claims occur.
"""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from evidence_research.arms import AllowlistedExperimentTool, recovery_summary
from evidence_research.comparison_arms import ImprovedArm
from evidence_research.evaluation import _audit_telemetry, _audit_research_counters
from evidence_research.tasks import make_spec, sha256_file, write_json
from tests.test_comparison_arms import FixtureProvider, proposal, public_payload


class ResearchCounterAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def improved(self):
        providers = []

        class RetryFixture(FixtureProvider):
            def complete(self, prompt, *, call_id, json_response=False):
                memory = json.loads(prompt)["verified_memory"]
                if memory:
                    candidate = self.responses[0]["candidates"][0]
                    candidate["retry_of"] = memory[0]["run_id"]
                    candidate["retry_reason"] = "Changed polynomial degree under the same fixed data and evaluator."
                return super().complete(prompt, call_id=call_id, json_response=json_response)

        def factory(**kwargs):
            provider = RetryFixture(**kwargs, responses=[{"candidates": "invalid shape"}, proposal(1), proposal(2)])
            providers.append(provider);return provider

        output = self.root / "C"
        response = ImprovedArm(factory)(public_payload(calls=3), output)
        telemetry_path = Path(response["telemetry_evidence_path"])
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        return output, response, telemetry, providers[0]

    def test_protocol_recovery_and_failed_hypothesis_retry_have_separate_evidence(self):
        output, response, telemetry, provider = self.improved()
        counters, evidence = _audit_telemetry(response, output)
        self.assertEqual(counters["recovered_errors"], 1)
        self.assertEqual(counters["completed_verified_retries"], 1)
        self.assertEqual(counters["failed_hypothesis_retries"], 1)
        self.assertEqual(counters["verified_memory_hits"], 1)
        self.assertEqual(counters["unique_verified_memory_records"], 1)
        self.assertEqual(counters["duplicate_executions"], 0)
        self.assertEqual(evidence["secondary_counter_audit"]["status"], "independently_recomputed_from_fixed_host_ledgers")
        self.assertEqual(telemetry["recovery_evidence"][0]["causes"][0]["kind"], "protocol_error")
        self.assertEqual(provider.prompts[-1]["verified_memory"][0]["outcome"], "failure")

    def test_false_common_aggregates_and_evidence_are_rejected(self):
        output, _, telemetry, _ = self.improved()
        for field in ("duplicate_executions", "recovered_errors", "completed_verified_retries",
                      "failed_hypothesis_retries", "verified_memory_hits", "unique_verified_memory_records"):
            altered = deepcopy(telemetry);altered[field] += 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "counters differ"):
                _audit_research_counters(altered, output)
        altered = deepcopy(telemetry);altered["recovery_evidence"] = []
        with self.assertRaisesRegex(ValueError, "recovery episodes"):_audit_research_counters(altered, output)
        altered = deepcopy(telemetry);altered["hypothesis_retry_evidence"] = []
        with self.assertRaisesRegex(ValueError, "retry evidence"):_audit_research_counters(altered, output)

    def test_memory_conditions_and_exact_four_original_sources_are_checked(self):
        output, _, telemetry, _ = self.improved()
        request_path = output / "model/improved-0002/request.json"
        original = json.loads(request_path.read_text(encoding="utf-8"))
        for field in ("registered_criterion", "conditions", "original_evidence", "evidence_hash"):
            request = deepcopy(original);payload = json.loads(request["prompt"])
            memory = payload["verified_memory"][0]
            if field == "registered_criterion":memory[field]["threshold"] = 10.0
            elif field == "conditions":memory[field]["resource_envelope_sha256"] = "0" * 64
            elif field == "original_evidence":memory[field].pop()
            else:memory[field] = "0" * 64
            request["prompt"] = json.dumps(payload);write_json(request_path, request)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "compact memory conditions"):
                _audit_research_counters(telemetry, output)
        write_json(request_path, original)

    def test_criterion_failure_cannot_be_relabelled_as_success_even_in_both_ledgers(self):
        output, _, telemetry, _ = self.improved()
        path = output / "research-audit.json";audit = json.loads(path.read_text(encoding="utf-8"))
        failure = next(run for run in audit["runs"] if run["outcome"] == "failure")
        with closing(sqlite3.connect(output / "research/research.sqlite3")) as db:
            # Simulate a filesystem-authorized attacker rewriting both copies;
            # ordinary SQL writes are already blocked by this immutable trigger.
            db.execute("DROP TRIGGER immutable_completed_run")
            db.execute("UPDATE runs SET outcome='success' WHERE run_id=?", (failure["run_id"],));db.commit()
        failure["outcome"] = "success";write_json(path, audit)
        with self.assertRaisesRegex(ValueError, "recomputed criterion"):_audit_research_counters(telemetry, output)

    def test_store_event_chain_is_recomputed_without_writable_store_access(self):
        output, _, telemetry, _ = self.improved()
        path = output / "research-audit.json";audit = json.loads(path.read_text(encoding="utf-8"))
        audit["events"][0]["event_hash"] = "0" * 64
        with closing(sqlite3.connect(output / "research/research.sqlite3")) as db:
            db.execute("DROP TRIGGER no_event_update")
            db.execute("UPDATE events SET event_hash=? WHERE sequence=?", ("0" * 64, audit["events"][0]["sequence"]));db.commit()
        write_json(path, audit)
        with self.assertRaisesRegex(ValueError, "event chain"):_audit_research_counters(telemetry, output)

    def test_valid_failed_hypothesis_has_no_runtime_error_recovery(self):
        output = self.root / "C"
        factory = lambda **kwargs: FixtureProvider(**kwargs, responses=[proposal(1), proposal(2)])
        response = ImprovedArm(factory)(public_payload(), output)
        counters, _ = _audit_telemetry(response, output)
        self.assertEqual(counters["recovered_errors"], 0)
        self.assertEqual(counters["completed_verified_retries"], 0)
        self.assertEqual(counters["failed_hypothesis_retries"], 0)
        self.assertEqual(counters["verified_memory_hits"], 1)

    def test_upstream_rejection_and_duplicate_identity_are_independently_counted(self):
        output = self.root / "B";output.mkdir()
        spec_factory = lambda config: make_spec("dev-quadratic", 7, config, model="fixture-model")
        tool = AllowlistedExperimentTool(output / "attempts/attempt-0000/experiments", spec_factory)
        tool("import os")
        tool("CONFIG = {'degree':2, 'alpha':0.0}")
        tool("run_candidate({'degree':2, 'alpha':0.0})")
        events_path = tool.events_path
        timeline = []
        for event in tool.records:
            reference = {"tool_events_path": str(events_path), "tool_events_sha256": sha256_file(events_path),
                         "invocation": event["invocation"], "code_sha256": event["code_sha256"], "run_dir": event.get("run_dir")}
            if event["status"] == "rejected_code":timeline.append({**reference, "kind": "protocol_error", "reason": event["error"]})
            elif event.get("actual_task_executed"):timeline.append({**reference, "kind": "verified_cpu_success"})
        telemetry = {"provenance": "trusted_host_audit", "duplicate_executions": 1, "unsupported_claims": 0,
            "verified_memory_hits": 0, "unique_verified_memory_records": 0,
            "completed_verified_retries": 0, "failed_hypothesis_retries": 0,
            "verified_memory_hits_scope": "No verified Store memory exposed by upstream adapter.",
            "hypothesis_retry_scope": "No explicit registered retry_of records in upstream adapter.",
            "duplicate_execution_identity": "Full registered task/resource/config identity.",
            "sources": [{"path": str(events_path), "sha256": sha256_file(events_path)}], **recovery_summary(timeline)}
        path = output / "telemetry.json";write_json(path, telemetry)
        counters, _ = _audit_telemetry({"telemetry_evidence_path": str(path)}, output)
        self.assertEqual(counters["duplicate_executions"], 1)
        self.assertEqual(counters["recovered_errors"], 1)
        altered = deepcopy(telemetry);altered["verified_memory_hits"] = 1
        with self.assertRaisesRegex(ValueError, "counters differ"):_audit_research_counters(altered, output)


if __name__ == "__main__":unittest.main()
