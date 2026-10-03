"""Saved report flags are recomputed; all CPU/model bytes are synthetic.

Only earlier CPU/model gates are explicit no-execution stubs. Report contract,
numeric inventory, independent review validation and saved-score gate are the
fixed candidate functions. These fixtures cannot authenticate actual adoption.
"""
from copy import deepcopy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_research.evaluation import (
    _audit_telemetry, _native_callback_response_evidence, _validate_saved_score,
    adjudicate_numeric_review, prepare_numeric_review)
from evidence_research.report_contract import REPORT_SCHEMA_VERSION, verify_report_contract
from evidence_research.study import _report_decision
from evidence_research.tasks import sha256_file, value_hash, write_json


class SavedScoreReportBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c9-saved-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.counter = 0

    def fixture(self, *, sufficient=True, review_both=True, unknown_tokens=False,
                resources=None, review_decoy=False):
        root = self.root / str(self.counter); self.counter += 1; root.mkdir()
        run = root / "synthetic-selected"; run.mkdir()
        spec = {"fixture_only": True, "config": {"degree": 1, "alpha": 0},
                "task_id": "synthetic-no-data", "task_version": "fixture", "seed": 1,
                "split_manifest_sha256": "split-fixture", "implementation_sha256": "source-fixture",
                "evaluator_sha256": "evaluator-fixture", "metric": "validation_mse",
                "execution_entrypoint": {"kind": "synthetic_fixture"},
                "command": "not executable: fixture", "reproduction_command": "not executable: fixture"}
        result = {"fixture_only": True, "status": "success", "metrics": {"validation_mse": 0.2}}
        verification = {"valid": True, "metrics": {"validation_mse": 0.2}}
        write_json(run / "registered_spec.json", spec)
        write_json(run / "result.json", result)
        write_json(run / "model.json", {"fixture_only": True})
        primary = root / "report.txt"; primary.write_text("Synthetic engineering report only.\n", encoding="utf-8")
        companion = root / "research_report.json"
        resource = resources or {"tokens_known": not unknown_tokens,
            "token_usage": None if unknown_tokens else {"input_tokens": 0, "output_tokens": 0},
            "seconds": 0, "scope": "Synthetic zero-call component receipt; no actual model measurement."}
        report = {"fixture_only": True, "schema_version": REPORT_SCHEMA_VERSION,
            "goal": "Check a synthetic report contract." if sufficient else "",
            "hypothesis": "Synthetic fixture only.", "selected_config": spec["config"],
            "provenance": {k: spec[k] for k in ("task_id", "task_version", "seed", "split_manifest_sha256",
                          "implementation_sha256", "evaluator_sha256")},
            "execution": {"kind": spec["execution_entrypoint"]["kind"], "entrypoint": spec["command"],
                          "reproduction_command": spec["reproduction_command"]},
            "evidence": [{"path": str(run / "result.json"), "sha256": sha256_file(run / "result.json")}],
            "measured_metrics": [{"metric": "validation_mse", "value": 0.2, "kind": "measured",
                "evidence_path": str(run / "result.json"), "evidence_sha256": sha256_file(run / "result.json")}],
            "selection_reason": "Hand-authored fixture; no model selection.", "unresolved": [],
            "limitations": ["This is not an actual research result."], "next_questions": ["Does the gate reject tampering?"],
            "references": [{"kind": "literature", "url": "https://arxiv.org/abs/2501.04227",
                            "claim": "Reference identifier only in a synthetic fixture."}], "resources": resource}
        write_json(companion, report)
        review_paths = [primary, companion] if review_both else [primary]
        if review_decoy:
            decoy = root / "unrelated.txt"; decoy.write_text("Unrelated synthetic report.\n", encoding="utf-8")
            review_paths = [primary, decoy]
        reviews = []
        for i, path in enumerate(review_paths):
            inventory = root / f"inventory-{i}.json"
            original = prepare_numeric_review(path, inventory)
            judgments = [{"claim_id": item["claim_id"], "kind": "method", "source_path": str(path),
                          "source_sha256": sha256_file(path),
                          "rationale": "Literal synthetic fixture contract content, not an actual measured claim."}
                         for item in original["items"]]
            review = root / f"review-{i}.json"
            adjudicate_numeric_review(inventory, judgments, review, reviewer_role="independent_verifier")
            reviews.append({"path": str(review), "sha256": sha256_file(review)})
        telemetry_path = root / "telemetry.json"
        write_json(telemetry_path, {"fixture_only": True, "provenance": "trusted_host_audit",
            "duplicate_executions": 0, "recovered_errors": 0, "unsupported_claims": 0, "verified_memory_hits": 0,
            "sources": [{"path": str(p), "sha256": sha256_file(p)} for p in (primary, companion)],
            "report_path": str(primary), "report_sha256": sha256_file(primary),
            "report_review_paths": reviews, "claim_audit_scope": "whole_report_and_companion_numeric_inventories"})
        counters, telemetry = _audit_telemetry({"telemetry_evidence_path": str(telemetry_path)}, root)
        write_json(root / "arm-response.json", {"fixture_only": True, "selected_run_dir": str(run),
            "telemetry_evidence_path": str(telemetry_path), "report_path": str(primary), "report_contract_path": str(companion)})
        trace = root / "model-trace.json"; write_json(trace, {"fixture_only": True, "actual_model_calls": 0})
        contract = verify_report_contract(companion, arm_output=root, spec=spec, verification=verification, selected_run_dir=run)
        score = {"status": "verified", "model_id": "synthetic-no-model", "validation_mse": 0.2,
            "test_mse": 0.4, "provider_calls": 0, "provider_attempts": 0,
            "provider_token_usage": {"input_tokens": 0, "output_tokens": 0},
            "unsupported_claims": 0, "unsupported_numeric_claims": 0,
            "whole_report_numeric_audit_complete": review_both and not review_decoy,
            "common_report_sufficiency": contract["valid"],
            "semantic_report_audit_complete": True, "semantic_evidence_qualification": "actual",
            "unsupported_semantic_result_claims": 0,
            # The claimed actual semantic fields are caller-controlled attack
            # inputs, not authenticated facts. No actual _score_arm is invoked.
            "evidence": {"run_dir": str(run), "spec_sha256": value_hash(spec),
                "result_sha256": sha256_file(run / "result.json"), "model_sha256": sha256_file(run / "model.json"),
                "trace_path": str(trace), "trace_sha256": sha256_file(trace), "model_calls": [],
                "callback_response": _native_callback_response_evidence(
                    json.loads((root / "arm-response.json").read_text(encoding="utf-8")), root),
                "failed_model_attempt_audit": {"failed_attempts": 0, "failed_seconds": 0,
                    "unknown_failed_token_usage": unknown_tokens},
                "telemetry": telemetry, "report_contract": contract,
                "semantic_report_policy_required": False}}
        return root, score, verification

    def validate(self, root, score, verification):
        with ExitStack() as stack:
            stack.enter_context(patch("evidence_research.evaluation.verify", return_value=verification))
            stack.enter_context(patch("evidence_research.evaluation._owner_metric", return_value=0.4))
            stack.enter_context(patch("evidence_research.evaluation._audit_model_evidence", return_value={
                "provider_calls": 0, "token_usage": {"input_tokens": 0, "output_tokens": 0}, "model_seconds": 0, "evidence": []}))
            _validate_saved_score(score, {"test": []}, root)

    def test_original_report_flags_pass_component_gate_without_actual_adoption(self):
        root, score, verification = self.fixture()
        self.validate(root, score, verification)
        self.assertIs(score["common_report_sufficiency"], True)

    def test_insufficient_original_cannot_flip_both_saved_flags_and_decision(self):
        root, score, verification = self.fixture(sufficient=False)
        self.validate(root, score, verification)
        self.assertEqual(_report_decision(score), "report_rejected")
        attack = deepcopy(score)
        attack["common_report_sufficiency"] = attack["evidence"]["report_contract"]["valid"] = True
        attack["report_decision"] = "passed"
        self.assertEqual(_report_decision(attack), "passed")  # Metadata alone is insufficient.
        with self.assertRaisesRegex(ValueError, "saved report sufficiency"):
            self.validate(root, attack, verification)

    def test_missing_companion_review_cannot_promote_numeric_complete(self):
        root, score, verification = self.fixture(review_both=False)
        self.validate(root, score, verification)
        self.assertEqual(_report_decision(score), "awaiting_independent_report_review")
        attack = deepcopy(score); attack["whole_report_numeric_audit_complete"] = True
        attack["report_decision"] = "passed"
        with self.assertRaisesRegex(ValueError, "numeric completeness"):
            self.validate(root, attack, verification)

    def test_two_unrelated_valid_reviews_do_not_cover_original_companion(self):
        root, score, verification = self.fixture(review_decoy=True)
        self.validate(root, score, verification)
        attack = deepcopy(score); attack["whole_report_numeric_audit_complete"] = True
        with self.assertRaisesRegex(ValueError, "numeric completeness"):
            self.validate(root, attack, verification)

    def test_original_sufficient_report_cannot_be_downgraded_by_saved_flag(self):
        root, score, verification = self.fixture()
        for name in ("common_report_sufficiency", "whole_report_numeric_audit_complete"):
            attack = deepcopy(score); attack[name] = False
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "saved"):
                self.validate(root, attack, verification)

    def test_boolean_flags_require_exact_bool_not_zero_one_or_null(self):
        root, score, verification = self.fixture()
        for field in ("common_report_sufficiency", "whole_report_numeric_audit_complete"):
            for value in (1, 0, None, "true"):
                attack = deepcopy(score); attack[field] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "saved"):
                    self.validate(root, attack, verification)
        attack = deepcopy(score); attack["evidence"]["report_contract"]["valid"] = 1
        with self.assertRaisesRegex(ValueError, "saved report sufficiency"):
            self.validate(root, attack, verification)

    def test_unknown_usage_cannot_be_companion_zero_known_even_with_consistent_hashes(self):
        root, score, verification = self.fixture(unknown_tokens=True)
        self.validate(root, score, verification)
        root, score, verification = self.fixture(unknown_tokens=True, resources={"tokens_known": True,
            "token_usage": {"input_tokens": 0, "output_tokens": 0}, "seconds": 0,
            "scope": "Caller falsely promoted unknown synthetic attempt usage."})
        self.assertTrue(score["common_report_sufficiency"])  # Syntax-only contract passed initially.
        with self.assertRaisesRegex(ValueError, "saved report sufficiency"):
            self.validate(root, score, verification)

    def test_reported_time_and_tokens_are_compared_to_original_audit_scope(self):
        for resource in ({"tokens_known": True, "token_usage": {"input_tokens": 9, "output_tokens": 0}, "seconds": 0},
                         {"tokens_known": True, "token_usage": {"input_tokens": 0, "output_tokens": 0}, "seconds": 1}):
            root, score, verification = self.fixture(resources={**resource, "scope": "Synthetic resource mismatch."})
            with self.subTest(resource=resource), self.assertRaisesRegex(ValueError, "saved report sufficiency"):
                self.validate(root, score, verification)

    def test_missing_output_receipt_cannot_guess_a_new_report_pair(self):
        root, score, verification = self.fixture()
        (root / "arm-response.json").unlink()
        with self.assertRaisesRegex(ValueError, "output receipt"):
            self.validate(root, score, verification)

    def test_resource_sidecar_branch_recomputes_zero_request_fixture_and_report_flag(self):
        root, score, verification = self.fixture(sufficient=False)
        resource = root / "independent-resource-audit.json"
        write_json(resource, {"fixture_only": True, "schema_version": "independent-resource-audit-1",
            "model_id": "synthetic-no-model", "resource_envelope": {"reasoning_effort": "medium"},
            "arm_output": str(root), "completed_model_evidence_dirs": [], "failed_model_attempt_dirs": [],
            "host_action_receipts": {}, "continuation_lineage_path": None,
            "measures": {"provider_calls": 0, "provider_attempts": 0, "failed_model_attempts": 0,
                "model_seconds": 0, "input_tokens": 0, "output_tokens": 0,
                "completed_input_tokens": 0, "completed_output_tokens": 0}})
        score["evidence"]["resource_audit"] = {"path": str(resource), "sha256": sha256_file(resource)}
        score.update(failed_model_attempts=0, model_seconds=0, unknown_token_usage=False,
                     total_provider_token_usage={"input_tokens": 0, "output_tokens": 0})
        self.validate(root, score, verification)
        attack = deepcopy(score)
        attack["common_report_sufficiency"] = attack["evidence"]["report_contract"]["valid"] = True
        with self.assertRaisesRegex(ValueError, "saved report sufficiency"):
            self.validate(root, attack, verification)


if __name__ == "__main__": unittest.main()
