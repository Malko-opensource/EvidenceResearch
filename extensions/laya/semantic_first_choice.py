"""Pure, prospective input projection. No Laya imports, I/O or model execution.

Host anchors must originate outside this function. Matching a caller-supplied
hash authenticates values against that anchor, not the truth of its declarations.
The full d40 host eligibility gate and subsequent original response validation
remain required. This new question shape is always unqualified here.
"""
import hashlib
import json
import math

SCHEMA = "laya-semantic-first-choice-projection-1"
ADAPTER_SHA256 = "d40fd186d9c872018f77f58bbb6292f93f62fb4c9bb8f95a4ab7d12fabb635c6"
POLICY = {
    "schema": SCHEMA,
    "original_adapter_sha256": ADAPTER_SHA256,
    "label_policy": "c + zero-padded sorted-full-ID ordinal; whole pool retained",
    "option_order": ["minimal_host_label", "proposed_hypothesis", "applicability", "evidence_kind_and_verification", "public_prior_observation"],
    "maximum_text_codepoints": {"hypothesis": 64, "applicability": 48, "observation": 80},
    "text_shortening": "reject overlong fields; never silently slice",
    "actual_SDK_48_token_fit_guaranteed": False,
    "host_gate_or_criterion_changes": False,
    "threshold_qualified_routing_allowed": False,
    "annotation_truth_qualification": "host-declared public links; formatter does not verify source content",
}
ORIGINAL_INSTRUCTION = "Suggest the most relevant eligible next research candidate. The descriptions and cost estimates are proposals. Prior measurements and failures are not promises of future success."
PROJECTED_INSTRUCTION = ORIGINAL_INSTRUCTION + " Short labels refer to the complete host-eligible pool. H is a proposed hypothesis, IF its applicability, V a host declaration about prior evidence, and E a prior observation. No score represents future task success."
CANDIDATE_KEYS = {"id", "description", "configuration_sha256", "conditions_sha256", "tool_permission_allowed", "relevance_tags", "estimated_cost", "changed_conditions", "retry_basis"}
PREPARED_KEYS = {"current_selected_id", "input_canonical_json_sha256", "eligible_candidates", "excluded_candidates", "state", "questions"}
KINDS = {"measured", "literature", "inference", "unexecuted", "unknown", "unsupported"}
VERIFICATION = {"verified", "unverified", "not_run", "unknown", "unsupported"}
NO_OBSERVATION = {
    "unknown": ("unknown", "Unknown: no verified public observation."),
    "unsupported": ("unsupported", "Unsupported: no accepted public evidence."),
    "unexecuted": ("not_run", "Unexecuted proposal; no observed outcome."),
}

class ProjectionError(ValueError):
    """Finite reason code only; no input or private values in the exception."""

def _need(condition, reason):
    if not condition:
        raise ProjectionError(reason)

def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        raise ProjectionError("non_json_or_nonfinite_value") from None

def value_sha256(value):
    try:
        return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()
    except UnicodeError:
        raise ProjectionError("invalid_unicode_value") from None

def _copy(value):
    return json.loads(_canonical(value))

def _digest(value):
    _need(type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value), "invalid_digest")
    return value

def _text(value, reason, maximum=None):
    _need(type(value) is str and bool(value.strip()) and value == value.strip(), reason)
    _need(not any(ord(c) < 32 or ord(c) == 127 for c in value), reason)
    if maximum is not None:
        _need(len(value) <= maximum, "semantic_field_over_policy_limit")
    return value

def _host_text(value, reason):
    # Preserve the d40 host text rule for original values. Only the new short
    # annotation fields have stricter formatting bounds; no original ID or
    # description is silently trimmed or newly rejected for whitespace.
    _need(type(value) is str and bool(value.strip()), reason)
    return value

def _ref(value):
    _need(type(value) is dict and set(value) == {"path", "sha256"}, "invalid_evidence_ref")
    _host_text(value["path"], "invalid_evidence_ref")
    _digest(value["sha256"])
    return (value["path"], value["sha256"])

def _semantic_text(value, reason, maximum):
    value = _text(value, reason, maximum)
    _need("|" not in value, "semantic_field_contains_structural_separator")
    return value

