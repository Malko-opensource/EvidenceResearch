"""Original report-set binding on real validators over synthetic file fixtures.

These engineering reviews keep component_fixture qualification. They do not
pretend that a complete synthetic review supports actual adoption. The primary
attack replaces the companion with another authentically reviewed local text,
maintains two reviews, and re-matches saved aggregate fields.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from evidence_research.evaluation import _audit_telemetry, adjudicate_numeric_review, prepare_numeric_review
from evidence_research.report_contract import verify_report_contract
from evidence_research.report_semantics import (adjudicate_semantic_review, audit_semantic_reports,
    prepare_semantic_review, semantic_claim)
from evidence_research.tasks import sha256_file, write_json
from tests import test_saved_score_report_binding as fixture_helpers


class SavedSemanticReportBindingTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixture_helpers.SavedScoreReportBindingTests(
            "test_original_report_flags_pass_component_gate_without_actual_adoption")
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)

    def fixture(self):
        root, score, verification = self.helper.fixture()
        response = json.loads((root / "arm-response.json").read_text(encoding="utf-8"))
        primary = Path(response["report_path"])
        companion = Path(response["report_contract_path"])
        # Companion prose is deliberately insufficient as a research-report
        # contract. Its original path is still a required semantic output.
        companion.write_text("This procedure is a bounded planning illustration.\n", encoding="utf-8")
        links = []
        for i, path in enumerate((primary, companion)):
            inventory = root / f"replacement-numeric-inventory-{i}.json"
            content = prepare_numeric_review(path, inventory)
            self.assertEqual(content["items"], [])
            review = root / f"replacement-numeric-review-{i}.json"
            adjudicate_numeric_review(inventory, [], review, reviewer_role="independent_verifier")
            links.append({"path": str(review), "sha256": sha256_file(review)})
        telemetry_path = Path(score["evidence"]["telemetry"]["path"])
        telemetry = json.loads(telemetry_path.read_text(encoding="utf-8"))
        telemetry["sources"] = [{"path": str(path), "sha256": sha256_file(path)} for path in (primary, companion)]
        telemetry["report_review_paths"] = links
        write_json(telemetry_path, telemetry)
        _, audited = _audit_telemetry({"telemetry_evidence_path": str(telemetry_path)}, root)
        score["evidence"]["telemetry"] = audited
        run = Path(score["evidence"]["run_dir"])
        spec = json.loads((run / "registered_spec.json").read_text(encoding="utf-8"))
        score["evidence"]["report_contract"] = verify_report_contract(companion, arm_output=root,
            spec=spec, verification=verification, selected_run_dir=run)
        score["common_report_sufficiency"] = False
        return root, score, verification, primary, companion

    def review(self, root, report, name):
        inventory = root / (name + "-semantic-inventory.json")
        record = prepare_semantic_review(report, inventory)
        rows = []
        for unit in record["units"]:
            claim = semantic_claim(unit, kind="method", outcome="classified_nonresult",
                rationale="Explicit bounded fixture prose; no execution or model-performance assertion.")
            rows.append({"unit_id": unit["unit_id"], "outcome": "reviewed",
                "rationale": "Read the complete synthetic text span.",
                "exhaustive_result_claim_mapping": True, "claims": [claim]})
        path = root / (name + "-semantic-review.json")
        adjudicate_semantic_review(inventory, rows, path, arm_output=root, reviewer_role="independent_verifier")
        return path

    def attach(self, score, report_paths, review_paths, root):
        audit = audit_semantic_reports(report_paths, review_paths, arm_output=root)
        self.assertEqual(audit["semantic_evidence_qualification"], "component_fixture")
        self.assertFalse(audit["semantic_report_audit_complete"])
        score["evidence"]["semantic_report_audit"] = audit
        for name in ("semantic_report_audit_complete", "semantic_evidence_qualification",
                     "unsupported_semantic_result_claims"):
            score[name] = audit[name]
        return audit

    def test_original_primary_and_companion_snapshot_reconstructs_without_actual_promotion(self):
        root, score, verification, primary, companion = self.fixture()
        reviews = [self.review(root, path, name) for path, name in ((primary, "primary"), (companion, "companion"))]
        self.attach(score, [primary, companion], reviews, root)
        self.helper.validate(root, score, verification)
        self.assertFalse(score["semantic_report_audit_complete"])

    def test_two_authentic_reviews_cannot_substitute_unrelated_report_for_original_companion(self):
        root, score, verification, primary, companion = self.fixture()
        decoy = root / "unrelated-authentic-report.txt"
        decoy.write_text("This method is an independent planning illustration.\n", encoding="utf-8")
        reviews = [self.review(root, path, name) for path, name in ((primary, "primary"), (decoy, "decoy"))]
        audit = self.attach(score, [primary, decoy], reviews, root)
        self.assertEqual(len(audit["audits"]), 2)
        self.assertEqual(audit["pending_items"], 0)
        self.assertEqual(audit["unsupported_semantic_result_claims"], 0)
        # Both reviews are genuine fixed-validator fixtures and the saved top
        # fields match their recomputed aggregate. Only original set binding
        # distinguishes this substitution; no eligibility is monkeypatched.
        with self.assertRaisesRegex(ValueError, "unexpected report"):
            self.helper.validate(root, score, verification)

    def test_missing_companion_stays_incomplete_instead_of_becoming_a_pass(self):
        root, score, verification, primary, companion = self.fixture()
        review = self.review(root, primary, "primary")
        audit = self.attach(score, [primary, companion], [review], root)
        self.assertEqual(audit["pending_items"], 1)
        self.helper.validate(root, score, verification)
        attack = deepcopy(score)
        attack["semantic_report_audit_complete"] = True
        attack["evidence"]["semantic_report_audit"]["semantic_report_audit_complete"] = True
        with self.assertRaisesRegex(ValueError, "semantic evidence aggregate"):
            self.helper.validate(root, attack, verification)

    def test_later_companion_review_cannot_upgrade_an_immutable_pending_snapshot(self):
        root, score, verification, primary, companion = self.fixture()
        first = self.review(root, primary, "primary")
        audit = self.attach(score, [primary, companion], [first], root)
        before = deepcopy(audit)
        self.review(root, companion, "semantic-companion-review-later")
        self.helper.validate(root, score, verification)
        self.assertEqual(score["evidence"]["semantic_report_audit"], before)
        self.assertEqual(len(before["audits"]), 1)
        self.assertEqual(before["pending_items"], 1)


if __name__ == "__main__": unittest.main()
