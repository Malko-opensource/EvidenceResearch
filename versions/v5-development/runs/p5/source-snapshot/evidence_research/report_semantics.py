"""Owner-only semantic result review; never participant self-adjudication.

Every paragraph and JSON string value is inventoried, including claims without
digits. Coverage is mechanical. Mapping natural language to predicates and
identifying every result assertion remains the independent reviewer's explicit
responsibility; this is not a proof of unrestricted natural-language entailment
or reviewer identity. Predicates accept actual pinned artifacts, not LLM scores.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from .tasks import sha256_file, value_hash, write_json
from .verifier import verify

SEMANTIC_SCHEMA_VERSION = "whole-report-semantics-1"
SEMANTIC_POLICY = {"schema_version": SEMANTIC_SCHEMA_VERSION, "required_for_both_arms": True,
    "scope": "all primary-report paragraphs and structured companion JSON keys, string/scalar values; independent result-claim mapping",
    "adoption": "numeric AND semantic inventories complete; both unsupported counts zero",
    "limits": "fixed predicates validate evidence and scope; exhaustive interpretation is an accountable independent reviewer judgement, not automatic NLP entailment or authenticated human identity"}
_RESULT_CUE = re.compile(r"\b(?:best|better|worse|improv\w*|superior|successful|reproduc\w*|replicat\w*|caus\w*|generaliz\w*|measur\w*|execut\w*|validation|verified|evidence|result\w*)\b|개선|재현|인과|일반화|검증|실행|측정|최선|결과", re.I)
_BROAD_EFFECT = re.compile(r"(?:framework|research performance|memory|model replacement|프레임워크|연구 성능|기억|모델 교체).{0,100}(?:improv|superior|caus|benefit|개선|효과|우수)|(?:caus|generaliz|인과|일반화)", re.I | re.S)
_TENTATIVE = re.compile(r"\b(?:may|might|could|suggest|hypothes\w*|propos\w*|plan|would|next|unexecuted|untested|uncertain)\b|가설|제안|추론|가능|미실행|미검증|다음", re.I)
_LIMITATION = re.compile(r"\b(?:not|no|unproven|unavailable|unknown|cannot|insufficient|limited)\b|미입증|없|불가|한계|불확실", re.I)
_REPRODUCTION = re.compile(r"\b(?:reproduced|replicated|independently replicated)\b|재현되|재현했|독립 재현", re.I)
_MINIMUM = re.compile(r"\b(?:best|minimum|lowest|optimal)\b|최선|최소|최적", re.I)
_INDEPENDENT_REPEATS = re.compile(r"\bindependent\s+(?:replicat\w*|repeat\w*|trial\w*)\b|독립.{0,12}(?:반복|재현)", re.I)
_COMPARISON = re.compile(r"\b(?:improved|improvement|better|worse|worsened|outperform\w*|reduced|superior)\b|개선|악화|우수|비교", re.I)
_ASSERTED_RESULT = re.compile(r"\b(?:improved|caused|outperformed|achieved|executed|verified|measured|reproduced|replicated|successful|better|worse|superior|best|minimum|lowest|optimal)\b|개선했|유발|실행했|검증됐|재현했|최선|우수", re.I)
_PAST_RESULT = re.compile(r"\b(?:improved|caused|outperformed|achieved|executed|verified|measured|reproduced|replicated)\b|개선했|유발|실행했|검증됐|재현했", re.I)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=\S)", text) if part.strip()]


def _directly_negated(sentence: str, match) -> bool:
    prefix = sentence[:match.start()]
    return bool(re.search(r"\b(?:not|never|no)\s+(?:[\w-]+\s+){0,3}$|(?:아니|없|미입증).{0,8}$", prefix, re.I))


def _check_nonresult_scope(raw: str, kind: str) -> None:
    """Recognized result assertions cannot vanish under an arbitrary type label.

    These conservative lexical guards supplement, not replace, human semantic
    judgement. Unrecognized assertions remain the reviewer's responsibility.
    """
    for sentence in _sentences(raw):
        assertions = list(_ASSERTED_RESULT.finditer(sentence)); broad = _BROAD_EFFECT.search(sentence)
        if kind == "method" and (assertions or broad or _REPRODUCTION.search(sentence)):
            raise ValueError("recognized result assertion cannot be excluded as method")
        if kind == "proposal":
            if (assertions or broad or _RESULT_CUE.search(sentence)) and not _TENTATIVE.search(sentence):
                raise ValueError("every result-bearing proposal sentence must itself be tentative")
            if any(not _directly_negated(sentence, match) for match in _PAST_RESULT.finditer(sentence)):
                raise ValueError("an asserted completed result cannot be excluded as a proposal")
        if kind == "limitation":
            if any(not _directly_negated(sentence, match) for match in assertions):
                raise ValueError("affirmative result assertion cannot be excluded as a limitation")
            if broad and not re.search(r"\b(?:unproven|unknown|unavailable|not demonstrated|not established|no evidence|cannot establish)\b|미입증|불확실|입증.{0,4}없", sentence, re.I):
                raise ValueError("limitation must locally restrict the same general/causal assertion")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _link(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def _checked_link(item: dict, root: Path | None = None) -> Path:
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("semantic evidence must have exact path/hash fields")
    path = Path(item["path"]).resolve()
    if root is not None and not path.is_relative_to(root.resolve()):
        raise ValueError("semantic evidence escaped the arm directory")
    if not path.is_file() or sha256_file(path) != item["sha256"]:
        raise ValueError("semantic source hash changed")
    return path


def _json_strings(source: str, offset: int = 0) -> list[dict]:
    """Parse source offsets, so repeated/escaped strings are unambiguous."""
    json.loads(source)
    decoder = json.JSONDecoder(); pos = 0; items = []
    def space():
        nonlocal pos
        while pos < len(source) and source[pos].isspace(): pos += 1
    def value(pointer):
        nonlocal pos
        space(); start = pos; ch = source[pos]
        if ch == '{':
            pos += 1; space()
            if source[pos] == '}': pos += 1; return
            while True:
                space(); key_start = pos; key, end = decoder.raw_decode(source, pos); pos = end; space()
                child_pointer = pointer + '/' + str(key).replace('~', '~0').replace('/', '~1')
                items.append({"unit_kind": "json_key", "pointer": child_pointer,
                    "start": offset+key_start, "end": offset+end, "text": source[key_start:end], "decoded_text": key})
                if source[pos] != ':': raise ValueError("invalid JSON object")
                pos += 1; value(child_pointer); space()
                if source[pos] == '}': pos += 1; return
                pos += 1
        elif ch == '[':
            pos += 1; space(); index = 0
            if source[pos] == ']': pos += 1; return
            while True:
                value(pointer + '/' + str(index)); index += 1; space()
                if source[pos] == ']': pos += 1; return
                pos += 1
        else:
            decoded, end = decoder.raw_decode(source, pos); pos = end
            if isinstance(decoded, str):
                items.append({"unit_kind": "json_string", "pointer": pointer,
                    "start": offset + start, "end": offset + end, "text": source[start:end], "decoded_text": decoded})
            else:
                items.append({"unit_kind": "json_scalar", "pointer": pointer,
                    "start": offset+start, "end": offset+end, "text": source[start:end], "decoded_text": source[start:end]})
    value(""); space()
    if pos != len(source): raise ValueError("unparsed JSON suffix")
    return items


def semantic_units(text: str, report_sha256: str) -> list[dict]:
    """All nonempty textual paragraphs, and every JSON *value* string leaf.

    JSON keys and scalar values are also inventoried; a qualitative assertion
    encoded as an object key and a boolean cannot escape semantic review.
    An explicit structural unit prevents a pure numeric JSON document from being
    mistaken for an empty report. Fenced JSON is parsed as JSON rather than prose.
    """
    blocks = []
    try:
        json.loads(text)
    except (ValueError, TypeError):
        cursor = 0
        for match in re.finditer(r"(?m)^```json[^\n]*\n([\s\S]*?)^```[ \t]*$", text):
            blocks.append((cursor, match.start(), False)); blocks.append((match.start(1), match.end(1), True)); cursor = match.end()
        blocks.append((cursor, len(text), False))
    else:
        blocks = [(0, len(text), True)]
    units = []
    for start, end, is_json in blocks:
        body = text[start:end]
        if is_json:
            units.extend(_json_strings(body, start))
            units.append({"unit_kind": "json_structure", "pointer": "", "start": start,
                "end": end, "text": body, "decoded_text": "JSON structural punctuation; keys, strings and scalar values are separate units"})
        else:
            for match in re.finditer(r"\S[\s\S]*?(?=\n[ \t]*\n|\Z)", body):
                raw = match.group(); right = len(raw.rstrip()); raw = raw[:right]
                if raw:
                    units.append({"unit_kind": "paragraph", "pointer": None, "start": start+match.start(),
                        "end": start+match.start()+right, "text": raw, "decoded_text": raw})
    for unit in units:
        unit["unit_id"] = value_hash({"report_sha256": report_sha256, **unit})
    return sorted(units, key=lambda u: (u["start"], u["end"], u["unit_kind"]))


def prepare_semantic_review(report_path: Path, output_path: Path) -> dict:
    report_path, output_path = Path(report_path).resolve(), Path(output_path).resolve()
    record = {"schema_version": SEMANTIC_SCHEMA_VERSION, "report": _link(report_path),
        "predicate_source": _link(Path(__file__)),
        "units": semantic_units(report_path.read_text(encoding="utf-8"), sha256_file(report_path)),
        "scope": SEMANTIC_POLICY["scope"]}
    if not record["units"]: raise ValueError("an empty report cannot have complete semantic coverage")
    if output_path.exists():
        if _load(output_path) != record: raise ValueError("immutable semantic inventory differs")
    else: write_json(output_path, record)
    return record


def _actual_run(link: dict, root: Path, *, require_success: bool = True) -> tuple[dict, dict, dict, list[dict]]:
    directory = Path(link["run_dir"]).resolve()
    if not directory.is_relative_to(root.resolve()): raise ValueError("semantic run is outside the arm directory")
    sources = [_link(directory / name) for name in ("registered_spec.json", "result.json")]
    if link.get("sources") != sources: raise ValueError("semantic original run source hashes differ")
    spec, result = (_load(directory / name) for name in ("registered_spec.json", "result.json"))
    checked = verify(spec, result, directory)
    if result.get("execution_kind") != "actual_cpu_execution" or (require_success and result.get("status") != "success") or checked.get("valid") is not True:
        raise ValueError("semantic predicate requires independently verified actual CPU evidence")
    return spec, result, checked, sources


def run_reference(run_dir: Path) -> dict:
    directory = Path(run_dir).resolve()
    return {"run_dir": str(directory), "sources": [_link(directory / name) for name in ("registered_spec.json", "result.json")]}


def _same_conditions(a: dict, b: dict) -> bool:
    keys = ("task_id", "task_version", "seed", "model", "implementation_sha256", "evaluator_sha256",
            "source_sha256", "split_manifest_sha256", "data_sha256", "public_bundle_sha256", "resource_envelope",
            "command", "execution_entrypoint", "metric", "tool_contract_sha256")
    return all(a.get(key) == b.get(key) for key in keys)


def evaluate_predicate(claim: dict, arm_output: Path) -> dict:
    """Recompute fixed, narrow predicates; never infer a framework effect from a fit."""
    predicate = claim.get("predicate_id"); args = claim.get("arguments", {})
    if not isinstance(args, dict): raise ValueError("semantic predicate arguments must be an object")
    if predicate in {"final_framework_effect", "causal_memory_effect", "model_replacement_effect", "independent_reproduction"}:
        raise ValueError("this source version has no registered independent final/causal/replay proof adapter; claim remains pending or unsupported")
    if predicate in {"verified_execution", "train_only_disjoint_split", "registered_configuration", "registered_criterion"}:
        spec, result, checked, sources = _actual_run(args["run"], arm_output)
        if predicate == "registered_configuration":
            if args.get("config") != spec["config"]: raise ValueError("semantic claimed configuration differs from registration")
            facts = {"config": spec["config"]}
        elif predicate == "registered_criterion":
            criterion = spec.get("criterion", {}); metric = spec.get("metric")
            if criterion.get("threshold") is None or criterion.get("baseline_value") is not None:
                raise ValueError("semantic criterion adapter supports fixed absolute thresholds only")
            actual = checked["metrics"][metric]; direction = criterion["direction"]
            threshold = criterion["threshold"]
            if direction not in {"min", "max"} or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
                raise ValueError("semantic criterion must have a finite fixed threshold and explicit direction")
            success = actual <= criterion["threshold"] if direction == "min" else actual >= criterion["threshold"]
            if args.get("success") is not success: raise ValueError("semantic registered success claim contradicts actual metric")
            facts = {"criterion": criterion, "metric": metric, "value": actual, "success": success}
        else:
            facts = {"execution_kind": result["execution_kind"], "valid": True,
                "task_id": spec["task_id"], "seed": spec["seed"], "split_manifest_sha256": spec["split_manifest_sha256"],
                "scope": "one registered train/validation experiment; train-only fit and disjoint splits checked by fixed verifier"}
        return {"predicate_id": predicate, "facts": facts, "evidence": sources}
    if predicate == "observed_validation_comparison":
        a, _, av, ae = _actual_run(args["left"], arm_output); b, _, bv, be = _actual_run(args["right"], arm_output)
        if not _same_conditions(a, b): raise ValueError("semantic comparison conditions do not match")
        metric = "validation_mse"; left, right = av["metrics"][metric], bv["metrics"][metric]
        operation = args.get("relation"); valid = {"lt": left < right, "le": left <= right, "gt": left > right, "eq": left == right}.get(operation)
        if valid is not True: raise ValueError("semantic observed comparison contradicts actual metrics")
        return {"predicate_id": predicate, "facts": {"metric": metric, "left": left, "right": right, "relation": operation,
            "scope": "observed validation metrics on one matched split; not unseen-task generalization or independent stochastic replication"}, "evidence": ae+be}
    if predicate in {"observed_minimum", "observed_inventory_counts"}:
        provided = args.get("runs", []); folders = [Path(item["run_dir"]).resolve() for item in provided]
        discovered = set()
        for path in arm_output.rglob("registered_spec.json"):
            result_path = path.parent / "result.json"
            if not result_path.exists(): raise ValueError("semantic whole-history inventory has an unresolved execution")
            if _load(result_path).get("execution_kind") == "actual_cpu_execution": discovered.add(path.parent.resolve())
        if not folders or len(set(folders)) != len(folders) or set(folders) != discovered:
            raise ValueError("semantic whole-history inventory omits, duplicates or invents an actual execution")
        records = [_actual_run(item, arm_output, require_success=False) for item in provided]
        reference = records[0][0]
        if any(not _same_conditions(reference, row[0]) for row in records):
            raise ValueError("semantic whole-history runs have different task/seed/model/split/resources")
        sources = [item for row in records for item in row[3]]
        configs = {value_hash(row[0]["config"]) for row in records}
        counts = {"actual_executions": len(records), "distinct_configurations": len(configs),
                  "repeated_configurations": len(records)-len(configs)}
        if predicate == "observed_inventory_counts":
            if args.get("counts") != counts: raise ValueError("semantic execution/configuration counts contradict the full history")
            return {"predicate_id": predicate, "facts": {**counts,
                "scope": "actual deterministic execution receipts on one task/seed; repeated configurations are not independent stochastic replications"}, "evidence": sources}
        selected, _, selected_verification, selected_sources = _actual_run(args["selected"], arm_output)
        if Path(args["selected"]["run_dir"]).resolve() not in discovered or not _same_conditions(reference, selected):
            raise ValueError("semantic selected minimum is absent from the complete matched history")
        successful = [row for row in records if row[1]["status"] == "success"]
        minimum = min(row[2]["metrics"]["validation_mse"] for row in successful)
        if selected_verification["metrics"]["validation_mse"] != minimum:
            raise ValueError("semantic selected candidate is not the minimum observed validation error")
        return {"predicate_id": predicate, "facts": {**counts, "successful_executions": len(successful),
            "validation_mse": minimum, "selected_config": selected["config"],
            "scope": "minimum among all observed verified candidates on this fixed validation split; not global optimum or test/population superiority"}, "evidence": sources+selected_sources}
    if predicate == "resource_accounting":
        from .evaluation import recompute_resource_audit
        path = _checked_link(args["resource_audit"], arm_output); record = recompute_resource_audit(path)
        key = args.get("measure"); actual = record["measures"].get(key)
        if actual is None or args.get("value") != actual: raise ValueError("semantic resource claim is unknown or differs from raw receipt accounting")
        return {"predicate_id": predicate, "facts": {"measure": key, "value": actual,
            "scope": "research-provider inference / trusted CPU receipts only; engineering and independent reviewer cost excluded"}, "evidence": [_link(path)]}
    if predicate == "attributed_literature":
        path = _checked_link(args["source"]); excerpt = args.get("excerpt"); url = args.get("url")
        source_text = path.read_text(encoding="utf-8")
        if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in source_text or not isinstance(url, str) or not url.startswith("https://") or url not in source_text:
            raise ValueError("semantic literature attribution needs pinned original excerpt and citation")
        return {"predicate_id": predicate, "facts": {"url": url, "excerpt": excerpt,
            "scope": "attributed source statement; not a locally measured finding"}, "evidence": [_link(path)]}
    if predicate == "conditional_inference":
        _, _, _, sources = _actual_run(args["run"], arm_output)
        if claim.get("kind") != "inference" or not _TENTATIVE.search(claim["text"]) or _BROAD_EFFECT.search(claim["text"]):
            raise ValueError("conditional inference must be visibly tentative and cannot establish general framework or causal effect")
        _check_nonresult_scope(claim["text"], "proposal")
        if not isinstance(args.get("conditions"), str) or not args["conditions"].strip():
            raise ValueError("conditional inference requires explicit applicability conditions")
        return {"predicate_id": predicate, "facts": {"conditions": args["conditions"], "scope": "reviewer interpretation, not measured expected improvement"}, "evidence": sources}
    raise ValueError("unknown semantic predicate; cannot accept self-defined evaluation code")


def _review_claim(claim: dict, unit: dict, arm_output: Path) -> dict:
    if not isinstance(claim, dict): raise ValueError("semantic claim must be an object")
    text = unit["decoded_text"]; start, end = claim.get("start"), claim.get("end")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
        raise ValueError("semantic claim span is invalid")
    raw = text[start:end]
    if claim.get("text") != raw or claim.get("claim_id") != value_hash({"unit_id": unit["unit_id"], "start": start, "end": end, "text": raw}):
        raise ValueError("semantic claim is not bound to the exact original source span")
    if not isinstance(claim.get("rationale"), str) or not claim["rationale"].strip(): raise ValueError("semantic reviewer rationale missing")
    outcome, kind = claim.get("outcome"), claim.get("kind")
    if outcome not in {"supported", "classified_nonresult", "unsupported", "pending"}: raise ValueError("semantic outcome is invalid")
    if kind not in {"measured_result", "execution_provenance", "literature", "inference", "proposal", "method", "limitation", "general_result"}: raise ValueError("semantic claim kind is invalid")
    if outcome == "supported":
        predicate = claim.get("predicate_id")
        if kind in {"method", "proposal", "limitation"}: raise ValueError("non-result interpretation cannot be relabelled supported measurement")
        if _BROAD_EFFECT.search(raw) and kind not in {"literature"} and predicate not in {"final_framework_effect", "causal_memory_effect", "model_replacement_effect"}:
            raise ValueError("general or causal result exceeds a local experiment predicate")
        if kind == "literature" and predicate != "attributed_literature": raise ValueError("literature must be attributed, not accepted as local measurement")
        if kind == "inference" and predicate != "conditional_inference": raise ValueError("inference requires tentative conditional interpretation")
        if _REPRODUCTION.search(raw) and predicate != "independent_reproduction":
            raise ValueError("actual reproduction requires independent replay proof, not one successful execution")
        if _MINIMUM.search(raw) and predicate != "observed_minimum":
            raise ValueError("observed best claim requires the complete actual candidate history, not a pair comparison")
        if _INDEPENDENT_REPEATS.search(raw) and predicate != "independent_reproduction":
            raise ValueError("deterministic repeated configurations do not establish independent stochastic replications")
        if _COMPARISON.search(raw) and predicate not in {"observed_validation_comparison", "observed_minimum", "conditional_inference", "attributed_literature"}:
            raise ValueError("comparative result requires an actual matched comparison, not an execution-success predicate")
        proof = evaluate_predicate(claim, arm_output)
        if claim.get("predicate_result") != proof: raise ValueError("semantic predicate result differs from independent recomputation")
    elif outcome == "classified_nonresult":
        if kind not in {"method", "proposal", "limitation"}: raise ValueError("result assertion cannot be excluded as non-result")
        if kind == "proposal" and not _TENTATIVE.search(raw): raise ValueError("proposal must be visibly prospective/tentative")
        _check_nonresult_scope(raw, kind)
        if "predicate_result" in claim: raise ValueError("non-result claim contains a measurement proof")
    return claim


def validate_semantic_review(review_path: Path, *, arm_output: Path, require_complete: bool = True) -> dict:
    review_path = Path(review_path).resolve(); arm_output = Path(arm_output).resolve()
    if not review_path.is_relative_to(arm_output): raise ValueError("semantic review escaped the arm directory")
    review = _load(review_path)
    if review.get("schema_version") != SEMANTIC_SCHEMA_VERSION or review.get("reviewer_role") != "independent_verifier":
        raise ValueError("independent semantic reviewer/schema required")
    predicate = _checked_link(review["predicate_source"])
    if sha256_file(predicate) != sha256_file(Path(__file__)):
        raise ValueError("semantic predicate source is not the executing frozen evaluator")
    inventory_path = _checked_link(review["inventory"], arm_output); inventory = _load(inventory_path)
    report_path = _checked_link(inventory["report"], arm_output)
    expected = semantic_units(report_path.read_text(encoding="utf-8"), sha256_file(report_path))
    if inventory.get("schema_version") != SEMANTIC_SCHEMA_VERSION or inventory.get("predicate_source") != review["predicate_source"] or inventory.get("units") != expected or not expected:
        raise ValueError("semantic inventory does not reconstruct the entire original report")
    rows = review.get("units", []); ids = [row.get("unit_id") for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != {unit["unit_id"] for unit in expected}:
        raise ValueError("semantic paragraph/string coverage omitted, duplicated or invented a unit")
    unit_map = {unit["unit_id"]: unit for unit in expected}; pending = unsupported = 0; claim_ids = set()
    for row in rows:
        unit = unit_map[row["unit_id"]]
        if row.get("exhaustive_result_claim_mapping") is not True or not isinstance(row.get("rationale"), str) or not row["rationale"].strip():
            raise ValueError("reviewer must attest exhaustive meaning/condition mapping per unit")
        outcome = row.get("outcome"); claims = row.get("claims", [])
        if outcome not in {"reviewed", "pending"}: raise ValueError("semantic unit status invalid")
        if outcome == "pending": pending += 1
        if not isinstance(claims, list): raise ValueError("semantic claims must be a list")
        if not claims and outcome != "pending" and unit["unit_kind"] != "json_structure" and (
                _RESULT_CUE.search(unit["decoded_text"]) or _ASSERTED_RESULT.search(unit["decoded_text"]) or _COMPARISON.search(unit["decoded_text"])):
            raise ValueError("result-bearing text cannot pass solely as an unexamined non-result unit")
        for claim in claims:
            _review_claim(claim, unit, arm_output)
            if claim["claim_id"] in claim_ids: raise ValueError("duplicate semantic claim span")
            claim_ids.add(claim["claim_id"])
            pending += claim["outcome"] == "pending"; unsupported += claim["outcome"] == "unsupported"
        if claims:
            spans = sorted((claim["start"], claim["end"]) for claim in claims)
            if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
                raise ValueError("semantic assertion spans overlap")
            covered = {index for start, end in spans for index in range(start, end)}
            if any(not char.isspace() and index not in covered for index, char in enumerate(unit["decoded_text"])):
                raise ValueError("semantic claim spans omit non-whitespace original content")
    for key, actual in (("pending_items", pending), ("unsupported_semantic_result_claims", unsupported)):
        if type(review.get(key)) is not int or review[key] != actual: raise ValueError("semantic counters differ from reconstructed judgments")
    complete = pending == 0
    if review.get("status") != ("complete" if complete else "pending"): raise ValueError("semantic complete flag contradicts actual review coverage")
    if require_complete and not complete: raise ValueError("independent semantic review is pending")
    return {"semantic_report_audit_complete": complete, "unsupported_semantic_result_claims": unsupported,
        "pending_items": pending, "units": len(expected), "claims": len(claim_ids), "report": inventory["report"],
        "review": _link(review_path), "inventory": review["inventory"], "predicate_source": review["predicate_source"],
        "review_wall_seconds": None, "review_usage": None, "limits": SEMANTIC_POLICY["limits"]}


def semantic_claim(unit: dict, *, kind: str, outcome: str, rationale: str, predicate_id: str | None = None,
                   arguments: dict | None = None, start: int = 0, end: int | None = None) -> dict:
    end = len(unit["decoded_text"]) if end is None else end; text = unit["decoded_text"][start:end]
    claim = {"claim_id": value_hash({"unit_id": unit["unit_id"], "start": start, "end": end, "text": text}),
        "start": start, "end": end, "text": text, "kind": kind, "outcome": outcome, "rationale": rationale}
    if predicate_id is not None: claim.update(predicate_id=predicate_id, arguments=arguments or {})
    return claim


def adjudicate_semantic_review(inventory_path: Path, judgments: list[dict], output_path: Path, *,
                              arm_output: Path, reviewer_role: str) -> dict:
    if reviewer_role != "independent_verifier": raise ValueError("only an independent owner reviewer can adjudicate semantic claims")
    inventory_path, output_path = Path(inventory_path).resolve(), Path(output_path).resolve()
    rows = json.loads(json.dumps(judgments)); pending = unsupported = 0
    for row in rows:
        pending += row.get("outcome") == "pending"
        for claim in row.get("claims", []):
            pending += claim.get("outcome") == "pending"; unsupported += claim.get("outcome") == "unsupported"
            if claim.get("outcome") == "supported": claim["predicate_result"] = evaluate_predicate(claim, Path(arm_output))
    record = {"schema_version": SEMANTIC_SCHEMA_VERSION, "reviewer_role": reviewer_role,
        "inventory": _link(inventory_path), "predicate_source": _link(Path(__file__)), "units": rows,
        "pending_items": pending, "unsupported_semantic_result_claims": unsupported,
        "status": "pending" if pending else "complete", "review_wall_seconds": None, "review_usage": None,
        "responsibility": SEMANTIC_POLICY["limits"]}
    # Validate a temporary new file before atomically preserving the final review.
    if output_path.exists():
        if _load(output_path) != record: raise ValueError("immutable semantic review differs; write a versioned sidecar")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        probe = output_path.with_name(output_path.name + ".candidate")
        if probe.exists(): raise FileExistsError("prior semantic candidate requires reconciliation")
        write_json(probe, record)
        try: validate_semantic_review(probe, arm_output=arm_output, require_complete=False)
        except Exception:
            # Failed candidate remains an explicit review attempt; never silently overwrite it.
            raise
        else: probe.replace(output_path)
    validate_semantic_review(output_path, arm_output=arm_output, require_complete=False)
    return record


def audit_semantic_reports(report_paths: list[Path], review_paths: list[Path], *, arm_output: Path) -> dict:
    expected = {str(Path(path).resolve()) for path in report_paths}; reports = set(); audits = []
    for path in review_paths:
        audit = validate_semantic_review(path, arm_output=arm_output, require_complete=False)
        source = audit["report"]["path"]
        if source in reports or source not in expected: raise ValueError("semantic review duplicates or covers an unexpected report")
        reports.add(source); audits.append(audit)
    complete = len(expected) == 2 and expected == reports and all(a["semantic_report_audit_complete"] for a in audits)
    return {"semantic_report_audit_complete": complete,
        "unsupported_semantic_result_claims": sum(a["unsupported_semantic_result_claims"] for a in audits),
        "pending_items": sum(a["pending_items"] for a in audits) + len(expected-reports),
        "audits": audits, "scope": SEMANTIC_POLICY["scope"], "limits": SEMANTIC_POLICY["limits"]}


def semantic_review_sidecars(arm_output: Path) -> tuple[list[Path], list[dict]]:
    """Latest explicit owner review version per report; retain immutable history.

    A later pending review takes precedence over an earlier complete one. This
    never selects a favorable outcome or changes a completed owner score.
    """
    arm_output = Path(arm_output).resolve(); latest = []; history = []
    for stem in ("semantic-report-review", "semantic-companion-review"):
        candidates = []
        for path in arm_output.glob(stem + "*.json"):
            match = re.fullmatch(re.escape(stem) + r"(?:-v(\d{4,}))?\.json", path.name)
            if not match: continue
            ordinal = int(match.group(1)) if match.group(1) else 0
            if match.group(1) and ordinal <= 0: raise ValueError("semantic review version must be positive")
            candidates.append((ordinal, path))
        if len({ordinal for ordinal, _ in candidates}) != len(candidates): raise ValueError("duplicate semantic review version")
        for _, path in sorted(candidates):
            validate_semantic_review(path, arm_output=arm_output, require_complete=False)
            history.append(_link(path))
        if candidates: latest.append(max(candidates)[1])
    return latest, history


def next_semantic_review_path(arm_output: Path, stem: str) -> Path:
    if stem not in {"semantic-report-review", "semantic-companion-review"}: raise ValueError("unknown semantic report kind")
    arm_output = Path(arm_output).resolve(); ordinal = 0
    while True:
        path = arm_output / (stem + (f"-v{ordinal:04d}" if ordinal else "") + ".json")
        if not path.exists() and not path.with_name(path.name + ".candidate").exists(): return path
        ordinal += 1