def _validate_prepared(prepared, expected_sha256):
    _digest(expected_sha256)
    _need(value_sha256(prepared) == expected_sha256, "prepared_external_anchor_mismatch")
    _need(type(prepared) is dict and set(prepared) == PREPARED_KEYS, "prepared_shape_mismatch")
    _digest(prepared["input_canonical_json_sha256"])
    current = _host_text(prepared["current_selected_id"], "missing_current_selection")
    pool = prepared["eligible_candidates"]
    excluded = prepared["excluded_candidates"]
    _need(type(pool) is dict and bool(pool), "empty_candidate_pool")
    _need(type(excluded) is dict and not set(pool).intersection(excluded), "invalid_excluded_candidates")
    _need(current in pool or current in excluded, "missing_original_current_identity")
    _need(type(prepared["state"]) is dict, "invalid_public_state")
    question = prepared["questions"]
    _need(type(question) is dict and set(question) == {"next_candidate"}, "original_question_mismatch")
    q = question["next_candidate"]
    _need(type(q) is dict and set(q) == {"type", "instructions", "criteria"}, "original_question_mismatch")
    _need(q["type"] == "choice" and q["instructions"] == ORIGINAL_INSTRUCTION, "original_question_mismatch")
    _need(type(q["criteria"]) is dict and set(q["criteria"]) == set(pool), "original_question_pool_mismatch")
    for cid, candidate in pool.items():
        _host_text(cid, "invalid_candidate_id")
        _need(type(candidate) is dict and set(candidate) == CANDIDATE_KEYS and candidate["id"] == cid, "duplicate_or_mismatched_candidate_identity")
        _host_text(candidate["description"], "empty_original_description")
        _digest(candidate["conditions_sha256"])
        _digest(candidate["configuration_sha256"])
        _need(type(candidate["changed_conditions"]) is list, "missing_changed_conditions")
        _need(type(candidate["tool_permission_allowed"]) is bool and candidate["tool_permission_allowed"], "ineligible_candidate_permission")
        _need(type(candidate["retry_basis"]) is str and type(candidate["relevance_tags"]) is list, "original_gate_fields_missing")
        _need(type(candidate["estimated_cost"]) is dict, "original_gate_fields_missing")
        _need(q["criteria"][cid] == _canonical(candidate), "original_candidate_text_identity_mismatch")
    # No eligibility, retry, cost or source truth is recomputed here. The d40
    # prepare_public_request must actually run and be authenticated by the host.
    return pool

