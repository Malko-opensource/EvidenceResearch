"""Pinned owner numeric review of the quadratic31 C development diagnostic.

No new model/CPU fit, participant edit or hidden-test-row inspection. Historical
validation comparisons are rechecked; future plans remain unmeasured proposals.
This uses the registered v4 numeric review scope, not the future semantic gate.
"""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from evidence_research.evaluation import adjudicate_numeric_review, recompute_resource_audit
from evidence_research.tasks import sha256_file,value_hash
from evidence_research.verifier import verify
from evaluation.review_partial_upstream import link,write_once

ARM=ROOT / "runs/development/paired-pilot-v4/units/quadratic-seed31/C"
REVIEW=ARM / "independent_review/complete-numeric-review-v1"
HASHES={"primary":"97c1b7d2a6cabbbb58c086bfe3d1c94b39d09b63bcd00efb85149d4de4036c57",
        "companion":"3a6564de8644eba24b463845ce984c27a0e86e21531ef4ee4ba437eb1ad17b5a"}


def main():
    REVIEW.mkdir(parents=True,exist_ok=True)
    response=json.loads((ARM / "arm-response.json").read_text(encoding="utf-8"))
    selected=Path(response["selected_run_dir"]).resolve()
    companion=json.loads((ARM / "research_report.json").read_text(encoding="utf-8"))
    resource_path=ARM / "independent-resource-audit.json";resources=recompute_resource_audit(resource_path)
    database=ARM / "research/research.sqlite3";original_hash=sha256_file(database)
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as connection:
        rows=[{"run_id":row[0],"spec":json.loads(row[1]),"outcome":row[2],"status":row[3]}
              for row in connection.execute("SELECT run_id,spec,outcome,status FROM runs ORDER BY created_at,run_id")]
    if sha256_file(database)!=original_hash:raise ValueError("read-only store query changed evidence")
    runs=[]
    for row in rows:
        directory=ARM / "research/evidence" / row["run_id"]
        result=json.loads((directory / "result.json").read_text(encoding="utf-8"));checked=verify(row["spec"],result,directory)
        if row["status"]!="completed" or not checked["valid"] or result["status"]!="success":raise ValueError("original candidate does not verify")
        runs.append({**row,"run_dir":str(directory),"verification":checked,"result_evidence":link(directory / "result.json")})
    if len(runs)!=19 or len({value_hash(row["spec"]["config"]) for row in runs})!=19:raise ValueError("nineteen distinct actual candidate receipts differ")
    if {str(Path(path).resolve()) for path in response["cpu_execution_dirs"]}!={row["run_dir"] for row in runs}:raise ValueError("callback/store CPU inventories differ")
    best=min(runs,key=lambda row:row["verification"]["metrics"]["validation_mse"])
    if Path(best["run_dir"])!=selected or best["spec"]["config"]!={"degree":4,"alpha":0.0}:raise ValueError("reported incumbent differs from observed minimum")
    failed=[row for row in runs if row["outcome"]=="failure"]
    if len(failed)!=16 or {row["spec"]["hypothesis"] for row in failed}!={q["question"] for q in companion["unresolved"]}:raise ValueError("reported failed hypotheses differ")
    indexed={(row["spec"]["config"]["degree"],row["spec"]["config"]["alpha"]):row for row in runs}
    comparisons=[]
    for worse,better in (((2,.1),(2,0.0)),((3,.01),(3,0.0)),((4,.01),(4,0.0)),((5,.01),(5,0.0)),
                         ((8,.01),(8,0.0)),((8,1.0),(8,0.0)),((2,0.0),(3,0.0)),((3,0.0),(4,0.0)),
                         ((7,0.0),(7,.01)),((6,0.0),(6,.01)),((6,.1),(6,.01))):
        high,low=indexed[worse],indexed[better];a,b=[row["verification"]["metrics"]["validation_mse"] for row in (high,low)]
        if a<=b:raise ValueError("reported historical validation comparison contradicts original predictions")
        comparisons.append({"higher_error_config":list(worse),"lower_error_config":list(better),"higher_validation_mse":a,
            "lower_validation_mse":b,"difference":a-b,"evidence":[high["result_evidence"],low["result_evidence"]]})
    refinements=[row for row in runs if row["spec"]["config"]["degree"] in (6,7)]
    if any(row["verification"]["metrics"]["validation_mse"]<=best["verification"]["metrics"]["validation_mse"] for row in refinements):raise ValueError("degree6/7 refinement claim differs")
    evidence=REVIEW / "independent-execution-history-and-resource-evidence.json"
    write_once(evidence,{"runs":runs,"actual_cpu_executions":19,"distinct_configurations":19,"failed_criterion_hypotheses":16,
        "selected_observed_minimum":best["run_id"],"historical_comparisons":comparisons,"resources":resources,
        "resource_audit":link(resource_path),"read_only_store":link(database),"source":link(Path(__file__)),
        "hidden_test_observations_opened":False,"limits":"Fixed validation comparisons only; no global optimum, stochastic significance, framework improvement, causal effect or final-test superiority."})
    corpus=ROOT / "references/task_literature.json";literature=json.loads(corpus.read_text(encoding="utf-8"))
    value="0.007519794976732067"
    for label,report_name,inventory_name,output_name in (("primary","report.md","numeric-inventory.json","report-review.json"),
            ("companion","research_report.json","companion-numeric-inventory.json","companion-review.json")):
        report=ARM / report_name
        if sha256_file(report)!=HASHES[label]:raise ValueError("review source is not the pinned report")
        prepared=json.loads((ARM / f"independent_review/prepared-{label}.json").read_text(encoding="utf-8"));judgments=prepared["judgments"][:]
        for item in prepared["pending_contexts"]:
            path,number=item["json_path"],item["number"];judgment={"claim_id":item["claim_id"]}
            if path==["schema_version"]:judgment.update(kind="identifier",source_path=str(report),source_sha256=HASHES[label],rationale="Fixed report schema suffix, not a measured outcome.")
            elif path==["stop_reason"] and number==value:judgment.update(kind="measured",run_dir=str(selected),metric="validation_mse",rationale="Selected metric independently recomputed from actual predictions and all observed candidates.")
            elif path==["stop_reason"] and number in {"4","0.0","2","5","8","6","7"}:
                judgment.update(kind="method",source_path=str(evidence),source_sha256=sha256_file(evidence),rationale="Literal selected setting/tested degree ranges. Full actual history independently confirms the stated conditional validation comparisons; no population/test/global superiority is asserted.")
            elif path and path[0]=="unresolved" and path[1] in (12,14,15):
                judgment.update(kind="method",source_path=str(evidence),source_sha256=sha256_file(evidence),rationale="Literal historical/next-candidate parameter; referenced validation comparisons independently verify. Prospective expected gains remain proposals and each unresolved run retains its failed criterion.")
            elif path==["hypothesis"] or path and path[0]=="unresolved":judgment.update(kind="proposal",rationale="Original proposed hypothesis, not a measured expected gain or a claim of criterion success.")
            else:raise ValueError(f"unreviewed numeric narrative: {path}:{number}")
            judgments.append(judgment)
        primitive_path=REVIEW / f"{label}-primitive-adjudication.json";write_once(REVIEW / f"{label}-primitive-judgments.json",judgments)
        primitive=json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else adjudicate_numeric_review(ARM / inventory_name,judgments,primitive_path,reviewer_role="independent_verifier")
        supplement=[]
        for line_number,text in enumerate(report.read_text(encoding="utf-8").splitlines(),1):
            for match in re.finditer(r"\b\d{4}\.\d{5}v\d+\b|(?<![\w.])\d+\.\d+(?=\.(?:\s|$))",text):
                token=match.group();item={"line":line_number,"start":match.start(),"end":match.end(),"number":token,"context":text};item["claim_id"]=value_hash({"report_sha256":HASHES[label],**item})
                if token==value:supplement.append({**item,"kind":"measured","outcome":"supported","reason":"Terminal validation decimal independently recomputed; all observed candidates checked.","evidence":[{**link(selected / "result.json"),"metric":"validation_mse","independent_value":best["verification"]["metrics"]["validation_mse"]}]})
                else:
                    if token not in {record["id"] for record in literature["records"]}:raise ValueError("unknown supplemental number")
                    supplement.append({**item,"kind":"literature","outcome":"classified_nonmeasurement","reason":"Bibliographic primary-source identifier; not locally measured empirical evidence.","evidence":[link(corpus)]})
        supplemental_path=REVIEW / f"{label}-supplemental-inventory.json";write_once(supplemental_path,{"report_sha256":HASHES[label],"items":supplement})
        claims=primitive["claims"]+supplement
        if any(claim["outcome"] in {"pending","unsupported"} for claim in claims):raise ValueError("numeric review is incomplete")
        final={**primitive,"claims":claims,"whole_report_numeric_audit_complete":True,"supplemental_inventory":link(supplemental_path),
            "semantic_review_source":link(Path(__file__)),"actual_history_evidence":link(evidence),"original_report_modified":False,
            "independent_review_wall_seconds":None,"independent_review_usage":None,"final_evaluation":False,"comparison_improvement_claim":False,
            "study_scope":"Minimal upstream B settings paired development diagnostic, excluded from confirmatory variance design.",
            "limits":"Numeric-scope v4 review. Broader natural-language result coverage is a separate future policy; forecasts remain planning judgments and validation truth does not establish final improvement."}
        write_once(REVIEW / f"{label}-comprehensive-review.json",final);write_once(ARM / output_name,final)
        print(json.dumps({"label":label,"occurrences":len(claims),"unsupported":0,"pending":0,"final_evaluation":False}))
    source=REVIEW / "source";source.mkdir(exist_ok=True)
    for original in (Path(__file__),ROOT / "evaluation/prepare_independent_review.py",ROOT / "evaluation/review_partial_upstream.py"):
        target=source / original.name
        if target.exists() and target.read_bytes()!=original.read_bytes():raise ValueError("source snapshot differs")
        if not target.exists():target.write_bytes(original.read_bytes())


if __name__=="__main__":main()
