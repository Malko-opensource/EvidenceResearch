"""Review-gate attacks use real local CPU evidence, never real model calls."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.evaluation import (adjudicate_numeric_review, prepare_numeric_review,
                                         _validate_numeric_review, _audit_telemetry, _failure_score)
from evidence_research.model import PreregisteredResourcesExhausted
from evidence_research.tasks import make_spec, run_task, sha256_file, value_hash, write_json
from tests.test_model_request_audit import completed_fixture


class IndependentReviewGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.run = self.root / "actual-cpu"
        spec = make_spec("dev-quadratic", 71, {"degree": 2, "alpha": 0.1})
        result = run_task(spec, self.run)
        self.report = self.root / "report.txt"
        self.report.write_text(f"Validation MSE {result['metrics']['validation_mse']:.8f}; registered degree 2. One fixed public split.\n", encoding="utf-8")
        self.inventory = self.root / "inventory.json"
        items = prepare_numeric_review(self.report, self.inventory)["items"]
        judgments = [{"claim_id": items[0]["claim_id"], "kind": "measured", "run_dir": str(self.run),
            "metric": "validation_mse", "rationale": "Independent CPU prediction/metric recomputation."},
            {"claim_id": items[1]["claim_id"], "kind": "method", "source_path": str(self.run / "registered_spec.json"),
            "source_sha256": sha256_file(self.run / "registered_spec.json"), "rationale": "Literal degree agrees with fixed registration."}]
        self.review = adjudicate_numeric_review(self.inventory, judgments, self.root / "review.json", reviewer_role="independent_verifier")

    def validate(self, review):
        return _validate_numeric_review(review, arm_output=self.root)

    def test_valid_coverage_and_actual_metric_recomputation(self):
        self.assertEqual(self.validate(self.review), {"unsupported_claims": 0, "original_claims": 2, "supplemental_claims": 0})

    def test_omitted_duplicate_or_unknown_claim_rejects_complete_flag(self):
        for change in ("omitted", "duplicate", "unknown"):
            with self.subTest(change=change):
                r = deepcopy(self.review)
                if change == "omitted": r["claims"].pop()
                elif change == "duplicate": r["claims"].append(deepcopy(r["claims"][0]))
                else: r["claims"][0]["claim_id"] = "f" * 64
                with self.assertRaises(ValueError): self.validate(r)

    def test_inventory_cannot_omit_report_number_even_with_fresh_hashes(self):
        r = deepcopy(self.review)
        inventory = json.loads(self.inventory.read_text(encoding="utf-8"))
        inventory["items"].pop(); write_json(self.inventory, inventory)
        r["inventory_sha256"] = sha256_file(self.inventory); r["claims"].pop()
        with self.assertRaisesRegex(ValueError, "report reconstruction"): self.validate(r)

    def test_claim_source_literal_and_role_are_exact(self):
        r = deepcopy(self.review); r["claims"][0]["number"] = "0.00000000"
        with self.assertRaisesRegex(ValueError, "inventoried source"): self.validate(r)
        r = deepcopy(self.review); r["reviewer_role"] = "research_proposer"
        with self.assertRaisesRegex(ValueError, "role"): self.validate(r)

    def test_false_pending_and_unsupported_counters_are_recomputed(self):
        r = deepcopy(self.review); r["claims"][1]["outcome"] = "pending"
        with self.assertRaisesRegex(ValueError, "pending"): self.validate(r)
        r["pending_claims"] = 1
        with self.assertRaisesRegex(ValueError, "pending"): self.validate(r)
        r = deepcopy(self.review); r["unsupported_claims"] = 1
        with self.assertRaisesRegex(ValueError, "counters"): self.validate(r)
        r = deepcopy(self.review); r["pending_claims"] = False
        with self.assertRaisesRegex(ValueError, "counters"): self.validate(r)

    def test_forged_supported_value_and_nonmeasurement_relabel_are_rejected(self):
        r = deepcopy(self.review); r["claims"][0]["evidence"][0]["independent_value"] = 0
        with self.assertRaisesRegex(ValueError, "value differs"): self.validate(r)
        r = deepcopy(self.review); r["claims"][0]["outcome"] = "classified_nonmeasurement"
        with self.assertRaisesRegex(ValueError, "contradicts"): self.validate(r)

    def test_changed_source_hash_and_missing_hash_are_rejected(self):
        source = self.run / "registered_spec.json"
        source.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError): self.validate(self.review)
        r = deepcopy(self.review); r["claims"][1]["evidence"][0].pop("sha256")
        with self.assertRaises(ValueError): self.validate(r)

    def test_supported_claim_requires_calculation_or_original_evidence(self):
        r = deepcopy(self.review); r["claims"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "hash-linked"): self.validate(r)
        r = deepcopy(self.review); r["claims"][0]["kind"] = "derived_measured"
        with self.assertRaisesRegex(ValueError, "pinned calculation"): self.validate(r)

    def test_supplemental_word_quantity_is_source_span_and_hash_bound(self):
        line = self.report.read_text(encoding="utf-8").splitlines()[0];start = line.index("One")
        item = {"line": 1, "start": start, "end": start + 3, "number": "One", "context": line}
        item["claim_id"] = value_hash({"report_sha256": self.review["report_sha256"], **item})
        supplemental = self.root / "supplemental.json"
        write_json(supplemental, {"report_sha256": self.review["report_sha256"], "items": [item]})
        r = deepcopy(self.review);r["supplemental_inventory"] = {"path": str(supplemental), "sha256": sha256_file(supplemental)}
        r["claims"].append({**item, "kind": "method", "outcome": "classified_nonmeasurement",
            "reason": "Fixed public partition count from the actual manifest, not independently sampled repeats.",
            "evidence": [{"path": str(self.run / "split_manifest.json"), "sha256": sha256_file(self.run / "split_manifest.json")}]})
        self.assertEqual(self.validate(r)["supplemental_claims"], 1)
        r["claims"][-1]["start"] = 0
        with self.assertRaisesRegex(ValueError, "inventoried source"): self.validate(r)

    def test_telemetry_does_not_accept_an_empty_forged_complete_review(self):
        r = deepcopy(self.review);r["claims"] = []
        review_path = self.root / "forged-review.json";write_json(review_path, r)
        telemetry = {"provenance": "trusted_host_audit", "duplicate_executions": 0, "recovered_errors": 0,
            "unsupported_claims": 0, "verified_memory_hits": 0, "sources": [{"path": str(self.report), "sha256": sha256_file(self.report)}],
            "report_review_paths": [{"path": str(review_path), "sha256": sha256_file(review_path)}], "claim_audit_scope": "whole_report_numeric_inventory"}
        path = self.root / "telemetry.json";write_json(path, telemetry)
        with self.assertRaisesRegex(ValueError, "coverage"): _audit_telemetry({"telemetry_evidence_path": str(path)}, self.root)

    def test_registered_budget_failure_is_terminal_and_usage_unknown(self):
        arm = self.root / "budget-arm";arm.mkdir()
        receipt = arm / "raw.txt";receipt.write_text("preserved original partial evidence", encoding="utf-8")
        score = _failure_score({"unit_id": "development-fixture"}, "C", arm, PreregisteredResourcesExhausted("Declared allowance used."))
        self.assertEqual(score["status"], "registered_resources_exhausted")
        self.assertEqual(score["classification"], "registered_resources_exhausted")
        self.assertFalse(score["task_success"]);self.assertIsNone(score["provider_token_usage"])
        self.assertTrue(any(e["path"] == str(receipt) and e["sha256"] == sha256_file(receipt) for e in score["evidence"]["failure_files"]))

    def test_resource_review_recomputes_raw_receipts_and_rejects_forged_value(self):
        # These are labelled synthetic provider bytes; no actual model is called.
        folder = self.root / "synthetic-resource-provider"
        completed_fixture(self.root, folder)
        measures = {"provider_calls": 1, "provider_attempts": 1, "failed_model_attempts": 0, "model_seconds": 1.25,
            "input_tokens": 10, "output_tokens": 5, "completed_input_tokens": 10, "completed_output_tokens": 5}
        audit = self.root / "resource-audit.json"
        write_json(audit, {"schema_version": "independent-resource-audit-1", "model_id": "fixture-model",
            "resource_envelope": {"reasoning_effort": "medium", "actual_cpu_executions_per_unit": 2},
            "arm_output": str(self.root), "completed_model_evidence_dirs": [str(folder)], "failed_model_attempt_dirs": [],
            "host_action_receipts": {}, "continuation_lineage_path": None, "measures": measures})
        report = self.root / "resource-report.txt";report.write_text("Input tokens 10; model seconds 1.25", encoding="utf-8")
        inventory = self.root / "resource-inventory.json";items = prepare_numeric_review(report, inventory)["items"]
        judgments = [{"claim_id": item["claim_id"], "kind": "measured_resource", "resource_audit_path": str(audit),
            "resource_metric": "input_tokens" if item["number"] == "10" else "model_seconds",
            "rationale": "Synthetic resource-audit gate test, not actual model-effect evidence."} for item in items]
        reviewed = adjudicate_numeric_review(inventory, judgments, self.root / "resource-review.json", reviewer_role="independent_verifier")
        self.assertEqual(self.validate(reviewed)["original_claims"], 2)
        corrupted = deepcopy(reviewed)
        corrupted["claims"][0]["evidence"][-1]["independent_value"] = 999
        with self.assertRaisesRegex(ValueError, "resource value differs"): self.validate(corrupted)


if __name__ == "__main__": unittest.main()
