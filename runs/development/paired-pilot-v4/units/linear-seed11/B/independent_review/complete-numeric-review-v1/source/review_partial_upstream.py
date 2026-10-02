"""Reproduce an independent review of one immutable DEVELOPMENT report snapshot.

This script contains accountable, report-specific semantic classifications.
It is not an automatic judge for arbitrary scientific prose or a final evaluator.
No upstream report, frozen task source, or completed experimental evidence is edited.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from evidence_research.evaluation import adjudicate_numeric_review, prepare_numeric_review
from evidence_research.tasks import sha256_file, value_hash
from evidence_research.verifier import verify

EXPECTED_REPORT_SHA256 = "52d82cafc37e7e288de37df7464be0cbff04a783ba75e84909d417f5ddcf8b52"
BASELINE = PROJECT / "runs/development/B-upstream-dev-quadratic-seed7-literature"
REVIEW = BASELINE / "independent_review"


def link(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def write_once(path: Path, value: dict | list) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"existing independent review changed: {path}")
        return
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    report = REVIEW / "partial_report.tex"
    if sha256_file(report) != EXPECTED_REPORT_SHA256:
        raise ValueError("these semantic judgments apply only to the pinned partial report")
    final_state = json.loads((BASELINE / "upstream/baseline_result.json").read_text(encoding="utf-8"))
    if final_state["status"] != "failure":
        raise ValueError("this review is for a failed/incomplete development pipeline")
    runs = []
    for folder in sorted((BASELINE / "experiments").glob("execution-*")):
        spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        verification = verify(spec, result, folder)
        if not verification["valid"] or result["status"] != "success":
            raise ValueError("report metric evidence fails independent verification")
        runs.append({"folder": folder, "spec": spec, "result": result, "verification": verification})
    if len(runs) != 2 or len({value_hash(r["spec"]["config"]) for r in runs}) != 1:
        raise ValueError("pipeline execution/configuration counts differ from reviewed evidence")
    chosen = runs[0]
    metrics = chosen["verification"]["metrics"]
    if any(r["verification"]["metrics"] != metrics for r in runs):
        raise ValueError("duplicated configuration has different measurements")
    data = {name: json.loads((chosen["folder"] / f"{name}.json").read_text(encoding="utf-8")) for name in ("train", "validation")}
    if len(data["train"]) != 80 or len(data["validation"]) != 64:
        raise ValueError("reported split sizes do not match execution evidence")
    inventory_path = REVIEW / "numeric_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else prepare_numeric_review(report, inventory_path)
    if len(inventory["items"]) != 47:
        raise ValueError("numeric inventory differs from manually reviewed snapshot")
    corpus = PROJECT / "references/task_literature.json"
    literature = json.loads(corpus.read_text(encoding="utf-8"))
    if value_hash(literature["records"]) != literature["records_sha256"]:
        raise ValueError("fixed literature records changed")
    judgments, derived = [], []
    for item in inventory["items"]:
        number, line = item["number"], item["line"]
        judgment = {"claim_id": item["claim_id"]}
        if number in ("0.0086303159202098", "0.012638906669511679"):
            metric = "train_mse" if number.startswith("0.008") else "validation_mse"
            judgment.update({"kind": "measured", "run_dir": str(chosen["folder"]), "metric": metric,
                             "rationale": "The value equals independently recomputed predictions for this fixed split; both actual CPU executions agree."})
        elif number == "0.004009":
            # The frozen generic API supports primitive metrics only. Do not
            # misclassify a real arithmetic measurement as proposal or inference.
            derived.append(item)
            continue
        elif line == 29 or (line == 14 and number in ("1", "8")):
            judgment.update({"kind": "proposal", "rationale": "The sentence explicitly specifies a subsequent unexecuted degree/alpha comparison; this is not an achieved result."})
        elif number in ("80", "64"):
            judgment.update({"kind": "method", "source_path": str(chosen["folder"] / "split_manifest.json"),
                             "source_sha256": sha256_file(chosen["folder"] / "split_manifest.json"),
                             "rationale": "Actual split files and their independently verified manifest contain 80 training and 64 validation observations; this number describes data or MSE normalization."})
        elif line in (23, 24, 27):
            source = chosen["folder"] / "source/evidence_research/verifier.py"
            judgment.update({"kind": "method", "source_path": str(source), "source_sha256": sha256_file(source),
                             "rationale": "This is an index, normalization constant, or squared-error exponent in the MSE definition, consistent with the fixed independent calculation; it is not a measured performance claim."})
        elif line in (14, 31, 39) and number in ("2", "0.0"):
            source = chosen["folder"] / "registered_spec.json"
            judgment.update({"kind": "method", "source_path": str(source), "source_sha256": sha256_file(source),
                             "rationale": "The actual preregistered configuration is degree=2, alpha=0.0. These are executed hyperparameters, not predictive measurements."})
        elif line in (17, 41) and number in ("1", "8", "8.", "0", "100"):
            source = chosen["folder"] / "source/evidence_research/tasks.py"
            judgment.update({"kind": "method", "source_path": str(source), "source_sha256": sha256_file(source),
                             "rationale": "The trusted configuration validator allows integer degrees 1..8 and finite alpha 0..100. These are permitted settings, not experimental outcomes."})
        else:
            raise ValueError(f"unreviewed numeric context: line={line}, value={number}")
        judgments.append(judgment)
    write_once(REVIEW / "primitive_numeric_judgments.json", judgments)
    base_path = REVIEW / "primitive_numeric_adjudication.json"
    if base_path.exists():
        base_review = json.loads(base_path.read_text(encoding="utf-8"))
    else:
        base_review = adjudicate_numeric_review(inventory_path, judgments, base_path, reviewer_role="independent_verifier")
    gap = metrics["validation_mse"] - metrics["train_mse"]
    calculation = {"kind": "derived_measured", "operation": "validation_mse - train_mse",
                   "inputs": metrics, "value": gap, "displayed_value": 0.004009,
                   "display_precision_decimal_places": 6, "rounding_tolerance": 0.0000005,
                   "rounding_matches": abs(gap - 0.004009) <= 0.0000005,
                   "primitive_evidence": [link(chosen["folder"] / "result.json"), link(REVIEW / "verified_experiment_evidence.json")],
                   "calculation_source": link(Path(__file__))}
    if not calculation["rounding_matches"]:
        raise ValueError("reported validation/training gap fails arithmetic reproduction")
    calculation_path = REVIEW / "derived_gap_calculation.json"
    write_once(calculation_path, calculation)
    final_claims = []
    for claim in base_review["claims"]:
        if claim["number"] == "0.004009":
            final_claims.append({**claim, "kind": "derived_measured", "outcome": "supported", "evidence": [link(calculation_path)],
                                 "reason": "Independent subtraction of verified MSEs gives 0.004008590749301879, which rounds to 0.004009. It is descriptive; no significance or overfitting is claimed."})
        else:
            final_claims.append(claim)
    supplemental = []
    pattern = r"\b(?:one|two|three|zero|single)\b|\b\d{4}\.\d{5}v\d+\b|\[(?:11pt|margin=1in|T1)\]"
    for line_no, line in enumerate(report.read_text(encoding="utf-8").splitlines(), 1):
        for match in re.finditer(pattern, line, flags=re.I):
            item = {"line": line_no, "start": match.start(), "end": match.end(), "number": match.group(), "context": line}
            item["claim_id"] = value_hash({"report_sha256": EXPECTED_REPORT_SHA256, **item})
            value = match.group().lower()
            kind, outcome, rationale, evidence = "method", "classified_nonmeasurement", "", []
            if line_no in (1, 2, 3):
                kind, rationale, evidence = "identifier", "Typesetting declaration or font encoding; not a study number or scientific outcome.", [link(report)]
            elif re.fullmatch(r"\d{4}\.\d{5}v\d+", value):
                if value not in {r["id"] for r in literature["records"]}:
                    raise ValueError("reported arXiv identifier is absent from the fixed corpus")
                kind, rationale, evidence = "literature", "The identifier matches the frozen supplied primary-source synopsis. Literature context is not local experimental verification.", [link(corpus)]
            elif line_no == 31 and value == "one":
                kind, outcome = "execution_count", "pending"
                rationale = "The entire host pipeline logged two actual executions of one configuration. 'One actual host execution' could mean the single supplied candidate record, but it is inaccurate if interpreted as pipeline-wide execution count. The incomplete author report does not make that scope explicit; clarification is needed. Do not count this as a verified one-execution claim."
                evidence = [link(REVIEW / "verified_experiment_evidence.json"), link(BASELINE / "experiments/tool_events.jsonl")]
            elif line_no == 14 and value == "one":
                kind, outcome, rationale = "derived_measured", "supported", "There is one distinct executed configuration, degree=2/alpha=0, although it was actually executed twice. The claim counts configurations, not repeated executions."
                evidence = [link(REVIEW / "verified_experiment_evidence.json")]
            elif value == "zero" and line_no in (14, 41):
                rationale, evidence = "The executed alpha is 0.0; the report denies that its optimality is established, which avoids an unsupported comparative claim.", [link(chosen["folder"] / "registered_spec.json")]
            elif line_no == 17 and value == "one":
                rationale, evidence = "A conceptual statement about how changing feature expansion can change regularization behavior; it is not an empirical sample/execution count.", [link(corpus)]
            elif line_no == 33 and value == "single":
                rationale, evidence = "The experiment uses one fixed training/validation split and data seed, so robustness across independent splits is not established.", [link(chosen["folder"] / "split_manifest.json")]
            elif line_no == 45 and value == "two":
                agent_sources = [r["id"] for r in literature["records"] if r["id"].startswith(("2501.", "2503."))]
                if len(agent_sources) != 2:
                    raise ValueError("agent-oriented reference count differs")
                rationale, evidence = "The fixed corpus contains exactly the two referenced agent-workflow papers, Agent Laboratory and AgentRxiv; the ridge reference is separate.", [link(corpus)]
            elif line_no == 45 and value == "single":
                rationale, evidence = "One distinct measured configuration supplies the regression baseline; no alternate configured candidate was measured in this pipeline.", [link(REVIEW / "verified_experiment_evidence.json")]
            else:
                raise ValueError(f"unreviewed spelled-out/identifier numeric context: {line_no}: {value}")
            supplemental.append({**item, "kind": kind, "outcome": outcome, "reason": rationale, "evidence": evidence})
    if len(supplemental) != 16:
        raise ValueError("supplemental numeric coverage differs from reviewed snapshot")
    write_once(REVIEW / "supplemental_numeric_inventory.json", {"report_sha256": EXPECTED_REPORT_SHA256, "items": supplemental})
    all_claims = final_claims + supplemental
    complete = {"status": "pending" if any(c["outcome"] == "pending" for c in all_claims) else "complete",
                "scope": "development partial report numeric review only; not a final study or completed upstream report",
                "reviewer_role": "independent_verifier", "report_path": str(report), "report_sha256": EXPECTED_REPORT_SHA256,
                "inventory_path": str(inventory_path), "inventory_sha256": sha256_file(inventory_path),
                "primitive_adjudication": link(base_path), "derived_calculation": link(calculation_path),
                "claims": all_claims, "unsupported_claims": sum(c["outcome"] == "unsupported" for c in all_claims),
                "pending_claims": sum(c["outcome"] == "pending" for c in all_claims),
                "regex_occurrences": len(final_claims), "supplemental_occurrences": len(supplemental),
                "whole_report_numeric_audit_complete": False, "report_pipeline_complete": False,
                "final_evaluation": False, "original_report_modified": False,
                "semantic_review_source": link(Path(__file__)),
                "limits": "All identified numerals, listed spelled-out quantities and identifiers were reviewed; arbitrary semantic truth and missing unfinished sections are not verified. One execution-count scope remains unresolved."}
    write_once(REVIEW / "comprehensive_numeric_adjudication.json", complete)
    print(json.dumps({"report": str(REVIEW / "comprehensive_numeric_adjudication.json"), "regex_occurrences": len(final_claims),
                      "supplemental_occurrences": len(supplemental), "unsupported": complete["unsupported_claims"],
                      "pending": complete["pending_claims"], "status": complete["status"]}))


if __name__ == "__main__":
    main()