def project_choice(prepared, annotations, evidence_registry, *, expected_prepared_sha256, expected_evidence_registry_sha256):
    """Project an externally anchored d40 prepared input to a new typed choice.

    Registry records and annotations are authenticated caller declarations; this
    pure function cannot read their paths or qualify scientific evidence.
    """
    pool = _validate_prepared(prepared, expected_prepared_sha256)
    _digest(expected_evidence_registry_sha256)
    _need(value_sha256(evidence_registry) == expected_evidence_registry_sha256, "evidence_registry_external_anchor_mismatch")
    _need(type(evidence_registry) is list, "invalid_evidence_registry")
    registry, registry_paths = {}, set()
    for entry in evidence_registry:
        _need(type(entry) is dict and set(entry) == {"path", "sha256", "kind", "verification_status"}, "invalid_evidence_registry")
        key = _ref({"path": entry["path"], "sha256": entry["sha256"]})
        _need(key not in registry and entry["path"] not in registry_paths, "duplicate_evidence_registry_record")
        _need(entry["kind"] in KINDS and entry["verification_status"] in VERIFICATION, "invalid_evidence_classification")
        registry[key] = entry
        registry_paths.add(entry["path"])
    _need(type(annotations) is dict and set(annotations) == set(pool), "annotation_pool_mismatch")
    label_map, criteria = {}, {}
    width = max(2, len(str(len(pool))))
    for ordinal, cid in enumerate(sorted(pool), 1):
        candidate = pool[cid]
        a = annotations[cid]
        _need(type(a) is dict and set(a) == {"candidate_identity_sha256", "conditions_sha256", "changed_conditions_sha256", "hypothesis", "applicability", "observation"}, "annotation_shape_mismatch")
        _need(a["candidate_identity_sha256"] == value_sha256(candidate), "annotation_candidate_identity_mismatch")
        _need(a["conditions_sha256"] == candidate["conditions_sha256"], "annotation_conditions_lost_or_changed")
        _need(a["changed_conditions_sha256"] == value_sha256(candidate["changed_conditions"]), "annotation_changed_conditions_lost_or_changed")
        hypothesis = _semantic_text(a["hypothesis"], "empty_hypothesis", POLICY["maximum_text_codepoints"]["hypothesis"])
        applicability = _semantic_text(a["applicability"], "empty_applicability", POLICY["maximum_text_codepoints"]["applicability"])
        observation = a["observation"]
        _need(type(observation) is dict and set(observation) == {"kind", "verification_status", "text", "evidence_refs"}, "observation_shape_mismatch")
        kind, verified = observation["kind"], observation["verification_status"]
        _need(kind in KINDS and verified in VERIFICATION, "invalid_evidence_classification")
        text = _semantic_text(observation["text"], "empty_observation", POLICY["maximum_text_codepoints"]["observation"])
        refs = observation["evidence_refs"]
        _need(type(refs) is list, "missing_evidence_refs")
        keys = [_ref(ref) for ref in refs]
        _need(len(set(keys)) == len(keys), "duplicate_evidence_ref")
        if kind in NO_OBSERVATION:
            wanted_verification, wanted_text = NO_OBSERVATION[kind]
            _need(verified == wanted_verification and text == wanted_text and not refs, "unknown_or_unsupported_promoted")
        else:
            _need(bool(refs) and verified in {"verified", "unverified"}, "observation_without_source")
            _need(kind != "inference" or verified == "unverified", "inference_promoted_to_verified")
            for key in keys:
                _need(key in registry, "evidence_outside_external_registry")
                record = registry[key]
                _need(record["kind"] == kind and record["verification_status"] == verified, "evidence_classification_changed")
        label = "c" + str(ordinal).zfill(width)
        label_map[label] = cid
        criteria[label] = "H: " + hypothesis + " | IF: " + applicability + " | V: " + kind + "/" + verified + " | E: " + text
    projection = {
        "schema": SCHEMA,
        "policy": _copy(POLICY),
        "policy_sha256": value_sha256(POLICY),
        "qualification": "unqualified_prospective_input_projection",
        "actual_selection_unchanged": True,
        "host_receipt": {"expected_prepared_sha256": expected_prepared_sha256,
                         "expected_evidence_registry_sha256": expected_evidence_registry_sha256,
                         "original_prepared": _copy(prepared), "annotations": _copy(annotations),
                         "public_evidence_registry": _copy(evidence_registry), "label_to_full_candidate_id": label_map},
        "request": {"state": _copy(prepared["state"]),
                    "questions": {"next_candidate": {"type": "choice", "instructions": PROJECTED_INSTRUCTION, "criteria": criteria}}},
        "scientific_adoption_allowed": False,
        "threshold_qualified_routing_allowed": False,
        "actual_SDK_48_token_fit_guaranteed": False,
    }
    projection["projection_fingerprint_sha256"] = value_sha256(projection)
    return projection

def _authenticated_projection(projection, expected_fingerprint):
    _digest(expected_fingerprint)
    _need(type(projection) is dict and "projection_fingerprint_sha256" in projection, "missing_projection_fingerprint")
    body = {k: v for k, v in projection.items() if k != "projection_fingerprint_sha256"}
    _need(projection["projection_fingerprint_sha256"] == expected_fingerprint == value_sha256(body), "projection_external_anchor_mismatch")
    host = projection["host_receipt"]
    rebuilt = project_choice(host["original_prepared"], host["annotations"], host["public_evidence_registry"],
                             expected_prepared_sha256=host["expected_prepared_sha256"],
                             expected_evidence_registry_sha256=host["expected_evidence_registry_sha256"])
    _need(rebuilt == projection, "projection_policy_or_mapping_changed")
    return host["original_prepared"], host["label_to_full_candidate_id"]

def _number(v):
    return type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1

