"""No new CPU/provider calls: inspect explicit existing fixture qualification."""
from pathlib import Path
import json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CANDIDATE=ROOT/"work/c7"
sys.path.insert(0,str(CANDIDATE))
from transport_fixture import sha
from evidence_research.report_semantics import (run_reference,evaluate_predicate,prepare_semantic_review,
    semantic_claim,adjudicate_semantic_review,validate_semantic_review)

def main():
    arm=ROOT/"work/t7/bctx0001/C";run=arm/"research/runs/cpu-0"
    spec=json.loads((run/"registered_spec.json").read_text(encoding="utf-8"))
    if spec.get("fixture_only") is not True:raise AssertionError("negative needs an explicitly marked fixture")
    metric=json.loads((run/"result.json").read_text(encoding="utf-8"))["metrics"]
    display=f"{metric['validation_mse']-metric['train_mse']:.8f}"
    text=f"For the named verified run, validation MSE minus training MSE is {display} MSE."
    args={"operation":"validation_minus_training","run":run_reference(run),"left_metric":"validation_mse","right_metric":"train_mse","value":float(display),"decimal_places":8,"unit":"mse"}
    number=len(list(HERE.glob("qualification-attempt-*.json")))+1
    folder=arm/f"qualification-{number:02d}";folder.mkdir()
    report=folder/"report.txt";report.write_text(text,encoding="utf-8")
    inventory=folder/"inventory.json";unit=prepare_semantic_review(report,inventory)["units"][0]
    claim=semantic_claim(unit,kind="measured_result",outcome="supported",rationale="Explicit fixture-to-actual qualification attack, not a study report.",predicate_id="derived_metric_arithmetic",arguments=args)
    rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","exhaustive_result_claim_mapping":True,"rationale":"All source characters mapped.","claims":[claim]}]
    out={"schema_version":"independent-explicit-fixture-qualification-attack-1","case":"fixture_cpu_arithmetic_production_qualification",
         "actual_provider_calls":0,"new_cpu_executions":0,"research_trials":0,"owner_private_reads":False,
         "candidate_report_semantics_sha256":sha(CANDIDATE/"evidence_research/report_semantics.py"),"explicit_cpu_spec":str(run/"registered_spec.json"),"spec_sha256":sha(run/"registered_spec.json"),"spec_fixture_only":True}
    try:
        review=adjudicate_semantic_review(inventory,rows,folder/"review.json",arm_output=arm,reviewer_role="independent_verifier")
        coverage=validate_semantic_review(folder/"review.json",arm_output=arm,require_complete=False)
        out["coverage_and_qualification"]=coverage
        # Rehash the entire review JSON, including claimed eligibility/aggregate
        # counters. Original linked evidence is unchanged and must win.
        forged=json.loads((folder/"review.json").read_text(encoding="utf-8"))
        forged["semantic_evidence_qualification"]="actual"
        for row in forged["units"]:
            for item in row.get("claims",[]):
                if "predicate_result" in item:
                    item["predicate_result"]["facts"].update(evidence_class="actual",adoption_eligible=True)
                    item["predicate_result"]["facts"].pop("contains_synthetic_original_evidence",None)
        forged_path=folder/"rehashed-caller-actual-label-review.json";forged_path.write_text(json.dumps(forged,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        try:validate_semantic_review(forged_path,arm_output=arm);out["rehashed_caller_actual_labels_rejected"]=False
        except ValueError as error:out.update(rehashed_caller_actual_labels_rejected=True,caller_label_error=str(error))
        validation=validate_semantic_review(folder/"review.json",arm_output=arm)
        out.update(production_rejected=False,semantic_evidence_qualification=validation.get("semantic_evidence_qualification"),actual_complete=validation.get("semantic_report_audit_complete"),validation=validation)
    except ValueError as exc:
        out.update(production_rejected=True,error=str(exc))
    path=HERE/f"qualification-attempt-{number:04d}.json";path.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:out.get(key) for key in ("production_rejected","semantic_evidence_qualification","actual_complete","error")},ensure_ascii=True))

if __name__=="__main__":main()
