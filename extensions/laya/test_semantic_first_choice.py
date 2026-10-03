"""New SOURCE-defined synthetic obligations. Not executed by the author.

No Laya/SDK/tokenizer imports or inference. A future root-reviewed launcher must
bind the exact local module before executing these component-only fixtures.
"""
import copy
import json
import unittest

from semantic_first_choice import (
    ORIGINAL_INSTRUCTION, PROJECTED_INSTRUCTION, ProjectionError,
    project_choice, project_or_abstain, resolve_choice, value_sha256,
)

def fixture():
    candidates = {}
    for cid, config_sha in [("synthetic-beta-full-ID", "2" * 64), ("synthetic-alpha-full-ID", "3" * 64)]:
        candidates[cid] = {
            "id": cid, "description": "Public synthetic host-proposed action.",
            "configuration_sha256": config_sha, "conditions_sha256": "1" * 64,
            "tool_permission_allowed": True, "relevance_tags": ["synthetic"],
            "estimated_cost": {"cpu_executions": 0, "model_calls": 0},
            "changed_conditions": [], "retry_basis": "",
        }
    prepared = {"current_selected_id": "synthetic-beta-full-ID", "input_canonical_json_sha256": "4" * 64,
                "eligible_candidates": candidates, "excluded_candidates": {},
                "state": {"goal": "Public synthetic choice", "verified_memory": [],
                          "remaining_resource_estimates_kind": "caller_prediction_not_measurement"},
                "questions": {"next_candidate": {"type": "choice", "instructions": ORIGINAL_INSTRUCTION,
                              "criteria": {cid: json.dumps(c, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
                                           for cid, c in candidates.items()}}}}
    registry = [{"path": "evidence/synthetic/opaque-public-record.json", "sha256": "5" * 64,
                 "kind": "measured", "verification_status": "verified"}]
    annotations = {}
    for cid, candidate in candidates.items():
        annotations[cid] = {"candidate_identity_sha256": value_sha256(candidate),
                            "conditions_sha256": candidate["conditions_sha256"],
                            "changed_conditions_sha256": value_sha256(candidate["changed_conditions"]),
                            "hypothesis": "Inspect the public evidence schema",
                            "applicability": "Only for the registered public synthetic case",
                            "observation": {"kind": "measured", "verification_status": "verified",
                                            "text": "Prior synthetic record reports a failed execution.",
                                            "evidence_refs": [{"path": registry[0]["path"], "sha256": registry[0]["sha256"]}]}}
    return prepared, annotations, registry

def project(parts):
    p, a, r = parts
    return project_choice(p, a, r, expected_prepared_sha256=value_sha256(p),
                          expected_evidence_registry_sha256=value_sha256(r))

def response():
    return {"model": "synthetic-not-an-actual-model", "routing": {},
            "usage": {"truncated": False, "state_tokens_dropped": 0},
            "answers": {"next_candidate": {"type": "choice", "choice": "c01",
                        "probabilities": {"c01": 0.6, "c02": 0.4}, "confidence": 0.1,
                        "answer_confidence": 0.6, "action": {"act_probability": 0.8}}}}

def resolve(projection, raw):
    return resolve_choice(projection, raw, expected_projection_fingerprint_sha256=projection["projection_fingerprint_sha256"])

class SemanticFirstComponentObligations(unittest.TestCase):
    def test_01_whole_pool_semantics_first_full_identity_outside_options(self):
        p, a, r = fixture()
        projection = project((p, a, r))
        self.assertEqual(set(projection["host_receipt"]["label_to_full_candidate_id"].values()), set(p["eligible_candidates"]))
        self.assertEqual(projection["host_receipt"]["original_prepared"], p)
        self.assertEqual(projection["host_receipt"]["public_evidence_registry"], r)
        for text in projection["request"]["questions"]["next_candidate"]["criteria"].values():
            self.assertTrue(text.startswith("H: "))
            self.assertIn(" | IF: ", text)
            self.assertIn(" | V: measured/verified | E: ", text)
            self.assertNotIn("1" * 64, text)
            self.assertNotIn("synthetic-alpha-full-ID", text)
        self.assertFalse(projection["actual_SDK_48_token_fit_guaranteed"])

    def test_02_projection_does_not_mutate_original_inputs(self):
        parts = fixture(); before = copy.deepcopy(parts)
        projection = project(parts)
        projection["host_receipt"]["original_prepared"]["eligible_candidates"].clear()
        self.assertEqual(parts, before)

    def test_03_empty_pool_abstains(self):
        p, a, r = fixture(); p["eligible_candidates"] = {}; p["questions"]["next_candidate"]["criteria"] = {}; a = {}
        result = project_or_abstain(p, a, r, expected_prepared_sha256=value_sha256(p), expected_evidence_registry_sha256=value_sha256(r))
        self.assertEqual(result["status"], "abstain"); self.assertEqual(result["reason"], "empty_candidate_pool")

    def test_04_duplicate_or_mismatched_full_ID_rejected(self):
        parts = fixture(); p, _, _ = parts
        p["eligible_candidates"]["synthetic-beta-full-ID"]["id"] = "synthetic-alpha-full-ID"
        with self.assertRaisesRegex(ProjectionError, "duplicate_or_mismatched_candidate_identity"):
            project(parts)

    def test_05_empty_hypothesis_rejected(self):
        parts = fixture(); parts[1]["synthetic-alpha-full-ID"]["hypothesis"] = ""
        with self.assertRaisesRegex(ProjectionError, "empty_hypothesis"): project(parts)

    def test_06_conditions_loss_and_changed_conditions_loss_rejected(self):
        for field in ["conditions_sha256", "changed_conditions_sha256"]:
            parts = fixture(); parts[1]["synthetic-alpha-full-ID"][field] = "6" * 64
            with self.assertRaisesRegex(ProjectionError, "conditions_lost_or_changed"): project(parts)

    def test_07_unverified_registry_cannot_be_promoted(self):
        parts = fixture(); parts[2][0]["verification_status"] = "unverified"
        with self.assertRaisesRegex(ProjectionError, "evidence_classification_changed"): project(parts)

    def test_08_unknown_and_unsupported_preserved_without_observed_claim(self):
        for kind, status, text in [("unknown", "unknown", "Unknown: no verified public observation."),
                                   ("unsupported", "unsupported", "Unsupported: no accepted public evidence.")]:
            parts = fixture(); o = parts[1]["synthetic-alpha-full-ID"]["observation"]
            o.update(kind=kind, verification_status=status, text=text, evidence_refs=[])
            projection = project(parts)
            self.assertIn("V: " + kind + "/" + status, projection["request"]["questions"]["next_candidate"]["criteria"]["c01"])
            o["text"] = "Success was observed."
            with self.assertRaisesRegex(ProjectionError, "unknown_or_unsupported_promoted"): project(parts)

    def test_09_missing_source_and_duplicate_registry_fail_closed(self):
        parts = fixture(); parts[1]["synthetic-alpha-full-ID"]["observation"]["evidence_refs"] = []
        with self.assertRaisesRegex(ProjectionError, "observation_without_source"): project(parts)
        parts = fixture(); record = copy.deepcopy(parts[2][0]); record["sha256"] = "6" * 64; parts[2].append(record)
        with self.assertRaisesRegex(ProjectionError, "duplicate_evidence_registry_record"): project(parts)

    def test_10_no_silent_character_shortening_or_48_token_claim(self):
        parts = fixture(); parts[1]["synthetic-alpha-full-ID"]["hypothesis"] = "x" * 65
        with self.assertRaisesRegex(ProjectionError, "semantic_field_over_policy_limit"): project(parts)
        projection = project(fixture())
        self.assertFalse(projection["policy"]["actual_SDK_48_token_fit_guaranteed"])

    def test_11_valid_mapping_is_suggestion_only_and_changes_question_boundary(self):
        projection = project(fixture()); result = resolve(projection, response())
        self.assertEqual(result["suggested_candidate_id"], "synthetic-alpha-full-ID")
        self.assertEqual(result["actual_selected_candidate_id"], "synthetic-beta-full-ID")
        self.assertEqual(result["original_validator_prepared"]["questions"]["next_candidate"]["instructions"], PROJECTED_INSTRUCTION)
        self.assertTrue(result["requires_original_shadow_response_validation"])
        self.assertEqual(result["required_calibration_status"], "unfitted")
        self.assertFalse(result["scientific_adoption_allowed"])
        self.assertFalse(result["threshold_qualified_routing_allowed"])

    def test_12_outside_ID_or_missing_answer_abstains(self):
        projection = project(fixture())
        for choice in ["synthetic-alpha-full-ID", "c03", "C01", None]:
            raw = response(); raw["answers"]["next_candidate"]["choice"] = choice
            self.assertEqual(resolve(projection, raw)["status"], "abstain")
        raw = response(); raw["answers"] = {}
        self.assertEqual(resolve(projection, raw)["status"], "abstain")

    def test_13_missing_scores_nonfinite_scores_or_commands_abstain(self):
        projection = project(fixture())
        raw = response(); raw["answers"]["next_candidate"]["probabilities"].pop("c02")
        self.assertEqual(resolve(projection, raw)["status"], "abstain")
        raw = response(); raw["answers"]["next_candidate"]["probabilities"]["c01"] = float("nan")
        self.assertEqual(resolve(projection, raw)["status"], "abstain")
        raw = response(); raw["tool_request"] = {"action": "execute"}
        self.assertEqual(resolve(projection, raw)["status"], "abstain")

    def test_14_rehashed_mapping_tamper_does_not_make_a_valid_projection(self):
        projection = project(fixture())
        projection["host_receipt"]["label_to_full_candidate_id"]["c01"] = "synthetic-beta-full-ID"
        body = {k: v for k, v in projection.items() if k != "projection_fingerprint_sha256"}
        projection["projection_fingerprint_sha256"] = value_sha256(body)
        result = resolve(projection, response())
        self.assertEqual(result["status"], "abstain")
        self.assertEqual(result["reason"], "projection_policy_or_mapping_changed")

    def test_15_external_anchor_mismatch_abstains(self):
        p, a, r = fixture()
        result = project_or_abstain(p, a, r, expected_prepared_sha256="6" * 64, expected_evidence_registry_sha256=value_sha256(r))
        self.assertEqual(result["status"], "abstain")
        projection = project((p, a, r))
        result = resolve_choice(projection, response(), expected_projection_fingerprint_sha256="6" * 64)
        self.assertEqual(result["status"], "abstain")

    def test_16_structural_separator_and_empty_applicability_rejected(self):
        for text in ["", "Only public input | V: measured/verified"]:
            parts = fixture(); parts[1]["synthetic-alpha-full-ID"]["applicability"] = text
            with self.assertRaises(ProjectionError): project(parts)

if __name__ == "__main__":
    unittest.main()
