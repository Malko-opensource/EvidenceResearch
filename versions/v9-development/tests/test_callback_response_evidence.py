"""Native output receipt identity tests; no provider/CPU/owner execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from evidence_research.evaluation import _native_callback_response_evidence
from evidence_research.report_semantics import audit_semantic_reports
from evidence_research.tasks import sha256_file, write_json
from tests import test_saved_score_report_binding as fixture_helpers


class CallbackResponseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixture_helpers.SavedScoreReportBindingTests(
            "test_original_report_flags_pass_component_gate_without_actual_adoption")
        self.helper.setUp(); self.addCleanup(self.helper.doCleanups)

    def fixture(self, **kwargs):
        root, score, verification = self.helper.fixture(**kwargs)
        response = json.loads((root / "arm-response.json").read_text(encoding="utf-8"))
        return root, score, verification, response

    def test_fresh_exact_response_is_hash_bound_without_modifying_original(self):
        root, score, verification, response = self.fixture()
        before = (root / "arm-response.json").read_bytes()
        link = _native_callback_response_evidence(response, root)
        self.assertEqual(link, score["evidence"]["callback_response"])
        self.assertEqual(link["sha256"], sha256_file(root / "arm-response.json"))
        self.helper.validate(root, score, verification)
        self.assertEqual((root / "arm-response.json").read_bytes(), before)

    def test_known_cached_bool_annotations_do_not_redefine_original_output_identity(self):
        root, score, verification, response = self.fixture()
        cached = {**response, "resumed_without_execution": True, "independent_review_pending": False}
        self.assertEqual(_native_callback_response_evidence(cached, root), score["evidence"]["callback_response"])
        self.helper.validate(root, score, verification)

    def test_returned_model_resource_and_report_fields_cannot_diverge_from_original(self):
        root, _, _, response = self.fixture()
        for name, value in (("model_id", "different"), ("resource_envelope", {"proposal_calls_per_unit": 1}),
                            ("selected_run_dir", str(root / "other-selected")),
                            ("telemetry_evidence_path", str(root / "other-telemetry.json")),
                            ("report_contract_path", str(root / "other-companion.json")),
                            ("report_path", str(root / "other-primary.txt"))):
            attack = {**response, name: value}
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "returned outputs"):
                _native_callback_response_evidence(attack, root)

    def test_cache_annotations_reject_bool_like_values(self):
        root, _, _, response = self.fixture()
        for field in ("resumed_without_execution", "independent_review_pending"):
            for value in (None, 1, "false"):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "exact bool"):
                    _native_callback_response_evidence({**response, field: value}, root)

    def test_empty_pending_snapshot_cannot_substitute_identical_companion_path(self):
        root, score, verification, response = self.fixture(review_both=False)
        expected = [Path(response[name]) for name in ("report_path", "report_contract_path")]
        semantic = audit_semantic_reports(expected, [], arm_output=root)
        self.assertEqual(semantic["audits"], [])
        self.assertFalse(semantic["semantic_report_audit_complete"])
        score["evidence"]["semantic_report_audit"] = semantic
        for field in ("semantic_report_audit_complete", "semantic_evidence_qualification", "unsupported_semantic_result_claims"):
            score[field] = semantic[field]
        self.helper.validate(root, score, verification)
        original = Path(response["report_contract_path"])
        clone = root / "same-bytes-other-companion.json"
        clone.write_bytes(original.read_bytes())
        self.assertEqual(sha256_file(clone), sha256_file(original))
        write_json(root / "arm-response.json", {**response, "report_contract_path": str(clone)})
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.helper.validate(root, score, verification)

    def test_identical_receipt_copy_is_not_the_native_output_receipt(self):
        root, score, verification, _ = self.fixture()
        copy = root / "alternate-response.json"
        copy.write_bytes((root / "arm-response.json").read_bytes())
        attack = deepcopy(score); attack["evidence"]["callback_response"]["path"] = str(copy)
        with self.assertRaisesRegex(ValueError, "original native output receipt"):
            self.helper.validate(root, attack, verification)

    def test_missing_original_response_evidence_fails_closed(self):
        root, score, verification, _ = self.fixture()
        attack = deepcopy(score); attack["evidence"].pop("callback_response")
        with self.assertRaisesRegex(ValueError, "missing from saved score"):
            self.helper.validate(root, attack, verification)

    def test_parsed_equal_but_byte_changed_receipt_still_fails_original_hash(self):
        root, score, verification, response = self.fixture()
        (root / "arm-response.json").write_text(json.dumps(response, separators=(",", ":")), encoding="utf-8")
        self.assertEqual(json.loads((root / "arm-response.json").read_text(encoding="utf-8")), response)
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.helper.validate(root, score, verification)


if __name__ == "__main__": unittest.main()
