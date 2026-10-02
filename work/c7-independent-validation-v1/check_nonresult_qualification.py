"""No new model/CPU: whole-report qualification with fixture originals."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CANDIDATE=ROOT/"work/c7"
sys.path.insert(0,str(CANDIDATE))
from transport_fixture import sha,write
from evidence_research.report_semantics import (prepare_semantic_review,semantic_claim,
    adjudicate_semantic_review,validate_semantic_review)

def main():
    number=len(list(HERE.glob("nonresult-qualification-attempt-*.json")))+1
    arm=ROOT/"work/t7/bctx0001/C";folder=arm/f"nonresult-qualification-{number:02d}";folder.mkdir()
    registration=arm/"callback-registration.json"
    if json.loads(registration.read_text(encoding="utf-8")).get("fixture_only") is not True:raise AssertionError("original fixture registration needed")
    report=folder/"report.txt";report.write_text("We propose a future comparison.",encoding="utf-8")
    inv=folder/"inventory.json";unit=prepare_semantic_review(report,inv)["units"][0]
    rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","exhaustive_result_claim_mapping":True,"rationale":"Full non-result original content mapped.","claims":[semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Genuine prospective text with explicit fixture arm originals.")]}]
    out={"schema_version":"independent-whole-report-fixture-qualification-attack-1","candidate_source_sha256":sha(CANDIDATE/"evidence_research/report_semantics.py"),
        "fixture_registration":{"path":str(registration),"sha256":sha(registration)},"new_cpu_executions":0,"actual_provider_calls":0,"research_trials":0,"owner_private_reads":False,"monetary_cost":None}
    review=adjudicate_semantic_review(inv,rows,folder/"review.json",arm_output=arm,reviewer_role="independent_verifier")
    coverage=validate_semantic_review(folder/"review.json",arm_output=arm,require_complete=False)
    out["nonresult_report_actual_complete"]=coverage["semantic_report_audit_complete"]
    out["nonresult_qualification"]=coverage["semantic_evidence_qualification"]
    out["nonresult_review"]={"path":str(folder/"review.json"),"sha256":sha(folder/"review.json")}
    try:validate_semantic_review(folder/"review.json",arm_output=arm);out["nonresult_production_rejected"]=False
    except ValueError as error:out.update(nonresult_production_rejected=True,nonresult_error=str(error))
    empty=folder/"empty.txt";empty.write_text("",encoding="utf-8")
    try:
        empty_inv=folder/"empty-inventory.json";prepare_semantic_review(empty,empty_inv)
        adjudicate_semantic_review(empty_inv,[],folder/"empty-review.json",arm_output=arm,reviewer_role="independent_verifier")
        validate_semantic_review(folder/"empty-review.json",arm_output=arm);out["empty_report_rejected"]=False
    except ValueError as error:out.update(empty_report_rejected=True,empty_error=str(error))
    write(HERE/f"nonresult-qualification-attempt-{number:04d}.json",out)
    print(json.dumps({key:out.get(key) for key in ("nonresult_report_actual_complete","nonresult_qualification","nonresult_production_rejected","empty_report_rejected")},ensure_ascii=True))

if __name__=="__main__":main()
