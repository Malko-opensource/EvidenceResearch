"""Accountable numeric review of one pinned, completed DEVELOPMENT report.

This is report-specific semantic adjudication, not an arbitrary prose evaluator.
It writes independent sidecars and never edits original reports or experiments.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from evidence_research.evaluation import adjudicate_numeric_review, prepare_numeric_review
from evidence_research.tasks import sha256_file, value_hash
from evidence_research.verifier import verify
from evaluation.review_partial_upstream import link, write_once

EXPECTED = "79a7ba96be63f8960e05d0fb0b29986562044c0955e978ccfcf14c92b6d5baaa"
ORIGINAL = PROJECT / "runs/development/B-upstream-dev-quadratic-seed7-literature"
CONTINUED = PROJECT / "runs/development/B-upstream-dev-quadratic-seed7-resumed"
REVIEW = CONTINUED / "independent_review"


def main() -> None:
    report = REVIEW / "final_development_report.tex"
    if sha256_file(report) != EXPECTED:
        raise ValueError("semantic adjudication is specific to the pinned report")
    state_path = CONTINUED / "upstream/baseline_result.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["status"] != "success":
        raise ValueError("the completed-report review requires a completed pipeline")
    runs = []
    for folder in sorted((ORIGINAL / "experiments").glob("execution-*")):
        folder = folder.resolve()
        spec = json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        verification = verify(spec, result, folder)
        if not verification["valid"] or result["status"] != "success":
            raise ValueError("actual CPU evidence failed independent verification")
        runs.append({"folder": str(folder), "spec": spec, "metrics": verification["metrics"],
                     "verification": verification, "result": link(folder / "result.json")})
    if len(runs) != 2 or len({value_hash(r["spec"]["config"]) for r in runs}) != 1:
        raise ValueError("reviewed duplicate execution counts changed")
    selected = Path(runs[-1]["folder"])
    metrics = runs[-1]["metrics"]
    if runs[0]["metrics"] != metrics:
        raise ValueError("repeated configurations produced different metrics")
    evidence_path = REVIEW / "verified_experiment_evidence.json"
    write_once(evidence_path, {"actual_cpu_executions": 2, "distinct_configurations": 1,
                              "runs": runs, "selected_supplied_record": str(selected),
                              "continuation_result": link(state_path), "final_evaluation": False})
    gap = metrics["validation_mse"] - metrics["train_mse"]
    stage_one = {(d, a) for d in range(1, 5) for a in (0.0, 0.1, 1.0)}
    stage_one |= {(d, a) for d in range(5, 9) for a in (0.1, 1.0)}
    extra = (0.01, 0.03, 0.3, 3.0, 10.0, 100.0)
    if len(stage_one) != 20 or any((d, a) in stage_one for d in range(1, 9) for a in extra):
        raise ValueError("proposed grid arithmetic changed")
    derived_path = REVIEW / "derived_arithmetic.json"
    write_once(derived_path, {"validation_minus_training": {"inputs": metrics, "value": gap,
               "displayed": 0.004009, "rounding_matches": abs(gap - 0.004009) <= 0.0000005},
               "proposed_grid": {"first_stage": sorted(stage_one), "extra_alphas": extra,
               "first_stage_count": 20, "extra_count": 6, "planned_count": 26,
               "distinct_measured_count": 1, "planned_unmeasured_count": 25,
               "kind": "proposal_arithmetic", "proposed_configs_executed": False},
               "evidence": [link(evidence_path)], "calculation_source": link(Path(__file__))})
    inventory_path = REVIEW / "numeric_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else prepare_numeric_review(report, inventory_path)
    if len(inventory["items"]) != 215:
        raise ValueError("pinned decimal inventory changed")
    corpus = PROJECT / "references/task_literature.json"
    literature = json.loads(corpus.read_text(encoding="utf-8"))
    if value_hash(literature["records"]) != literature["records_sha256"]:
        raise ValueError("supplied primary-source synopsis changed")
    method_note = REVIEW / "mathematical_context.json"
    write_once(method_note, {"kind": "independent_method_derivation", "literature_url": "https://arxiv.org/html/1910.02373v2",
               "sections": "2 ridge objective/closed form; 3 validation context",
               "note": "The normalized ridge objective uses lambda times squared coefficients. Multiplying by n yields the unnormalized penalty alpha=n*lambda. An unpenalized intercept requires a separate intercept convention. In full-rank unpenalized fitting or positive-penalty penalized directions, SVD coefficient factors are s/(s^2+alpha) and fitted-response factors s^2/(s^2+alpha). Polynomial powers, squared-error exponents, indices, and inverse notation are method symbols, not measured outcomes. The report does not supply coefficients or claim a measured SVD effect.",
               "trusted_implementation": link(selected / "source/evidence_research/tasks.py"),
               "trusted_verifier": link(selected / "source/evidence_research/verifier.py"),
               "limits": "Literature mathematics motivates proposals; it does not validate local superiority or inferred bias-variance explanations."})
    proposal_lines = {29,107,109,111,113,117,166,189,200}
    formula_lines = {23,24,27,38,40,42,50,51,53,60,62,66,68,74,75,80,82,123,124,129,135,136,137,157,158,160,162}
    judgments = []
    for item in inventory["items"]:
        number, line = item["number"], item["line"]
        j = {"claim_id": item["claim_id"]}
        if number in (str(metrics["train_mse"]), str(metrics["validation_mse"])):
            metric = "train_mse" if number == str(metrics["train_mse"]) else "validation_mse"
            j.update(kind="measured", run_dir=str(selected), metric=metric,
                     rationale="Independent prediction and metric recomputation succeeds for both preserved actual CPU executions; the displayed value matches.")
        elif number == "0.004009":
            continue  # Independently reproduced derived metric in sidecar below.
        elif line in proposal_lines and not (line == 166 and item["start"] > item["context"].find("Until further")) and not (line == 189 and number in ("2", "0.0")):
            j.update(kind="proposal", rationale="This occurrence belongs to the explicitly unexecuted finite grid or its independently calculated configuration count, not actual executed experiments.")
        elif line == 14 and number in ("1", "8"):
            j.update(kind="proposal", rationale="Permitted degrees for future comparisons; the report does not claim these alternatives were executed.")
        elif line in formula_lines:
            j.update(kind="method", source_path=str(method_note), source_sha256=sha256_file(method_note),
                     rationale="Index, exponent, inverse, MSE normalization, ridge or SVD mathematical notation; independently checked method context, not measured performance.")
        elif number in ("80", "64"):
            j.update(kind="method", source_path=str(selected / "split_manifest.json"), source_sha256=sha256_file(selected / "split_manifest.json"),
                     rationale="Verified actual train/validation rows and manifest contain the stated sizes; these define sample partition or normalization.")
        elif line == 151 and number == "1":
            j.update(kind="identifier", source_path=str(selected / "registered_spec.json"), source_sha256=sha256_file(selected / "registered_spec.json"),
                     rationale="Suffix of polynomial-ridge-1 task version, consistent with the actual registration; not an experiment count.")
        elif number in ("2", "0.0"):
            j.update(kind="method", source_path=str(selected / "registered_spec.json"), source_sha256=sha256_file(selected / "registered_spec.json"),
                     rationale="Executed degree=2/alpha=0.0 settings, or definition of that unpenalized quadratic model. Configuration is fixed in the registration.")
        elif number in ("1", "8", "8.", "0", "100"):
            src = selected / "source/evidence_research/tasks.py"
            j.update(kind="method", source_path=str(src), source_sha256=sha256_file(src),
                     rationale="Allowed degree/alpha limits or standard constant; the frozen validator enforces degrees 1..8 and alpha 0..100. No performance outcome is claimed.")
        else:
            raise ValueError(f"numeric context requires an accountable judgment: line{line}:{number}")
        judgments.append(j)
    write_once(REVIEW / "primitive_numeric_judgments.json", judgments)
    primitive_path = REVIEW / "primitive_numeric_adjudication.json"
    primitive = json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else adjudicate_numeric_review(inventory_path, judgments, primitive_path, reviewer_role="independent_verifier")
    claims = [{**c, "kind": "derived_measured", "outcome": "supported", "reason": "Independent subtraction of verified validation and training MSE agrees after rounding; no statistical significance is inferred.", "evidence": [link(derived_path)]} if c["number"] == "0.004009" else c for c in primitive["claims"]]
    pattern = r"\b(?:one|two|three|zero|single|six)\b|\b\d{4}\.\d{5}v\d+\b|\[(?:11pt|margin=1in|T1)\]|(?<![\w.])[+-]?(?:\d+\.\d+|\.\d+)(?:[eE][+-]?\d+)?(?=\.(?:\s|$))"
    supplement = []
    for line_no, line in enumerate(report.read_text(encoding="utf-8").splitlines(),1):
        for match in re.finditer(pattern,line,re.I):
            item={"line":line_no,"start":match.start(),"end":match.end(),"number":match.group(),"context":line}
            item["claim_id"]=value_hash({"report_sha256":EXPECTED,**item})
            v=match.group().lower()
            kind,outcome,reason,evidence="method","classified_nonmeasurement","",[]
            if line_no in (1,2,3):
                kind,reason,evidence="identifier","Typesetting option or font identifier; not a study outcome.",[link(report)]
            elif re.fullmatch(r"\d{4}\.\d{5}v\d+",v):
                if v not in {r["id"] for r in literature["records"]}: raise ValueError("literature identifier mismatch")
                kind,reason,evidence="literature","Bibliographic ID matches the supplied frozen primary-source synopsis; no local empirical result is attributed to it.",[link(corpus)]
            elif line_no==31 and v=="one":
                kind,outcome,reason,evidence="execution_count","pending","The pipeline has two actual host executions of one unique configuration. The writer received one selected record, but 'available experimental evidence consists of one actual host execution' does not explicitly scope its count to that supplied record. Pending scope clarification; do not treat as a verified pipeline-wide count.",[link(evidence_path),link(ORIGINAL / "experiments/tool_events.jsonl")]
            elif line_no==185:
                kind,outcome,reason,evidence="derived_measured","supported","This terminal decimal was missed by the initial regex; independent verified-MSE subtraction matches its six-decimal display.",[link(derived_path)]
            elif v=="six" or (v=="one" and line_no==200):
                kind,reason,evidence="proposal","Spelled-out size of an unexecuted refinement grid or its planned winning-degree choice; arithmetic is verified separately without asserting execution.",[link(derived_path)]
            elif v=="one" and line_no in (14,117,189):
                kind,outcome,reason,evidence="derived_measured","supported","Exactly one distinct degree/alpha configuration was measured, though it was executed twice.",[link(evidence_path)]
            elif line_no==169 and v=="one":
                reason,evidence="Explicitly refers to the single supplied host record; not a pipeline-wide execution count. Selected result is one record from two duplicate executions.",[link(state_path),link(evidence_path)]
            elif line_no==91 and v=="two":
                reason,evidence="Two agent-framework papers are named separately from the ridge reference in the frozen corpus.",[link(corpus)]
            elif line_no==155 and v=="two":
                reason,evidence="The executed result contains train and validation MSE, two primitive task metrics.",[link(selected / "result.json")]
            elif v=="zero":
                reason,evidence="Zero regularization is the executed setting or standard ridge definition; the report does not claim zero is globally optimal.",[link(selected / "registered_spec.json"),link(method_note)]
            elif v=="single" or (v=="one" and line_no==151):
                reason,evidence="One fixed partition or one unique measured baseline; uncertainty across independent splits is explicitly unestablished.",[link(evidence_path),link(selected / "split_manifest.json")]
            elif v=="one" and line_no==17:
                reason,evidence="Conceptual statement that feature expansion may alter regularization behavior, not a numerical experimental outcome.",[link(method_note)]
            else: raise ValueError(f"unreviewed supplemental context: {line_no}:{v}")
            supplement.append({**item,"kind":kind,"outcome":outcome,"reason":reason,"evidence":evidence})
    if len(supplement)!=33: raise ValueError("supplemental coverage changed")
    write_once(REVIEW / "supplemental_numeric_inventory.json",{"report_sha256":EXPECTED,"items":supplement})
    claims+=supplement
    pending=sum(c["outcome"]=="pending" for c in claims)
    final={"status":"pending" if pending else "complete","reviewer_role":"independent_verifier",
           "report_path":str(report),"report_sha256":EXPECTED,"inventory_path":str(inventory_path),"inventory_sha256":sha256_file(inventory_path),
           "claims":claims,"unsupported_claims":sum(c["outcome"]=="unsupported" for c in claims),"pending_claims":pending,
           "regex_occurrences":215,"supplemental_occurrences":33,"report_pipeline_complete":True,
           "whole_report_numeric_audit_complete":not pending,"final_evaluation":False,"original_report_modified":False,
           "semantic_review_source":link(Path(__file__)),"primitive_adjudication":link(primitive_path),"derived_calculation":link(derived_path),
           "limits":"248 lexical quantity occurrences are not 248 independent scientific claims. One execution-count scope remains pending. Non-numeric prose quality and discovery quality are not evaluated."}
    write_once(REVIEW / "comprehensive_numeric_adjudication.json",final)
    print(json.dumps({"path":str(REVIEW / "comprehensive_numeric_adjudication.json"),"pending":pending,"unsupported":final["unsupported_claims"],"occurrences":248,"final_evaluation":False}))

if __name__=="__main__": main()
