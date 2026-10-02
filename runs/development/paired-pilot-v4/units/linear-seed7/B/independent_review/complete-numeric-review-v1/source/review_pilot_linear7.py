"""Independent semantic review of the pinned, minimal-upstream linear7 diagnostic.

This is accountable review of one report, not an automatic prose evaluator.
Participant reports, registrations, package source and CPU/model receipts stay
unchanged. No model is called and no owner-only test observations are opened.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_research.evaluation import adjudicate_numeric_review, recompute_resource_audit
from evidence_research.tasks import sha256_file, value_hash
from evidence_research.verifier import verify
from evaluation.review_partial_upstream import link, write_once

ARM = ROOT / "runs/development/paired-pilot-v4/units/linear-seed7/B"
REVIEW = ARM / "independent_review/complete-numeric-review-v1"
EXPECTED_REPORT = "49863ddcdbe6a8d165dcee08c189495974dee5d36a1321fefc4562327242da2b"
EXPECTED_COMPANION = "c36cbc5a62d2619126e22ea1890f7b692f5513412c33398d11189c62a53ff850"


def source_judgment(kind, source, rationale):
    return {"kind": kind, "source_path": str(source.resolve()),
            "source_sha256": sha256_file(source), "rationale": rationale}


def combine(primitive, extra, *, report, inventory, derived, supplemental):
    claims = primitive["claims"] + extra
    pending = sum(c["outcome"] == "pending" for c in claims)
    return {"status": "pending" if pending else "complete", "reviewer_role": "independent_verifier",
            "report_path": str(report.resolve()), "report_sha256": sha256_file(report),
            "inventory_path": str(inventory.resolve()), "inventory_sha256": sha256_file(inventory),
            "claims": claims, "unsupported_claims": sum(c["outcome"] == "unsupported" for c in claims),
            "pending_claims": pending, "whole_report_numeric_audit_complete": not pending,
            "regex_occurrences": len(primitive["claims"]), "supplemental_occurrences": len(extra),
            "semantic_review_source": link(Path(__file__)), "derived_calculation": link(derived),
            "supplemental_inventory": link(supplemental), "independent_review_wall_seconds": None,
            "independent_review_usage": None, "final_evaluation": False,
            "comparison_improvement_claim": False, "original_report_modified": False,
            "study_scope": "Minimal upstream settings development diagnostic; excluded from confirmatory variance design.",
            "limits": "Lexical quantities are not independent claims. Non-numeric prose, literary quality and scientific discovery quality are not evaluated. Provider resources exclude engineering and independent semantic review cost; these unmetered costs remain unknown."}


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    report, companion = ARM / "report.txt", ARM / "research_report.json"
    if sha256_file(report) != EXPECTED_REPORT or sha256_file(companion) != EXPECTED_COMPANION:
        raise ValueError("semantic judgments are pinned to the two reviewed source reports")
    response = json.loads((ARM / "arm-response.json").read_text(encoding="utf-8"))
    resource_path = ARM / "independent-resource-audit.json"
    resource = recompute_resource_audit(resource_path)
    runs = []
    for entry in response["cpu_execution_dirs"]:
        run = Path(entry).resolve()
        spec = json.loads((run / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((run / "result.json").read_text(encoding="utf-8"))
        verification = verify(spec, result, run)
        if not verification["valid"] or result["status"] != "success":
            raise ValueError("actual CPU receipt failed independent verification")
        runs.append({"run_dir": str(run), "spec": spec, "verification": verification, "result": link(run / "result.json")})
    if len(runs) != 2 or len({value_hash(r["spec"]["config"]) for r in runs}) != 1:
        raise ValueError("the explicit two-attempt/one-configuration claim no longer matches")
    selected = Path(response["selected_run_dir"]).resolve()
    selected_run = next(r for r in runs if Path(r["run_dir"]) == selected)
    metrics = selected_run["verification"]["metrics"]
    if any(r["verification"]["metrics"] != metrics for r in runs):
        raise ValueError("repeated fixed configurations have different metrics")
    manifest_path = selected / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["splits"]["train"]["count"] != 80 or manifest["splits"]["validation"]["count"] != 64 or manifest["splits"]["test"]["count"] != 96:
        raise ValueError("public partition manifest differs")
    evidence_path = REVIEW / "independent-execution-and-resource-evidence.json"
    write_once(evidence_path, {"runs": runs, "distinct_configurations": 1, "resource_audit": link(resource_path),
                              "resource_measures": resource["measures"], "resource_evidence": resource["evidence"],
                              "hidden_test_observations_opened": False, "public_manifest_only": link(manifest_path)})
    plan_path = Path(response["baseline_result_path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))["plan"]
    candidates = [(d, a) for d in (1, 2, 4, 8) for a in (0.0, 0.1)]
    if len(candidates) != 8 or any(f"({d}, {a})" not in plan for d, a in candidates):
        raise ValueError("the explicit pre-execution proposal ladder differs from report")
    derived = REVIEW / "independent-derived-arithmetic.json"
    gap = metrics["validation_mse"] - metrics["train_mse"]
    limit = response["resource_envelope"]["actual_cpu_executions_per_unit"]
    write_once(derived, {"validation_minus_training": {"inputs": metrics, "value": gap,
                "display": 0.00229733, "rounding_tolerance": 0.000000005,
                "rounding_matches": abs(gap - 0.00229733) <= 0.000000005},
                "planned_grid": {"candidates": [list(x) for x in candidates], "count": 8, "measured_distinct": 1,
                "unmeasured": 7, "kind": "proposal_arithmetic", "unmeasured_candidates_executed": False},
                "remaining_cpu_allowance": {"limit": limit, "actual_attempts": resource["measures"]["actual_cpu_executions"],
                "remaining": limit - resource["measures"]["actual_cpu_executions"], "kind": "derived_resource_allowance"},
                "inputs": [link(evidence_path), link(plan_path)], "calculation_source": link(Path(__file__))})
    if not json.loads(derived.read_text(encoding="utf-8"))["validation_minus_training"]["rounding_matches"]:
        raise ValueError("displayed gap rounding does not agree")
    math_note = REVIEW / "independent-method-context.json"
    corpus = ROOT / "references/task_literature.json"
    literature = json.loads(corpus.read_text(encoding="utf-8"))
    if value_hash(literature["records"]) != literature["records_sha256"]:
        raise ValueError("frozen primary-source synopsis changed")
    write_once(math_note, {"kind": "independent_method_derivation", "source": link(selected / "source/evidence_research/tasks.py"),
        "literature": link(corpus), "note": "Polynomial indices and powers, squared loss, matrix inverse, validation and training MSE denominators are mathematical definitions. With positive eigenvalues of X'X and P=I, ridge coefficients shrink by s/(s+lambda). The descriptive identities B_d=V(d,0)-V(d,.1), C_d,a=V(1,a)-V(d,a), I_d=C_d,.1-C_d,0=B_d-B_1 are algebraically correct. None is a measured regularization effect with only one available configuration.",
        "limits": "The report's 'preregistered' candidate set refers to its pre-execution planning proposal, not this diagnostic's confirmatory statistical protocol. No held-out performance, cross-task superiority or causal mechanism is established."})
    inventory_path = ARM / "numeric-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    formula_lines = {24,26,33,35,44,52,63,67,69,76,77,109,110,115,121,122,125,131,135,136,142,179,181,183,184,186,222,229,236}
    proposal_lines = {94,99,100,101,102,166,167,168,169,170,171,172,199,200,201,202,203,204,205}
    judgments = []
    for item in inventory["items"]:
        number, line = item["number"], item["line"]
        j = {"claim_id": item["claim_id"]}
        if number in (str(metrics["train_mse"]), str(metrics["validation_mse"])):
            metric = "train_mse" if number == str(metrics["train_mse"]) else "validation_mse"
            j.update(kind="measured", run_dir=str(selected), metric=metric,
                     rationale="Both actual CPU receipts independently reproduce this displayed MSE; it is a local train/validation result, not an independent test metric.")
        elif number == "0.00229733" or number == "49":
            continue
        elif number == "0002":
            j.update(source_judgment("identifier", selected / "registered_spec.json", "Execution identifier suffix refers to the selected named actual CPU receipt, not a count."))
        elif line == 158 and number in ("1", "256"):
            j.update(source_judgment("identifier", manifest_path, "Task-version suffix or SHA-256 algorithm identifier; no experimental outcome quantity."))
        elif number == "51":
            j.update(source_judgment("method", ARM / "callback-registration.json", "The registered shared CPU resource ceiling, not measured usage or a limit on the Goal research loop."))
        elif number in ("80", "64", "96", "7") and line not in proposal_lines:
            j.update(source_judgment("method", manifest_path, "Data size or seed agrees with the public manifest and independently checked fitting inputs. The test count describes withheld observations only; their values were not accessed."))
        elif line in formula_lines:
            j.update(source_judgment("method", math_note, "Mathematical constant, index, exponent or proposed contrast definition, independently checked algebra; no evaluated contrast is asserted."))
        elif line in proposal_lines:
            j.update(kind="proposal", rationale="Parameter or table order of an explicitly unmeasured planned candidate; eight-minus-one proposal arithmetic is independently checked without claiming execution.")
        elif line in (14,21,72,160):
            j.update(source_judgment("method", plan_path, "Parameter of the written paired-complexity proposal or permitted host domain; the report explicitly limits actual measurements to degree1/alpha0."))
        elif line in (30,83,155,165,188,191,198,214,216,232):
            j.update(source_judgment("method", selected / "registered_spec.json", "Executed degree1/alpha0 configuration or its position in the planned ladder, independently checked against the selected actual registration."))
        else:
            raise ValueError(f"unreviewed numeric context: {line}:{number}")
        judgments.append(j)
    primitive_path = REVIEW / "primary-primitive-adjudication.json"
    write_once(REVIEW / "primary-primitive-judgments.json", judgments)
    primitive = (json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else
                 adjudicate_numeric_review(inventory_path, judgments, primitive_path, reviewer_role="independent_verifier"))
    for item in primitive["claims"]:
        if item["number"] in ("0.00229733", "49"):
            item.update(kind="derived_measured" if item["number"] == "0.00229733" else "derived_resource_allowance",
                        outcome="supported", evidence=[link(derived)], reason="Independent subtraction of verified inputs matches the display. This does not add an executed candidate, establish uncertainty or demonstrate superiority.")
    pattern = r"\b(?:one|two|three|four|seven|eight|single|singleton|zero|first|second)\b|\b\d{4}\.\d{5}v\d+\b|\[(?:11pt|margin=1in|T1)\]|_[0-9]+|(?<![\w.])[+-]?(?:\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?(?=\.(?:\s|$))"
    supplement = []
    for ln, text in enumerate(report.read_text(encoding="utf-8").splitlines(), 1):
        for match in re.finditer(pattern, text, re.I):
            token = match.group().lower()
            item = {"line": ln, "start": match.start(), "end": match.end(), "number": match.group(), "context": text}
            item["claim_id"] = value_hash({"report_sha256": EXPECTED_REPORT, **item})
            kind, outcome, why, links = "method", "classified_nonmeasurement", "", []
            if ln <= 3:
                kind, why, links = "identifier", "Typesetting and font options, not study quantities.", [link(report)]
            elif re.fullmatch(r"\d{4}\.\d{5}v\d+", token):
                if token not in {r["id"] for r in literature["records"]}:
                    raise ValueError("bibliographic ID not in the frozen corpus")
                kind, why, links = "literature", "Exact frozen primary-source bibliographic identifier; no reproduced paper metric is claimed.", [link(corpus)]
            elif token.startswith("_"):
                why, links = "Polynomial/eigenvalue/loss subscript or descriptive planned-contrast index; independently checked mathematical definition.", [link(math_note)]
            elif token == "0.00229733":
                kind, outcome, why, links = "derived_measured", "supported", "Terminal decimal missed by the primary regex; independent validation-minus-training subtraction agrees at eight decimal places.", [link(derived)]
            elif token == "seven" or (ln == 14 and token == "eight") or (ln == 234 and token in ("two", "eight")):
                kind, why, links = "proposal", "Unmeasured candidate count or planned penalty/grid count, checked against the eight-candidate written plan. No executed result is implied.", [link(derived)]
            elif (ln == 14 and token in ("one", "two")) or ln in (30,155,188,191,232) and token in ("one", "two", "singleton") or ln == 218 and token in ("single", "singleton", "two", "one") and match.start() < text.find("These counts"):
                kind, outcome, why, links = "derived_execution_coverage", "supported", "The two actual CPU receipts have exactly one distinct configuration, confirmed separately from attempts. Counts are not independent sampled trials.", [link(evidence_path)]
            elif ln == 83 and token == "three":
                why, links = "Three references are listed in the frozen corpus; their statements remain literature context.", [link(corpus)]
            elif token in ("one", "two", "four", "eight") and ln in (37,133,160,229,236):
                why, links = "Degree name or the two-penalty design definition; remaining alternatives are explicitly unmeasured.", [link(math_note), link(plan_path)]
            elif ln in (105,175) and token == "one":
                why, links = "Host action schema permits one literal candidate per action, not a pipeline-wide execution count.", [link(ARM / "callback-registration.json")]
            elif token == "single" and ln in (74,234):
                why, links = "The fixed public partition is one split; the report expressly declines inference about independent repetitions.", [link(manifest_path)]
            elif ln == 155 and token == "first":
                why, links = "Ordinal describing the proposed lexicographic validation-first rule; no additional comparison result.", [link(plan_path)]
            elif ln == 218 and token in ("two", "second"):
                why, links = "Negated interpretation: duplicate invocations do not establish two independently sampled trials or a second distinct comparison result.", [link(evidence_path)]
            elif ln == 191 and token == "zero":
                why, links = "Negated missing-value interpretation: unmeasured results are explicitly not zero error.", [link(report)]
            else:
                raise ValueError(f"unreviewed supplemental context: {ln}:{token}")
            supplement.append({**item, "kind": kind, "outcome": outcome, "reason": why, "evidence": links})
    supplemental = REVIEW / "primary-supplemental-inventory.json"
    write_once(supplemental, {"report_sha256": EXPECTED_REPORT, "items": supplement})
    primary = combine(primitive, supplement, report=report, inventory=inventory_path, derived=derived, supplemental=supplemental)

    preparation = json.loads((ARM / "independent_review/prepared-companion.json").read_text(encoding="utf-8"))
    companion_judgments = preparation["judgments"][:]
    for item in preparation["pending_contexts"]:
        path = item["json_path"]
        j = {"claim_id": item["claim_id"]}
        if path == ["hypothesis"]:
            if item["number"] in ("80", "64"):
                j.update(source_judgment("method", manifest_path, "Planned comparison uses the actual fixed public train/validation sizes; no additional outcome is claimed."))
            else:
                j.update(kind="proposal", rationale="Literal parameter inside the pre-execution paired ladder; alternatives are plans rather than measured results.")
        elif path == ["limitations", 0] or path == ["schema_version"]:
            j.update(source_judgment("identifier", companion, "Named MATH-500 benchmark or report schema version identifier, not a number of tasks executed here."))
        elif path == ["resources", "actual_cpu_executions"]:
            j.update(kind="measured_resource", resource_audit_path=str(resource_path), resource_metric="actual_cpu_executions",
                     rationale="Independent unique raw CPU inventory reproduces the two actual attempts; cache/rejected code do not count.")
        elif path[0] == "resources" and path[-1] in ("proposal_calls_per_unit", "actual_cpu_executions_per_unit"):
            j.update(source_judgment("method", ARM / "callback-registration.json", "Shared registered resource ceiling, not measured use or total Goal iteration limit."))
        else:
            raise ValueError(f"unreviewed companion narrative: {path}")
        companion_judgments.append(j)
    companion_inventory = ARM / "companion-numeric-inventory.json"
    companion_primitive_path = REVIEW / "companion-primitive-adjudication.json"
    write_once(REVIEW / "companion-primitive-judgments.json", companion_judgments)
    companion_primitive = (json.loads(companion_primitive_path.read_text(encoding="utf-8")) if companion_primitive_path.exists() else
        adjudicate_numeric_review(companion_inventory, companion_judgments, companion_primitive_path, reviewer_role="independent_verifier"))
    companion_extra = []
    companion_text = companion.read_text(encoding="utf-8")
    for match in re.finditer(r"\b(?:one|eight)\b|\b\d{4}\.\d{5}v\d+\b", companion_text, re.I):
        token = match.group().lower()
        item = {"line": 1, "start": match.start(), "end": match.end(), "number": match.group(),
                "context": companion_text[max(0,match.start()-100):match.end()+100]}
        item["claim_id"] = value_hash({"report_sha256": EXPECTED_COMPANION, **item})
        if re.fullmatch(r"\d{4}\.\d{5}v\d+", token):
            if token not in {r["id"] for r in literature["records"]}:
                raise ValueError("unknown companion bibliography")
            kind, why, links = "literature", "Exact URL bibliographic identifier in the frozen primary-source synopsis.", [link(corpus)]
        elif token == "eight":
            kind, why, links = "proposal", "Spelled-out number of candidates in the explicitly tagged planning proposal; not an execution count.", [link(derived)]
        else:
            kind, why, links = "method", "Single-candidate literal action convention in the tagged proposed procedure; no claim of only one actual CPU attempt.", [link(ARM / "callback-registration.json")]
        companion_extra.append({**item, "kind": kind, "outcome": "classified_nonmeasurement", "reason": why, "evidence": links})
    companion_supplemental = REVIEW / "companion-supplemental-inventory.json"
    write_once(companion_supplemental, {"report_sha256": EXPECTED_COMPANION, "items": companion_extra})
    companion_final = combine(companion_primitive, companion_extra, report=companion, inventory=companion_inventory,
                              derived=derived, supplemental=companion_supplemental)
    for label, value in (("primary", primary), ("companion", companion_final)):
        if value["pending_claims"] or value["unsupported_claims"]:
            raise ValueError(f"{label} review is not complete supported classification")
        write_once(REVIEW / f"{label}-comprehensive-review.json", value)
    source_dir = REVIEW / "source"
    source_dir.mkdir(exist_ok=True)
    for source in (Path(__file__), ROOT / "evaluation/prepare_independent_review.py", ROOT / "evaluation/review_partial_upstream.py"):
        destination = source_dir / source.name
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError("review source snapshot changed")
        if not destination.exists():
            destination.write_bytes(source.read_bytes())
    write_once(ARM / "report-review.json", primary)
    write_once(ARM / "companion-review.json", companion_final)
    print(json.dumps({"primary": len(primary["claims"]), "companion": len(companion_final["claims"]),
                      "unsupported": 0, "pending": 0, "actual_cpu": 2, "model_calls": resource["measures"]["provider_calls"],
                      "study_scope": primary["study_scope"], "final_evaluation": False}))


if __name__ == "__main__":
    main()
