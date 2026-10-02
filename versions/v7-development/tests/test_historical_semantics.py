"""Synthetic provider formats and tiny real CPU contracts; no research/model run."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.engine import Engine
from evidence_research.model import CodexProvider
from evidence_research.report_semantics import (adjudicate_semantic_review, evaluate_predicate,
    prepare_semantic_review, recompute_historical_resources, run_reference, semantic_claim)
from evidence_research.comparison_arms import provider_resource_observation
from evidence_research.store import Store
from evidence_research.tasks import make_spec, run_task, sha256_file, task_data, split_manifest, value_hash, write_json
from evidence_research.verifier import verify
from tests.test_model_request_audit import rich_request


def link(path):
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


class PrefixFixture:
    """Three fabricated transport receipts, with two or one actual CPU fixtures.

    The last request consumes deliberately different synthetic usage so treating
    an original pre-proposal input as a final unit total is detectably incorrect.
    """
    def __init__(self, root, failed_second=False):
        self.root = root
        self.envelope = {"reasoning_effort": "medium", "proposal_calls_per_unit": 10, "actual_cpu_executions_per_unit": 10}
        rows = task_data("dev-quadratic", 353)
        bundle = {"train": rows["train"], "validation": rows["validation"], "split_manifest": split_manifest("dev-quadratic", 353)}
        self.public = {"task_id": "dev-quadratic", "seed": 353, "task_bundle": bundle, "objective": "Format fixture only."}
        self.goal = {"payload_sha256": "f" * 64, "objective": self.public["objective"]}
        write_json(root / "callback-registration.json", {"payload_sha256": "f" * 64, "public_task": self.public,
            "model_id": "fixture-model", "resource_envelope": self.envelope,
            "implementation_sha256": sha256_file(Path(__file__).resolve().parents[1] / "evidence_research/comparison_arms.py"), "fixture_only": True})
        self.engine = Engine(root / "research", run_task, verify)
        self.engine.store.init_goal(self.goal); self.trace = []; self.events = []
        (root / "resource-observations").mkdir()
        self.failed_audit = {"valid": True, "failed_attempts": 0, "unknown_failed_token_usage": False, "failed_token_usage": {"input_tokens": 0, "output_tokens": 0}}
        for ordinal in range(3):
            call = f"improved-{ordinal:04d}"
            runs = self.engine.store.list_runs()
            resources = provider_resource_observation(self.trace, runs, actual=True, failed_audit=self.failed_audit)
            context = {"goal": self.goal, "public_task": self.public, "observed_resources": resources,
                "remaining_proposal_calls": 10 - ordinal, "actual_cpu_attempts_to_date": len(runs),
                "distinct_configs_to_date": len({value_hash(run["spec"]["config"]) for run in runs}),
                "host_ledger": {"current_events_path": str(root / "research/research.sqlite3"), "actual_execution_receipts": [
                    {"execution_id": run["run_id"], "result_path": str(Path(run["run_dir"]) / "result.json"),
                     "result_sha256": sha256_file(Path(run["run_dir"]) / "result.json")} for run in runs]}}
            snapshot = root / "resource-observations" / f"{call}.json"
            write_json(snapshot, {"call_id": call, "resources": resources, "fixture_only": True})
            start = {"call_id": call, "model_id": "fixture-model", "request_sha256": value_hash(context),
                "retrieved_run_ids": [], "resource_observation_path": str(snapshot), "resource_observation_sha256": sha256_file(snapshot),
                "classification": "actual_model", "status": "requested"}
            self.events.append(start)
            folder = root / "model" / call; folder.mkdir(parents=True)
            request = rich_request(root, folder)
            request["prompt"] = json.dumps(context, ensure_ascii=False, sort_keys=True)
            request["full_prompt"] = CodexProvider.guard + request["prompt"]
            request["fingerprint"] = value_hash({key: request[key] for key in ("model", "prompt", "reasoning_effort", "full_prompt", "provider_source_sha256")})
            write_json(folder / "request.json", request)
            failed = failed_second and ordinal == 1
            usage = {} if failed else {"input_tokens": (ordinal + 1) * 10, "output_tokens": ordinal + 2}
            raw_event = {"type": "turn.failed", "error": {"message": "Fixture no-action capacity failure"}} if failed else {"type": "turn.completed", "usage": usage}
            (folder / "events.jsonl").write_text(json.dumps(raw_event) + "\n", encoding="utf-8")
            (folder / "stderr.log").write_text("Synthetic format fixture only", encoding="utf-8")
            if not failed: (folder / "response.txt").write_text("Fixture response; no model invoked", encoding="utf-8")
            result = {"model": "fixture-model", "status": "failed" if failed else "completed", "execution_kind": "real_model",
                "fingerprint": request["fingerprint"], "returncode": 1 if failed else 0, "wall_seconds": 1.25,
                "usage": usage, "tool_calls": [], "files": {path.name: sha256_file(path) for path in folder.iterdir()}, "fixture_only": True}
            write_json(folder / "result.json", result)
            end = {**start, "event": "failure" if failed else "completion", "status": result["status"],
                "evidence_dir": str(folder), "model_evidence": result}
            if failed:
                receipt = root / "host-no-action.json"
                write_json(receipt, {"provenance": "trusted_host_audit", "attempt_result_sha256": sha256_file(folder / "result.json"),
                    "request_fingerprint": request["fingerprint"], "host_action_taken": False, "model_response_consumed": False,
                    "retry_reason": "Fixture explicit continuation only", "sources": [link(folder / name) for name in ("request.json", "result.json", "events.jsonl", "stderr.log")]})
                end["host_no_action_receipt"] = str(receipt)
                lineage = root / "failure-lineage.json"
                write_json(lineage, {"kind": "explicit_model_attempt_resume_lineage", "provenance": "trusted_host_audit", "model_id": "fixture-model",
                    "attempts": [{"failed_dir": str(folder), "result_sha256": sha256_file(folder / "result.json"),
                        "request_fingerprint": request["fingerprint"], "host_action_receipt": str(receipt), "receipt_sha256": sha256_file(receipt)}]})
                self.failed_audit = {"valid": True, "failed_attempts": 1, "unknown_failed_token_usage": True, "failed_token_usage": None}
            self.trace.append(end); self.events.append(end)
            if ordinal < 2 and not failed:
                spec = make_spec("dev-quadratic", 353, {"degree": ordinal + 1, "alpha": 0.0}, model="fixture-model", resource_envelope=self.envelope, task_bundle=bundle)
                spec["model_evidence"] = {"call_id": call, "fingerprint": request["fingerprint"], "model": "fixture-model"}
                self.engine.step(spec)
        self.flush()

    def flush(self):
        (self.root / "model-transport.jsonl").write_text("".join(json.dumps(row) + "\n" for row in self.events), encoding="utf-8")
        store = self.engine.store
        with store._connect() as db:
            events = [{**dict(row), "payload": json.loads(row["payload"])} for row in db.execute("SELECT * FROM events ORDER BY sequence")]
        write_json(self.root / "research-audit.json", {"provenance": "trusted_host_audit", "events": events, "runs": store.list_runs(), "fixture_only": True})

    def arguments(self):
        args = {"scope": "historical_pre_proposal", "proposal_request": link(self.root / "model/improved-0002/request.json"),
            "transport_trace": link(self.root / "model-transport.jsonl"), "callback_registration": link(self.root / "callback-registration.json"),
            "research_audit": link(self.root / "research-audit.json")}
        if (self.root / "failure-lineage.json").exists(): args["failed_lineage"] = link(self.root / "failure-lineage.json")
        return args

    def rewrite_request(self, ordinal, change, snapshot_change=False):
        """An attacker refreshes all outer hashes; fixed predicates must still fail."""
        call = f"improved-{ordinal:04d}"; folder = self.root / "model" / call
        request = json.loads((folder / "request.json").read_text()); change(request)
        request["fingerprint"] = value_hash({key: request[key] for key in ("model", "prompt", "reasoning_effort", "full_prompt", "provider_source_sha256")})
        write_json(folder / "request.json", request)
        result = json.loads((folder / "result.json").read_text()); result["fingerprint"] = request["fingerprint"]
        result["files"]["request.json"] = sha256_file(folder / "request.json"); write_json(folder / "result.json", result)
        for row in self.events:
            if row["call_id"] != call: continue
            row["request_sha256"] = value_hash(json.loads(request["prompt"]))
            if row["status"] != "requested": row["model_evidence"] = result
        if snapshot_change:
            path = self.root / "resource-observations" / f"{call}.json"
            snapshot = json.loads(path.read_text()); snapshot["resources"] = json.loads(request["prompt"])["observed_resources"]; write_json(path, snapshot)
            for row in self.events:
                if row["call_id"] == call: row["resource_observation_sha256"] = sha256_file(path)
        self.flush()


class HistoricalResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.fixture = PrefixFixture(self.root)

    def predicate(self, value=30, text="The historical pre-proposal cumulative input usage was 30 tokens.", kind="measured_result"):
        return {"predicate_id": "historical_pre_proposal_resources", "kind": kind, "text": text,
            "arguments": {**self.fixture.arguments(), "measure": "input_tokens", "value": value}}

    def test_exact_prefix_excludes_current_request_and_links_actual_cpu(self):
        record = recompute_historical_resources(self.fixture.arguments(), self.root)
        self.assertEqual(record["prefix_call_ids"], ["improved-0000", "improved-0001"])
        self.assertEqual(record["measures"]["input_tokens"], 30)
        self.assertEqual(record["measures"]["actual_cpu_executions"], 2)
        self.assertEqual(evaluate_predicate(self.predicate(), self.root)["facts"]["value"], 30)
        self.assertIn("excluded", record["scope"])

    def test_legacy_prefix_proof_is_ineligible_for_actual_semantic_completion(self):
        from evidence_research.report_semantics import validate_semantic_review
        text="The historical pre-proposal cumulative input usage was 30 tokens."
        report=self.root/"legacy-prefix.txt"; report.write_text(text,encoding="utf-8")
        inventory=self.root/"legacy-prefix-inventory.json"; unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="measured_result",outcome="supported",rationale="Historical format regression, not common actual proof.",
            predicate_id="historical_pre_proposal_resources",arguments=self.predicate()["arguments"])
        rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Complete legacy source span.","exhaustive_result_claim_mapping":True,"claims":[claim]}]
        output=self.root/"legacy-prefix-review.json"
        review=adjudicate_semantic_review(inventory,rows,output,arm_output=self.root,reviewer_role="independent_verifier")
        self.assertEqual(review["semantic_evidence_qualification"],"component_fixture")
        checked=validate_semantic_review(output,arm_output=self.root,require_complete=False)
        self.assertTrue(checked["review_coverage_complete"]); self.assertFalse(checked["semantic_report_audit_complete"])
        with self.assertRaises(ValueError): validate_semantic_review(output,arm_output=self.root)

    def test_new_list_grammar_does_not_let_legacy_scalar_skip_other_wrong_values(self):
        valid=self.predicate(text="Before this proposal, measured resources were 30 input tokens and 5 output tokens.")
        self.assertEqual(evaluate_predicate(valid,self.root)["facts"]["evidence_class"],"synthetic_fixture")
        changed=self.predicate(text="Before this proposal, measured resources were 30 input tokens and 99 output tokens.")
        with self.assertRaises(ValueError): evaluate_predicate(changed,self.root)

    def test_final_total_relabel_future_forecast_and_inference_rejected(self):
        for claim in (self.predicate(value=60), self.predicate(text="The final total was 30 tokens."),
                      self.predicate(text="The next proposal will consume 30 tokens."), self.predicate(kind="inference"),
                      self.predicate(text="Provider input usage was 30 tokens."), self.predicate(text="The historical final total was 30 tokens."),
                      self.predicate(text="This document has a historical appendix. Provider input usage was 30 tokens."),
                      self.predicate(text="Historically, we tested feature design. Provider input usage was 30 tokens."),
                      self.predicate(text="Historical feature design was discussed, and provider input usage was 30 tokens."),
                      self.predicate(text="The usage was not historical pre-proposal input usage of 30 tokens.")):
            with self.assertRaises(ValueError): evaluate_predicate(claim, self.root)
        args = self.fixture.arguments(); args["scope"] = "final"
        with self.assertRaises(ValueError): recompute_historical_resources(args, self.root)

    def test_request_order_arbitrary_shorter_list_and_trace_hash_rejected(self):
        original = deepcopy(self.fixture.events)
        self.fixture.events = original[2:4] + original[:2] + original[4:]; self.fixture.flush()
        with self.assertRaisesRegex(ValueError, "ordinals"): recompute_historical_resources(self.fixture.arguments(), self.root)
        self.fixture.events = original[2:]; self.fixture.flush()
        with self.assertRaises(ValueError): recompute_historical_resources(self.fixture.arguments(), self.root)
        self.fixture.events = original; self.fixture.flush(); args = self.fixture.arguments(); args["transport_trace"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"): recompute_historical_resources(args, self.root)

    def test_changed_raw_receipt_provider_source_settings_or_input_fail_closed(self):
        path = self.root / "model/improved-0000/events.jsonl"
        path.write_text('{"type":"turn.completed","usage":{"input_tokens":999,"output_tokens":2}}\n', encoding="utf-8")
        with self.assertRaises(ValueError): recompute_historical_resources(self.fixture.arguments(), self.root)

    def test_freshly_rehashed_wrong_provider_source_and_effort_rejected(self):
        for field, value in (("provider_source_sha256", "0" * 64), ("reasoning_effort", "high")):
            with tempfile.TemporaryDirectory() as name:
                root = Path(name).resolve(); fixture = PrefixFixture(root)
                fixture.rewrite_request(0, lambda request: request.update({field: value}))
                with self.assertRaisesRegex(ValueError, "source|effort"): recompute_historical_resources(fixture.arguments(), root)

    def test_rehashed_shorter_resource_list_and_reversed_cpu_order_rejected(self):
        def change(request):
            context = json.loads(request["prompt"]); context["host_ledger"]["actual_execution_receipts"].reverse()
            request["prompt"] = json.dumps(context, ensure_ascii=False, sort_keys=True); request["full_prompt"] = CodexProvider.guard + request["prompt"]
        self.fixture.rewrite_request(2, change, snapshot_change=True)
        with self.assertRaisesRegex(ValueError, "CPU prefix|receipt order"): recompute_historical_resources(self.fixture.arguments(), self.root)
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); fixture = PrefixFixture(root)
            def shorten(request):
                context = json.loads(request["prompt"]); context["observed_resources"]["sources"].pop()
                request["prompt"] = json.dumps(context, ensure_ascii=False, sort_keys=True); request["full_prompt"] = CodexProvider.guard + request["prompt"]
            fixture.rewrite_request(2, shorten, snapshot_change=True)
            with self.assertRaisesRegex(ValueError, "receipt lists"): recompute_historical_resources(fixture.arguments(), root)

    def test_additional_raw_request_not_in_durable_trace_is_discovered(self):
        from tests.test_model_request_audit import completed_fixture
        completed_fixture(self.root, self.root / "model/improved-0003")
        with self.assertRaisesRegex(ValueError, "omits"): recompute_historical_resources(self.fixture.arguments(), self.root)

    def test_rehashed_nonoriginal_provider_serialization_is_not_original_input(self):
        def change(request):
            request["prompt"] = " " + request["prompt"]
            request["full_prompt"] = CodexProvider.guard + request["prompt"]
        self.fixture.rewrite_request(0, change)
        with self.assertRaisesRegex(ValueError, "source input"): recompute_historical_resources(self.fixture.arguments(), self.root)

    def test_changed_snapshot_original_input_and_cpu_ledger_order_rejected(self):
        args = self.fixture.arguments(); path = self.root / "resource-observations/improved-0002.json"
        value = json.loads(path.read_text()); value["resources"]["sources"].pop(); write_json(path, value)
        with self.assertRaises(ValueError): recompute_historical_resources(args, self.root)

    def test_cpu_event_hash_chain_tamper_rejected_even_with_new_outer_link(self):
        path = self.root / "research-audit.json"; value = json.loads(path.read_text())
        value["events"][0]["payload"]["tampered"] = True; write_json(path, value)
        with self.assertRaisesRegex(ValueError, "hash chain"): recompute_historical_resources(self.fixture.arguments(), self.root)

    def test_fractional_tokens_are_not_allowed_by_float_rounding_tolerance(self):
        with self.assertRaises(ValueError): evaluate_predicate(self.predicate(value=30.000000001), self.root)

    def test_unknown_failed_tokens_remain_null_and_time_is_separate(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve(); fixture = PrefixFixture(root, failed_second=True)
            record = recompute_historical_resources(fixture.arguments(), root)
            self.assertIsNone(record["measures"]["input_tokens"]); self.assertFalse(record["tokens_known"])
            self.assertEqual(record["measures"]["wall_seconds"], 2.5)
            claim = {"predicate_id": "historical_pre_proposal_resources", "kind": "measured_result", "text": "Historical pre-proposal provider time was 2.5 seconds.",
                "arguments": {**fixture.arguments(), "measure": "wall_seconds", "value": 2.5}}
            self.assertEqual(evaluate_predicate(claim, root)["facts"]["value"], 2.5)
            claim["arguments"].update(measure="input_tokens", value=0)
            with self.assertRaisesRegex(ValueError, "unknown"): evaluate_predicate(claim, root)


class ScopedLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name).resolve()

    def review(self, text, kind, **extra):
        ordinal = len(list(self.root.glob("report-*.txt"))); path = self.root / f"report-{ordinal}.txt"
        path.write_text(text, encoding="utf-8"); inventory = self.root / f"inventory-{ordinal}.json"
        unit = prepare_semantic_review(path, inventory)["units"][0]
        claim = semantic_claim(unit, kind=kind, outcome="classified_nonresult", rationale="Scope fixture only.", **extra)
        rows = [{"unit_id": unit["unit_id"], "outcome": "reviewed", "rationale": "Complete original span.", "exhaustive_result_claim_mapping": True, "claims": [claim]}]
        return adjudicate_semantic_review(inventory, rows, self.root / f"review-{ordinal}.json", arm_output=self.root, reviewer_role="independent_verifier")

    def test_explicit_generalization_denials_and_future_test_are_nonresults(self):
        for text in ("That small validation difference does not establish a generalization advantage.", "이 결과는 프레임워크 설계 개선을 입증하지 않는다."):
            self.assertEqual(self.review(text, "limitation")["unsupported_semantic_result_claims"], 0)
        self.assertEqual(self.review("The next fit will test whether another feature improves validation prediction.", "proposal")["status"], "complete")

    def test_mixed_clause_unrelated_negative_and_future_cues_do_not_hide_results(self):
        for text, kind in (("Memory caused improvement, but this does not establish generalization.", "limitation"),
            ("This does not establish generalization, and Memory improved research performance.", "limitation"),
            ("We will test more features. Memory caused improvement.", "proposal"),
            ("The framework improved research performance. No private data were disclosed.", "limitation")):
            with self.assertRaises(ValueError): self.review(text, kind)

    def test_fixed_json_next_question_requires_its_exact_frozen_source(self):
        from evidence_research.report_semantics import _review_claim, semantic_units
        text = "Does removing retrieved verified memory change decisions under matched model and resources?"
        unit = next(value for value in semantic_units(json.dumps({"next_questions": [text]}), "f" * 64) if value["unit_kind"] == "json_string")
        context = {"kind": "fixed_next_question", "source": link(Path(__file__).resolve().parents[1] / "evidence_research/comparison_arms.py")}
        claim = semantic_claim(unit, kind="proposal", outcome="classified_nonresult", rationale="Frozen planning question, not a result.", nonresult_context=context)
        _review_claim(claim, unit, self.root)
        other = deepcopy(claim); other["nonresult_context"]["source"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError): _review_claim(other, unit, self.root)
        for alternate in ("Does Memory cause improvement?", "Does the model confirm generalization? It improved research performance."):
            changed = next(value for value in semantic_units(json.dumps({"next_questions": [alternate]}), "f" * 64) if value["unit_kind"] == "json_string")
            attack = semantic_claim(changed, kind="proposal", outcome="classified_nonresult", rationale="Changed question attack.", nonresult_context=context)
            with self.assertRaises(ValueError): _review_claim(attack, changed, self.root)

    def test_hypothesis_adjectival_prior_requires_actual_same_condition_baseline(self):
        envelope = {"reasoning_effort": "medium", "actual_cpu_executions_per_unit": 10}
        engine = Engine(self.root / "research", run_task, verify)
        first = engine.step(make_spec("dev-quadratic", 367, {"degree": 1, "alpha": 0.0}, resource_envelope=envelope))
        text = "A quadratic term may capture curvature that the verified linear fit misses."
        spec = make_spec("dev-quadratic", 367, {"degree": 2, "alpha": 0.0}, hypothesis=text, resource_envelope=envelope)
        spec["baseline"] = {"run_id": first["run_id"]}; second = engine.step(spec)
        context = {"kind": "registered_hypothesis", "run": run_reference(Path(second["run_dir"])), "prior_runs": [run_reference(Path(first["run_dir"]))]}
        self.assertEqual(self.review(text, "proposal", nonresult_context=context)["status"], "complete")
        with self.assertRaises(ValueError): self.review(text, "proposal")
        changed = deepcopy(context); changed["prior_runs"] = [run_reference(Path(second["run_dir"]))]
        with self.assertRaises(ValueError): self.review(text, "proposal", nonresult_context=changed)
        from evidence_research.report_semantics import validate_semantic_review
        checked=validate_semantic_review(self.root/"review-0.json",arm_output=self.root,require_complete=False)
        self.assertEqual(checked["semantic_evidence_qualification"],"engineering_legacy")
        self.assertFalse(checked["semantic_report_audit_complete"])
        with self.assertRaises(ValueError): self.review("We propose more research. Memory caused the improvement.", "proposal", nonresult_context=context)

    def test_literature_negated_optimal_is_attribution_not_local_minimum(self):
        text = "It does not identify an optimal polynomial degree; those must be measured from supplied data."
        source = self.root / "literature-format.txt"; source.write_text("https://example.org/fixture\n" + text, encoding="utf-8")
        report = self.root / "literal.txt"; report.write_text(text, encoding="utf-8"); inventory = self.root / "literal-inventory.json"
        unit = prepare_semantic_review(report, inventory)["units"][0]
        claim = semantic_claim(unit, kind="literature", outcome="supported", rationale="Exact attributed format fixture; no local task finding.", predicate_id="attributed_literature",
            arguments={"source": link(source), "excerpt": text, "url": "https://example.org/fixture"})
        row = {"unit_id": unit["unit_id"], "outcome": "reviewed", "rationale": "Entire quoted source.", "exhaustive_result_claim_mapping": True, "claims": [claim]}
        self.assertEqual(adjudicate_semantic_review(inventory, [row], self.root / "literal-review.json", arm_output=self.root, reviewer_role="independent_verifier")["status"], "complete")
        claim["kind"] = "execution_provenance"
        with self.assertRaisesRegex(ValueError, "local execution"): adjudicate_semantic_review(inventory, [row], self.root / "inverse-review.json", arm_output=self.root, reviewer_role="independent_verifier")

    def test_corpus_copy_does_not_verify_local_agent_reading_or_comprehension(self):
        text = "The agent understood all five papers."
        source = self.root / "format-source.txt"; source.write_text("https://example.org/fixture\n" + text, encoding="utf-8")
        report = self.root / "access.txt"; report.write_text(text, encoding="utf-8"); inventory = self.root / "access-inventory.json"; unit = prepare_semantic_review(report, inventory)["units"][0]
        claim = semantic_claim(unit, kind="literature", outcome="supported", rationale="Intentional corpus-copy attack.", predicate_id="attributed_literature", arguments={"source": link(source), "excerpt": text, "url": "https://example.org/fixture"})
        row = {"unit_id": unit["unit_id"], "outcome": "reviewed", "rationale": "Attack.", "exhaustive_result_claim_mapping": True, "claims": [claim]}
        with self.assertRaisesRegex(ValueError, "comprehension"): adjudicate_semantic_review(inventory, [row], self.root / "access-review.json", arm_output=self.root, reviewer_role="independent_verifier")


if __name__ == "__main__": unittest.main()