def resolve_choice(projection, raw_response, *, expected_projection_fingerprint_sha256):
    """Resolve whole short-label response to original IDs or return an abstention.

    Mapping is not original validator acceptance. Pass normalized response and
    the returned changed-question prepared context to the original d40 validator
    under an explicitly unfitted calibration config in any future integration.
    Never use the old calibrated question-shape proof for this projection.
    """
    current = None
    try:
        original, mapping = _authenticated_projection(projection, expected_projection_fingerprint_sha256)
        current = original["current_selected_id"]
        _canonical(raw_response)
        _need(type(raw_response) is dict and set(raw_response) == {"model", "answers", "routing", "usage"}, "unexpected_model_response_fields")
        answers = raw_response["answers"]
        _need(type(answers) is dict and set(answers) == {"next_candidate"}, "missing_or_extra_answer")
        answer = answers["next_candidate"]
        _need(type(answer) is dict and set(answer) == {"type", "choice", "probabilities", "confidence", "answer_confidence", "action"}, "malformed_choice_answer")
        _need(answer["type"] == "choice" and type(answer["choice"]) is str and answer["choice"] in mapping, "answer_outside_candidate_labels")
        probabilities = answer["probabilities"]
        _need(type(probabilities) is dict and set(probabilities) == set(mapping), "incomplete_candidate_probabilities")
        _need(all(_number(v) for v in probabilities.values()), "nonfinite_or_invalid_raw_score")
        _need(abs(sum(probabilities.values()) - 1) <= max(0.002, len(mapping) * 0.0001), "raw_probability_sum_mismatch")
        _need(probabilities[answer["choice"]] == max(probabilities.values()), "choice_probability_mismatch")
        _need(_number(answer["confidence"]) and _number(answer["answer_confidence"]), "nonfinite_or_invalid_raw_score")
        _need(type(answer["action"]) is dict and set(answer["action"]) == {"act_probability"} and _number(answer["action"]["act_probability"]), "malformed_action_metadata")
        normalized = _copy(raw_response)
        normalized["answers"]["next_candidate"]["choice"] = mapping[answer["choice"]]
        normalized["answers"]["next_candidate"]["probabilities"] = {mapping[label]: v for label, v in probabilities.items()}
        validator_prepared = _copy(original)
        # Original interpreter computes question shape from instructions. The new
        # instructions expose this boundary instead of reusing old shape identity.
        validator_prepared["questions"] = _copy(projection["request"]["questions"])
        return {"schema": SCHEMA, "status": "labels_resolved_requires_original_unfitted_validation",
                "actual_selected_candidate_id": current, "suggested_candidate_id": mapping[answer["choice"]],
                "projection_fingerprint_sha256": expected_projection_fingerprint_sha256,
                "normalized_sdk_response": normalized, "original_validator_prepared": validator_prepared,
                "requires_original_shadow_response_validation": True, "required_calibration_status": "unfitted",
                "raw_score_kind": "unqualified_model_score_not_task_success_probability",
                "scientific_adoption_allowed": False, "threshold_qualified_routing_allowed": False,
                "actual_SDK_48_token_fit_guaranteed": False}
    except ProjectionError as error:
        reason = str(error)
    except (KeyError, TypeError, ValueError, OverflowError):
        reason = "malformed_projection_or_response"
    return {"schema": SCHEMA, "status": "abstain", "reason": reason,
            "actual_selected_candidate_id": current, "suggested_candidate_id": None,
            "scientific_adoption_allowed": False, "threshold_qualified_routing_allowed": False}

def project_or_abstain(prepared, annotations, evidence_registry, *, expected_prepared_sha256, expected_evidence_registry_sha256):
    """Formatting failure has no request and never selects a different action."""
    try:
        return project_choice(prepared, annotations, evidence_registry,
                              expected_prepared_sha256=expected_prepared_sha256,
                              expected_evidence_registry_sha256=expected_evidence_registry_sha256)
    except ProjectionError as error:
        reason = str(error)
    except (KeyError, TypeError, ValueError, OverflowError):
        reason = "malformed_projection_input"
    current = prepared.get("current_selected_id") if type(prepared) is dict else None
    if type(current) is not str:
        current = None
    return {"schema": SCHEMA, "status": "abstain", "reason": reason,
            "actual_selected_candidate_id": current, "suggested_candidate_id": None,
            "scientific_adoption_allowed": False, "threshold_qualified_routing_allowed": False}
