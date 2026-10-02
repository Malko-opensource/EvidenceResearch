"""Future-source contract tests: real CPU evidence, simulated provider responses.

No test invokes a model or estimates comparative research performance.
"""
import copy
from collections import deque
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research.arms import (AllowlistedExperimentTool, UpstreamArm, UpstreamCodexBridge,
    literature_from_envelope, recovery_summary)
from evidence_research.baseline import verify_literature_review, make_literature_protocol
from evidence_research.comparison_arms import compact_memory_record, provider_resource_observation, ImprovedArm
from evidence_research.engine import Engine
from evidence_research.model import PreregisteredResourcesExhausted
from evidence_research.store import EvidenceError, Store, atomic_json, execution_fingerprint, fingerprint, sha256_file
from evidence_research.tasks import make_spec, run_task
from evidence_research.verifier import verify
from tests.test_comparison_arms import FixtureProvider, proposal, public_payload


def corpus():
    # Resolve the corpus inside this version; a missing snapshot must fail
    # rather than borrowing mutable files from an ancestor project.
    path = Path(__file__).resolve().parents[1] / "references" / "task_literature_v2.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert fingerprint(value["records"]) == value["records_sha256"]
    return value["records"]


class CompactContextTests(unittest.TestCase):
    def test_registered_five_record_snapshot_is_authoritative_and_detached(self):
        papers = corpus()
        envelope = {"literature_snapshot": papers, "literature_snapshot_sha256": fingerprint(papers)}
        selected = literature_from_envelope(envelope, required_papers=5)
        self.assertEqual(len(selected), 5)
        self.assertEqual(selected, papers)
        selected[0]["title"] = "Caller-local mutation"
        self.assertNotEqual(selected[0]["title"], papers[0]["title"])
        with self.assertRaisesRegex(ValueError, "does not match"):
            literature_from_envelope({**envelope, "literature_snapshot_sha256": "changed"})
        with self.assertRaisesRegex(ValueError, "enough distinct"):
            literature_from_envelope({"literature_snapshot": papers[:3]}, required_papers=5)

    def test_duplicate_ids_and_urls_cannot_inflate_literature_count(self):
        papers = corpus()
        for field in ("id", "url"):
            altered = copy.deepcopy(papers)
            altered[-1][field] = altered[0][field]
            with self.assertRaisesRegex(ValueError, "Duplicate literature"):
                literature_from_envelope({"literature_snapshot": altered}, required_papers=5)
        altered = copy.deepcopy(papers)
        altered[-1]["id"] = "1910.02373v9"
        altered[-1]["url"] = "https://arxiv.org/pdf/1910.02373v9.pdf"
        with self.assertRaisesRegex(ValueError, "Duplicate literature"):
            literature_from_envelope({"literature_snapshot": altered}, required_papers=5)

    def test_host_review_checks_original_entries_and_source_diagnostics_without_full_paper_read_claim(self):
        papers = corpus()
        review = [{"arxiv_id": paper["id"], "full_text": paper["text"], "summary": "Fixture-authored summary"} for paper in papers]
        checked = verify_literature_review(review, papers, 5)
        self.assertTrue(checked["valid"], checked["reasons"])
        self.assertEqual(checked["distinct_verified_source_records"], 5)
        self.assertIn("not proof of full-paper reading", checked["scope"])
        duplicate = verify_literature_review(review[:3] + review[:2], papers, 5)
        self.assertTrue(duplicate["valid"], duplicate["reasons"])
        self.assertEqual(duplicate["duplicate_source_entries"], 2)
        self.assertEqual(duplicate["original_review_entry_count"], 5)
        self.assertEqual(duplicate["distinct_verified_source_records"], 3)
        missing = verify_literature_review([{**review[0], "arxiv_id": "missing-source"}], papers, 1)
        self.assertFalse(missing["valid"])
        self.assertFalse(missing["entries"][0]["source_membership"])
        changed = verify_literature_review([{**review[0], "full_text": "Paper ID not found"}], papers, 1)
        self.assertFalse(changed["valid"])

    def test_actual_cpu_memory_compaction_retains_criteria_and_original_hashes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            envelope = {"device": "cpu", "literature_snapshot": corpus(), "large_tool_contract": "source contract " * 600}
            spec = make_spec("dev-quadratic", 7, {"degree": 2, "alpha": 0}, resource_envelope=envelope)
            engine = Engine(root, run_task, verify)
            engine.store.init_goal({"objective": "Compaction contract validation", "memory_query": "dev-quadratic"})
            run = engine.progress(spec)
            item = engine.store.search("dev-quadratic")[0]
            before = fingerprint(item)
            compact = compact_memory_record(item)
            self.assertEqual(before, fingerprint(item))
            self.assertNotIn("resource_envelope", compact["conditions"])
            self.assertEqual(compact["conditions"]["criterion_sha256"], fingerprint(spec["criterion"]))
            self.assertEqual(compact["conditions"]["execution_fingerprint"], execution_fingerprint(spec))
            self.assertEqual(compact["evidence_hash"], item["evidence_hash"])
            for reference in compact["original_evidence"]:
                self.assertEqual(reference["sha256"], sha256_file(reference["path"]))
            self.assertLess(len(json.dumps(compact)), len(json.dumps(item["conditions"])))
            changed = copy.deepcopy(spec)
            changed["criterion"] = {"direction": "min", "threshold": 100}
            changed["hypothesis"] = "Renamed; original execution is already complete"
            self.assertEqual(execution_fingerprint(changed), execution_fingerprint(spec))
            self.assertNotEqual(fingerprint(changed["criterion"]), compact["conditions"]["criterion_sha256"])
            atomic_json(Path(run["run_dir"]) / "registered_spec.json", changed)
            with self.assertRaises(EvidenceError):
                compact_memory_record(item)

    def test_callback_injects_registered_corpus_once_and_separate_cost_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            providers = []
            responses = [proposal(1), proposal(2)]
            def factory(**kwargs):
                provider = FixtureProvider(**kwargs, responses=responses)
                providers.append(provider)
                return provider
            payload = public_payload()
            payload["resource_envelope"].update(literature_snapshot=corpus(), literature_snapshot_sha256=fingerprint(corpus()))
            output = Path(temporary) / "C"
            result = ImprovedArm(factory)(payload, output)
            second = providers[0].prompts[1]
            self.assertEqual(second["frozen_literature"], corpus())
            memory = second["verified_memory"][0]
            self.assertNotIn("literature_snapshot", memory["conditions"])
            self.assertNotIn("resource_envelope", memory["conditions"])
            self.assertEqual(len(memory["original_evidence"]), 4)
            self.assertEqual(second["observed_resources"]["kind"], "simulation_fixture")
            self.assertIsNone(second["observed_resources"]["token_usage"])
            self.assertEqual(second["observed_resources"]["completed_provider_calls"], 1)
            observation = json.loads((output / "resource-observations" / "improved-0001.json").read_text(encoding="utf-8"))
            self.assertEqual(observation["serialization"]["unit"], "UTF-8 bytes")
            companion = json.loads(Path(result["report_contract_path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(companion["references"]), 5)
            self.assertEqual(len(companion["references"]), len({item["url"] for item in companion["references"]}))

    def test_raw_resource_unknown_failure_and_simulation_usage_are_not_zero_cost(self):
        # Synthetic raw records exercise bookkeeping only, not actual cost claims.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed, failed = root / "completed", root / "failed"
            completed.mkdir(); failed.mkdir()
            atomic_json(completed / "result.json", {"status": "completed", "usage": {"input_tokens": 7, "output_tokens": 3}, "wall_seconds": 2})
            atomic_json(failed / "result.json", {"status": "failed", "usage": {}, "wall_seconds": 4})
            trace = [{"call_id": "completed", "status": "completed", "evidence_dir": str(completed)},
                     {"call_id": "failed", "status": "failed", "evidence_dir": str(failed)}]
            audit = {"valid": True, "failed_attempts": 1, "unknown_failed_token_usage": True,
                     "failed_token_usage": {"input_tokens": 0, "output_tokens": 0}}
            resource = provider_resource_observation(trace, [], actual=True, failed_audit=audit)
            self.assertIsNone(resource["token_usage"])
            self.assertFalse(resource["tokens_known"])
            self.assertEqual(resource["wall_seconds"], 6)
            self.assertEqual(resource["completed_token_usage_lower_bound"], {"input_tokens": 7, "output_tokens": 3})
            self.assertEqual(resource["provider_attempts"], 2)
            fixture = provider_resource_observation(trace, [], actual=False, failed_audit=audit)
            self.assertIsNone(fixture["token_usage"])
            self.assertIsNone(fixture["wall_seconds"])

    def test_recovery_count_excludes_failed_hypotheses_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            providers = []
            responses = [{"candidates": "invalid shape"}, proposal(1), proposal(1), proposal(2)]
            def factory(**kwargs):
                provider = FixtureProvider(**kwargs, responses=responses); providers.append(provider); return provider
            output = Path(temporary) / "C"
            ImprovedArm(factory)(public_payload(calls=4), output)
            telemetry = json.loads((output / "telemetry.json").read_text(encoding="utf-8"))
            self.assertEqual(telemetry["recovered_errors"], 1)
            self.assertEqual(telemetry["completed_verified_retries"], 0)
            self.assertEqual(telemetry["failed_hypothesis_retries"], 0)
            self.assertEqual(telemetry["duplicate_executions"], 0)
            self.assertEqual(telemetry["recovery_evidence"][0]["causes"][0]["call_id"], "improved-0000")
            self.assertEqual(telemetry["recovery_evidence"][0]["success"]["call_id"], "improved-0001")
            self.assertEqual(telemetry["unique_verified_memory_records"], 1)
            self.assertIn("not unique retrievals or causal improvement", telemetry["verified_memory_hits_scope"])
            self.assertEqual(len(Store(output / "research").list_runs()), 2)
            self.assertEqual(recovery_summary([{"kind": "failed_hypothesis"}, {"kind": "verified_cpu_success"}])["recovered_errors"], 0)

    def test_explicit_failed_hypothesis_retry_is_not_runtime_error_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            class RetryProvider(FixtureProvider):
                def complete(self, prompt, *, call_id, json_response=False):
                    public = json.loads(prompt)
                    if public["verified_memory"]:
                        self.responses[0]["candidates"][0].update(
                            retry_of=public["verified_memory"][0]["run_id"],
                            retry_reason="Change polynomial degree while keeping the fixed split; compare actual validation evidence.")
                    return super().complete(prompt, call_id=call_id, json_response=json_response)
            def factory(**kwargs):
                return RetryProvider(**kwargs, responses=[proposal(1), proposal(2)])
            output = Path(temporary) / "C"
            ImprovedArm(factory)(public_payload(), output)
            telemetry = json.loads((output / "telemetry.json").read_text(encoding="utf-8"))
            self.assertEqual(telemetry["recovered_errors"], 0)
            self.assertEqual(telemetry["completed_verified_retries"], 1)
            self.assertEqual(telemetry["failed_hypothesis_retries"], 1)
            self.assertEqual(telemetry["hypothesis_retry_evidence"][0]["prior_hypothesis_outcome"], "failure")

    def test_cpu_budget_exhaustion_is_distinct_and_completed_replay_works(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def spec_factory(config):
                return make_spec("dev-quadratic", 7, config)
            tool = AllowlistedExperimentTool(root / "first", spec_factory, max_cpu_executions=1)
            code = "CONFIG = {'degree': 2, 'alpha': 0}"
            tool(code)
            with self.assertRaises(PreregisteredResourcesExhausted):
                tool("CONFIG = {'degree': 3, 'alpha': 0}")
            replay = AllowlistedExperimentTool(root / "resume", spec_factory, prior_records=tool.records, max_cpu_executions=1)
            self.assertEqual(json.loads(replay(code))["config"], {"degree": 2, "alpha": 0.0})
            self.assertEqual(len(replay.completed), 1)

    def test_model_budget_does_not_call_provider_and_identical_cache_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            class Provider:
                model = "fixture-model"
                def complete(self, *args, **kwargs):
                    raise AssertionError("No new provider call is allowed at the declared budget")
            root = Path(temporary)
            bridge = UpstreamCodexBridge(Provider(), root, max_model_calls=1)
            bridge.prior_attempts = 1
            with self.assertRaises(PreregisteredResourcesExhausted):
                bridge("fixture-model", "prompt", "system")
            from evidence_research.arms import TOOL_CONTRACT
            import hashlib
            request = "UPSTREAM SYSTEM PROMPT:\nsystem\n\nUPSTREAM USER PROMPT:\nprompt\n\nSHARED HOST EXECUTION CONTRACT:\n" + TOOL_CONTRACT
            bridge.replay[hashlib.sha256(request.encode()).hexdigest()] = deque([{
                "evidence_dir": "fixture-only", "model_evidence": {"classification": "fixture"}, "response": "cached fixture"}])
            self.assertEqual(bridge("fixture-model", "prompt", "system"), "cached fixture")
            self.assertTrue(bridge.calls[0]["reused_completed_evidence"])
            with self.assertRaises(PreregisteredResourcesExhausted):
                bridge("fixture-model", "prompt", "system")

    def test_upstream_receives_actual_registered_snapshot_and_preserves_budget_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = public_payload()
            payload["arm"] = "B"
            payload["resource_envelope"].update(actual_cpu_executions_per_unit=3,
                upstream_settings={"num_papers_lit_review": 5}, literature_snapshot=corpus(), literature_snapshot_sha256=fingerprint(corpus()),
                literature_protocol=make_literature_protocol(5, 5))
            def factory(**kwargs):
                return FixtureProvider(**kwargs, responses=[])
            with patch("evidence_research.arms.run_upstream_baseline", return_value={"status": "failure", "error": "PreregisteredResourcesExhausted: fixture allowance consumed"}) as upstream:
                with self.assertRaises(PreregisteredResourcesExhausted):
                    UpstreamArm(factory)(payload, Path(temporary) / "B")
            self.assertEqual(upstream.call_args.kwargs["literature"], corpus())
            self.assertEqual(upstream.call_args.args[4]["num_papers_lit_review"], 5)
            self.assertEqual(len(list(Path(temporary).rglob("request.json"))), 0)


if __name__ == "__main__":
    unittest.main()
