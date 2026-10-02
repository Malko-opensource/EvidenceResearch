"""Semantic scope/coverage attacks use real CPU artifacts, zero model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.report_semantics import (SEMANTIC_POLICY, prepare_semantic_review,
    adjudicate_semantic_review, validate_semantic_review, semantic_units, semantic_claim,
    run_reference, audit_semantic_reports)
from evidence_research.report_semantics import evaluate_predicate, semantic_review_sidecars, next_semantic_review_path
from evidence_research.evaluation import _semantic_score_ready, frozen_sources
from evidence_research.tasks import make_spec, run_task, sha256_file, write_json


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.left, self.right = self.root / "left", self.root / "right"
        for degree, directory in ((2, self.left), (1, self.right)):
            run_task(make_spec("dev-quadratic", 73, {"degree": degree, "alpha": 0.0}), directory)
        self.report = self.root / "report.txt"
        self.report.write_text("The selected experiment executed and independently verified.\n\n"
            "Its observed validation error is better than the linear candidate on the same split.\n\n"
            "We propose a new regularization hypothesis next.\n\n"
            "General scientific discovery remains unproven.", encoding="utf-8")
        self.inventory_path = self.root / "inventory.json"
        self.inventory = prepare_semantic_review(self.report, self.inventory_path)
        units = self.inventory["units"]
        claims = [semantic_claim(units[0], kind="execution_provenance", outcome="supported", rationale="Actual CPU receipts.",
                    predicate_id="verified_execution", arguments={"run": run_reference(self.left)}),
                  semantic_claim(units[1], kind="measured_result", outcome="supported", rationale="Observed same-split comparison only.",
                    predicate_id="observed_validation_comparison", arguments={"left": run_reference(self.left), "right": run_reference(self.right), "relation": "lt"}),
                  semantic_claim(units[2], kind="proposal", outcome="classified_nonresult", rationale="Prospective, no measured gain."),
                  semantic_claim(units[3], kind="limitation", outcome="classified_nonresult", rationale="Explicit restriction of conclusion.")]
        self.rows = [{"unit_id": unit["unit_id"], "outcome": "reviewed", "rationale": "All assertions and their applicable conditions read independently.",
                      "exhaustive_result_claim_mapping": True, "claims": [claim]} for unit, claim in zip(units, claims)]
        self.review_path = self.root / "review.json"
        self.review = adjudicate_semantic_review(self.inventory_path, self.rows, self.review_path,
            arm_output=self.root, reviewer_role="independent_verifier")

    def mutated_review(self, record):
        path = self.root / "mutated-review.json"; write_json(path, record)
        return validate_semantic_review(path, arm_output=self.root)

    def test_all_paragraphs_and_qualitative_assertions_audited_without_numbers(self):
        audit = validate_semantic_review(self.review_path, arm_output=self.root)
        self.assertTrue(audit["semantic_report_audit_complete"])
        self.assertEqual(audit["unsupported_semantic_result_claims"], 0)
        self.assertEqual(audit["units"], 4); self.assertEqual(audit["claims"], 4)
        self.assertIsNone(audit["review_usage"])
        self.assertTrue(any(Path(path).name == "report_semantics.py" for path in frozen_sources()))

    def test_every_escaped_repeated_json_string_leaf_and_mixed_paragraph_is_bound(self):
        text = 'Heading\n\n```json\n{"a": "same", "nested": ["same", "quoted \\\"yes\\\""], "empty": "", "n": 2}\n```\n\nNo demonstrated improvement.'
        units = semantic_units(text, "a"*64)
        leaves = [u for u in units if u["unit_kind"] == "json_string"]
        self.assertEqual([u["pointer"] for u in leaves], ["/a", "/nested/0", "/nested/1", "/empty"])
        self.assertEqual(len({u["unit_id"] for u in leaves}), 4)
        self.assertEqual(leaves[2]["decoded_text"], 'quoted "yes"')
        for unit in units: self.assertEqual(text[unit["start"]:unit["end"]], unit["text"])
        self.assertEqual(len([u for u in units if u["unit_kind"] == "paragraph"]), 2)
        self.assertEqual(len([u for u in units if u["unit_kind"] == "json_structure"]), 1)

    def test_omitted_duplicate_unknown_units_and_false_complete_rejected(self):
        for mode in ("omit", "duplicate", "unknown", "pending"):
            with self.subTest(mode=mode):
                r = deepcopy(self.review)
                if mode == "omit": r["units"].pop()
                elif mode == "duplicate": r["units"].append(deepcopy(r["units"][0]))
                elif mode == "unknown": r["units"][0]["unit_id"] = "f"*64
                else: r["units"][0]["outcome"] = "pending"
                with self.assertRaises(ValueError): self.mutated_review(r)

    def test_inventory_reconstruction_rejects_freshly_hashed_omission(self):
        inventory = deepcopy(self.inventory); inventory["units"].pop(); write_json(self.inventory_path, inventory)
        r = deepcopy(self.review); r["inventory"]["sha256"] = sha256_file(self.inventory_path); r["units"].pop()
        with self.assertRaisesRegex(ValueError, "entire original report"): self.mutated_review(r)

    def test_sources_role_spans_and_exhaustive_mapping_are_checked(self):
        for mode in ("role", "span", "mapping", "source", "proof"):
            with self.subTest(mode=mode):
                r = deepcopy(self.review)
                if mode == "role": r["reviewer_role"] = "research_proposer"
                elif mode == "span": r["units"][0]["claims"][0]["text"] = "forged assertion"
                elif mode == "mapping": r["units"][0]["exhaustive_result_claim_mapping"] = False
                elif mode == "source": r["units"][0]["claims"][0]["arguments"]["run"]["sources"][0]["sha256"] = "f"*64
                else: r["units"][0]["claims"][0]["predicate_result"]["facts"]["valid"] = False
                with self.assertRaises(ValueError): self.mutated_review(r)

    def test_general_framework_causality_and_reproduction_fail_closed(self):
        for text, predicate in (("The framework improved research performance.", "verified_execution"),
                                ("Memory caused the improvement.", "causal_memory_effect"),
                                ("The outcome was independently replicated.", "verified_execution")):
            with self.subTest(text=text):
                report = self.root / (str(len(text)) + "-scope.txt"); report.write_text(text, encoding="utf-8")
                inventory = self.root / (str(len(text)) + "-scope-inventory.json")
                unit = prepare_semantic_review(report, inventory)["units"][0]
                claim = semantic_claim(unit, kind="general_result", outcome="supported", rationale="Deliberate unsupported scope attack.",
                    predicate_id=predicate, arguments={"run": run_reference(self.left)})
                row = {"unit_id": unit["unit_id"], "outcome": "reviewed", "rationale": "Scope attack.", "exhaustive_result_claim_mapping": True, "claims": [claim]}
                with self.assertRaises(ValueError): adjudicate_semantic_review(inventory, [row], self.root / (str(len(text)) + "-scope-review.json"), arm_output=self.root, reviewer_role="independent_verifier")
                claim["kind"] = "method"; claim["outcome"] = "classified_nonresult"
                if "framework" in text or "Memory" in text:
                    with self.assertRaises(ValueError): adjudicate_semantic_review(inventory, [row], self.root / (str(len(text)) + "-method-review.json"), arm_output=self.root, reviewer_role="independent_verifier")

    def test_different_seed_comparison_and_wrong_direction_are_rejected(self):
        other = self.root / "other-seed"; run_task(make_spec("dev-quadratic", 79, {"degree": 1, "alpha": 0.0}), other)
        for changed in (run_reference(other), run_reference(self.right)):
            r = deepcopy(self.rows); args = r[1]["claims"][0]["arguments"]; args["right"] = changed
            if changed["run_dir"] == str(self.right): args["relation"] = "gt"
            with self.assertRaises(ValueError): adjudicate_semantic_review(self.inventory_path, r, self.root / (Path(changed["run_dir"]).name + "-attack.json"), arm_output=self.root, reviewer_role="independent_verifier")

    def test_pending_unsupported_and_two_report_AND_gate(self):
        r = deepcopy(self.rows); r[1]["claims"][0]["outcome"] = "pending"
        path = self.root / "pending.json"; pending = adjudicate_semantic_review(self.inventory_path, r, path, arm_output=self.root, reviewer_role="independent_verifier")
        self.assertEqual(pending["status"], "pending")
        self.assertFalse(validate_semantic_review(path, arm_output=self.root, require_complete=False)["semantic_report_audit_complete"])
        with self.assertRaises(ValueError): validate_semantic_review(path, arm_output=self.root)
        r[1]["claims"][0]["outcome"] = "unsupported"; unsupported_path = self.root / "unsupported.json"
        adjudicate_semantic_review(self.inventory_path, r, unsupported_path, arm_output=self.root, reviewer_role="independent_verifier")
        self.assertEqual(validate_semantic_review(unsupported_path, arm_output=self.root)["unsupported_semantic_result_claims"], 1)
        audit = audit_semantic_reports([self.report, self.root / "unreviewed-companion.json"], [self.review_path], arm_output=self.root)
        self.assertFalse(audit["semantic_report_audit_complete"])
        self.assertFalse(_semantic_score_ready({"semantic_report_audit_complete": True, "unsupported_semantic_result_claims": 1}))
        self.assertFalse(_semantic_score_ready({"whole_report_numeric_audit_complete": True}))
        self.assertTrue(_semantic_score_ready({}, required=False))

    def test_no_result_cue_cannot_bypass_review_and_candidate_review_is_immutable(self):
        r = deepcopy(self.rows); r[0]["claims"] = []
        with self.assertRaisesRegex(ValueError, "result-bearing text"): adjudicate_semantic_review(self.inventory_path, r, self.root / "empty-claims.json", arm_output=self.root, reviewer_role="independent_verifier")
        original = sha256_file(self.review_path)
        r = deepcopy(self.rows); r[0]["rationale"] = "Changed decision"
        with self.assertRaisesRegex(ValueError, "immutable"): adjudicate_semantic_review(self.inventory_path, r, self.review_path, arm_output=self.root, reviewer_role="independent_verifier")
        self.assertEqual(sha256_file(self.review_path), original)

    def test_absolute_criterion_configuration_and_train_only_predicates(self):
        base = {"arguments": {"run": run_reference(self.left)}}
        self.assertTrue(evaluate_predicate({**base, "predicate_id": "train_only_disjoint_split"}, self.root)["facts"]["valid"])
        spec = json.loads((self.left / "registered_spec.json").read_text(encoding="utf-8"))
        configured = {"predicate_id": "registered_configuration", "arguments": {**base["arguments"], "config": spec["config"]}}
        self.assertEqual(evaluate_predicate(configured, self.root)["facts"]["config"], spec["config"])
        criterion = {"predicate_id": "registered_criterion", "arguments": {**base["arguments"], "success": True}}
        self.assertTrue(evaluate_predicate(criterion, self.root)["facts"]["success"])
        criterion["arguments"]["success"] = False
        with self.assertRaisesRegex(ValueError, "contradicts"): evaluate_predicate(criterion, self.root)

    def test_complete_history_required_for_best_and_counts_not_independent_replication(self):
        refs = [run_reference(self.left), run_reference(self.right)]
        minimum = {"predicate_id": "observed_minimum", "arguments": {"runs": refs, "selected": refs[0]}}
        self.assertEqual(evaluate_predicate(minimum, self.root)["facts"]["actual_executions"], 2)
        minimum["arguments"]["runs"] = refs[:1]
        with self.assertRaisesRegex(ValueError, "omits"): evaluate_predicate(minimum, self.root)
        minimum["arguments"]["runs"] = refs; minimum["arguments"]["selected"] = refs[1]
        with self.assertRaisesRegex(ValueError, "not the minimum"): evaluate_predicate(minimum, self.root)
        counts = {"predicate_id": "observed_inventory_counts", "arguments": {"runs": refs,
            "counts": {"actual_executions": 2, "distinct_configurations": 2, "repeated_configurations": 0}}}
        self.assertEqual(evaluate_predicate(counts, self.root)["facts"]["repeated_configurations"], 0)
        counts["arguments"]["counts"]["repeated_configurations"] = 1
        with self.assertRaisesRegex(ValueError, "counts contradict"): evaluate_predicate(counts, self.root)

    def test_pending_then_complete_versions_preserve_history_and_new_pending_precedes(self):
        rows = deepcopy(self.rows); rows[0]["claims"][0]["outcome"] = "pending"
        old = next_semantic_review_path(self.root, "semantic-report-review")
        adjudicate_semantic_review(self.inventory_path, rows, old, arm_output=self.root, reviewer_role="independent_verifier")
        old_hash = sha256_file(old)
        fresh = next_semantic_review_path(self.root, "semantic-report-review")
        self.assertEqual(fresh.name, "semantic-report-review-v0001.json")
        adjudicate_semantic_review(self.inventory_path, self.rows, fresh, arm_output=self.root, reviewer_role="independent_verifier")
        latest, history = semantic_review_sidecars(self.root)
        self.assertEqual(latest, [fresh]); self.assertEqual(len(history), 2); self.assertEqual(sha256_file(old), old_hash)
        later = next_semantic_review_path(self.root, "semantic-report-review")
        adjudicate_semantic_review(self.inventory_path, rows, later, arm_output=self.root, reviewer_role="independent_verifier")
        self.assertEqual(semantic_review_sidecars(self.root)[0], [later])

    def test_recognized_result_labels_irrelevant_negation_and_partial_spans_cannot_bypass(self):
        examples = [("The outcome was independently replicated.", "method"),
                    ("The validation error is better than every other candidate.", "method"),
                    ("Memory improved research performance. No private data were disclosed.", "method"),
                    ("We propose future work. Memory caused the improvement.", "proposal"),
                    ("The framework improved research performance. No private data were disclosed.", "limitation")]
        for index, (text, kind) in enumerate(examples):
            report = self.root / f"label-attack-{index}.txt"; report.write_text(text, encoding="utf-8")
            inventory = self.root / f"label-inventory-{index}.json"; unit = prepare_semantic_review(report, inventory)["units"][0]
            claim = semantic_claim(unit, kind=kind, outcome="classified_nonresult", rationale="Deliberate exclusion attack.")
            row = {"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Attack.","exhaustive_result_claim_mapping":True,"claims":[claim]}
            with self.assertRaises(ValueError):adjudicate_semantic_review(inventory,[row],self.root / f"label-review-{index}.json",arm_output=self.root,reviewer_role="independent_verifier")
        text = "We propose future work. The outcome was independently replicated."
        report = self.root / "partial.txt"; report.write_text(text, encoding="utf-8")
        inventory = self.root / "partial-inventory.json";unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Only the first sentence reviewed.",end=len("We propose future work."))
        row={"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Attack.","exhaustive_result_claim_mapping":True,"claims":[claim]}
        with self.assertRaisesRegex(ValueError,"omit non-whitespace"):adjudicate_semantic_review(inventory,[row],self.root / "partial-review.json",arm_output=self.root,reviewer_role="independent_verifier")

    def test_qualitative_json_key_is_an_actual_semantic_unit(self):
        text='{"The framework is superior":true}'
        units=semantic_units(text,"b"*64)
        key=[u for u in units if u["unit_kind"]=="json_key"][0]
        self.assertEqual(key["decoded_text"],"The framework is superior")
        self.assertEqual([u["decoded_text"] for u in units if u["unit_kind"]=="json_scalar"],["true"])
        self.assertEqual(text[key["start"]:key["end"]],key["text"])

    def test_execution_success_does_not_support_comparative_improvement(self):
        text="This experiment improved validation error over the baseline."
        report=self.root / "comparison.txt";report.write_text(text,encoding="utf-8")
        inventory=self.root / "comparison-inventory.json";unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="measured_result",outcome="supported",rationale="Deliberate predicate-scope mismatch.",predicate_id="verified_execution",arguments={"run":run_reference(self.left)})
        row={"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Attack.","exhaustive_result_claim_mapping":True,"claims":[claim]}
        with self.assertRaisesRegex(ValueError,"matched comparison"):adjudicate_semantic_review(inventory,[row],self.root / "comparison-review.json",arm_output=self.root,reviewer_role="independent_verifier")

    def test_literature_is_attributed_and_conditional_inference_remains_tentative(self):
        source=self.root / "literature-format-fixture.txt"
        source.write_text("https://example.org/primary-format-fixture\nA synthetic citation format statement, not actual literature evidence.",encoding="utf-8")
        claim={"predicate_id":"attributed_literature","arguments":{"source":{"path":str(source),"sha256":sha256_file(source)},
            "url":"https://example.org/primary-format-fixture","excerpt":"A synthetic citation format statement, not actual literature evidence."}}
        self.assertEqual(evaluate_predicate(claim,self.root)["facts"]["scope"],"attributed source statement; not a locally measured finding")
        claim["arguments"]["url"]="https://example.org/wrong-citation"
        with self.assertRaises(ValueError):evaluate_predicate(claim,self.root)
        inference={"predicate_id":"conditional_inference","kind":"inference","text":"This observed validation result may suggest sensitivity to polynomial degree.",
            "arguments":{"run":run_reference(self.left),"conditions":"This fixed development task and validation split only."}}
        self.assertIn("not measured",evaluate_predicate(inference,self.root)["facts"]["scope"])
        inference["text"]="This validation result establishes a general framework improvement."
        with self.assertRaises(ValueError):evaluate_predicate(inference,self.root)
        inference["text"]="We propose next steps. This experiment improved validation error over the baseline."
        with self.assertRaisesRegex(ValueError,"sentence|completed result"):evaluate_predicate(inference,self.root)

    def test_resource_predicate_recomputes_format_fixture_not_fictitious_claim(self):
        from tests.test_model_request_audit import completed_fixture
        folder=self.root / "synthetic-provider-format";completed_fixture(self.root,folder)
        audit=self.root / "format-resource-audit.json"
        measures={"provider_calls":1,"provider_attempts":1,"failed_model_attempts":0,"model_seconds":1.25,
            "input_tokens":10,"output_tokens":5,"completed_input_tokens":10,"completed_output_tokens":5}
        write_json(audit,{"schema_version":"independent-resource-audit-1","model_id":"fixture-model",
            "resource_envelope":{"reasoning_effort":"medium","actual_cpu_executions_per_unit":2},"arm_output":str(self.root),
            "completed_model_evidence_dirs":[str(folder)],"failed_model_attempt_dirs":[],"host_action_receipts":{},"continuation_lineage_path":None,"measures":measures,
            "fixture_only":True,"scope":"Synthetic receipt-format unit test; no actual provider calls or performance evidence."})
        claim={"predicate_id":"resource_accounting","arguments":{"resource_audit":{"path":str(audit),"sha256":sha256_file(audit)},"measure":"input_tokens","value":10}}
        self.assertEqual(evaluate_predicate(claim,self.root)["facts"]["value"],10)
        claim["arguments"]["value"]=999
        with self.assertRaisesRegex(ValueError,"differs"):evaluate_predicate(claim,self.root)
        claim["arguments"]["value"]=None;claim["arguments"]["measure"]="unmetered_reviewer_usage"
        with self.assertRaisesRegex(ValueError,"unknown"):evaluate_predicate(claim,self.root)


if __name__ == "__main__": unittest.main()
