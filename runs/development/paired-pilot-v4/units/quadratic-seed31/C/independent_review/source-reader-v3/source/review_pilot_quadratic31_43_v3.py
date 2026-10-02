"""Source-reader's report-specific independent reviews of four v4 diagnostics.

All eight pinned reports were read in context. Literal parameter classifications
apply only to these SHA-pinned documents, not arbitrary new prose. CPU evidence
and numeric resource receipts are independently recomputed; no runner, provider,
Store writer, hidden owner rows or participant source/report edits are used.
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
from evaluation.prepare_independent_review import prepare, json_leaves
from evaluation.review_partial_upstream import link, write_once

HASHES = {
    (31,"B"): ("084fdd352d4c4fd53aec249b2e7f98f7bd86d3993e17373e3259fe110ce88c3a", "05f0b11445e06f1c97c0ca115a9a0829ba8448bb421a13a24c765e9181b014ec"),
    (31,"C"): ("97c1b7d2a6cabbbb58c086bfe3d1c94b39d09b63bcd00efb85149d4de4036c57", "3a6564de8644eba24b463845ce984c27a0e86e21531ef4ee4ba437eb1ad17b5a"),
    (43,"B"): ("b3107778365d555eccf4b078b4f557617e8a14f11393ec6f94ecb8b090f7fe13", "3193cf96ede35b0357d1e6fc64798cbe1d64b5f2ba96d622ac82086a5ce87c36"),
    (43,"C"): ("0095045a8a75764004e0bc0799a39b55aa22fcf383d93648b86af575617973bb", "1dd6e8827356a6ccf20bb986fadaf6d47ed444d1509bef752305d53d1f3c4d9d"),
}
COUNTS = {(31,"B"): (2,1), (43,"B"): (2,1), (31,"C"): (19,19), (43,"C"): (25,25)}
WORD_VALUES = {"zero":0,"one":1,"single":1,"singleton":1,"two":2,"three":3,"four":4,"five":5,
    "six":6,"seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12,
    "first":1,"second":2,"third":3,"fourth":4,"fifth":5,"sixth":6,"seventh":7,"eighth":8}
SUPPLEMENT = re.compile(r"\b(?:" + "|".join(WORD_VALUES) + r")\b|\b\d{4}\.\d{5}v\d+\b|\[(?:11pt|margin=1in|T1)\]|_[0-9]+",re.I)


def classified(kind, source, why):
    return {"kind":kind,"source_path":str(source),"source_sha256":sha256_file(source),"rationale":why}


def verify_history(arm, response, seed, name, companion, review):
    resource_path = arm / "independent-resource-audit.json"
    resources = recompute_resource_audit(resource_path)
    runs=[]
    for value in response["cpu_execution_dirs"]:
        folder=Path(value).resolve()
        assert folder.is_relative_to(arm), "Actual CPU receipt escapes this owned completed arm"
        spec=json.loads((folder / "registered_spec.json").read_text(encoding="utf-8"))
        result=json.loads((folder / "result.json").read_text(encoding="utf-8"))
        verification=verify(spec,result,folder)
        if result["status"]!="success" or not verification["valid"]:
            raise ValueError("Completed CPU evidence does not independently verify")
        runs.append({"run_dir":str(folder),"spec":spec,"metrics":verification["metrics"],"verification":verification,
            "result_evidence":link(folder / "result.json"),"predictions_evidence":link(folder / "predictions.json")})
    distinct=len({value_hash(run["spec"]["config"]) for run in runs})
    if (len(runs),distinct)!=COUNTS[(seed,name)] or len(runs)!=resources["measures"]["actual_cpu_executions"]:
        raise ValueError("Reviewed actual invocation/distinct-configuration counts differ")
    selected=Path(response["selected_run_dir"]).resolve()
    chosen=next(run for run in runs if Path(run["run_dir"])==selected)
    if name=="B":
        if any(run["spec"]["config"]!={"degree":2,"alpha":0.0} or run["metrics"]!=chosen["metrics"] for run in runs):
            raise ValueError("The repeated quadratic reference differs")
    elif min(runs,key=lambda run:run["metrics"]["validation_mse"])["run_dir"]!=str(selected):
        raise ValueError("Selected C result is not the minimum among actual recorded evaluations")
    indexed={(run["spec"]["config"]["degree"],run["spec"]["config"]["alpha"]):run for run in runs}
    comparisons=[]
    if name=="C":
        # Report-specific historical assertions inside the original stored
        # hypotheses and stopping statement, separated from next-step forecasts.
        pairs=(((2,.1),(2,0.0)),((4,.01),(4,0.0)),((5,.01),(5,0.0)),((3,.01),(3,0.0)),
               ((8,.01),(8,0.0)),((8,1.0),(8,0.0)),((7,.03),(7,.01)),((6,.1),(6,0.0))) if seed==31 else (
               ((3,.35),(3,.15)),((3,0.0),(3,.15)),((7,0.0),(7,.1)),((7,.3),(7,.1)),
               ((8,0.0),(8,.1)),((8,.2),(8,.1)),((6,0.0),(6,.1)),((6,.2),(6,.1)),
               ((2,.34),(2,.3412)),((2,.342),(2,.3412)))
        for high,low in pairs:
            higher,lower=indexed[high],indexed[low]
            hv,lv=higher["metrics"]["validation_mse"],lower["metrics"]["validation_mse"]
            if hv<=lv:raise ValueError("A report-specific historical comparison does not match predictions")
            comparisons.append({"higher_error_config":list(high),"lower_error_config":list(low),"difference":hv-lv,
                "sources":[higher["result_evidence"],lower["result_evidence"]],"scope":"Observed validation arithmetic, not significance or generalization."})
        failed=[run for run in runs if "baseline_value" in run["spec"]["criterion"]
            and run["metrics"]["validation_mse"]>=run["spec"]["criterion"]["baseline_value"]]
        if {run["spec"]["hypothesis"] for run in failed}!={item["question"] for item in companion["unresolved"]}:
            raise ValueError("Unresolved hypotheses do not preserve the registered failed comparisons")
        degrees=range(5,9) if seed==31 else range(3,9)
        higher=[run for run in runs if run["spec"]["config"]["degree"] in degrees]
        if {run["spec"]["config"]["degree"] for run in higher}!=set(degrees) or any(run["metrics"]["validation_mse"]<=chosen["metrics"]["validation_mse"] for run in higher):
            raise ValueError("Stopping statement's tested degree-range observation differs")
    else:failed=[]
    report_inputs=[]
    if name=="B":
        # These raw report-generation requests expose a selected execution0002
        # object with metrics, plus cumulative2/1 counts and execution0000 only
        # as a hash-linked receipt. 'Other metrics not supplied' is scoped to the
        # reporting input, not a claim that the original host has no such result.
        for index in (11,13,15,17,19,21):
            request_path=arm / f"attempts/attempt-0000/model/upstream-{index:04d}/request.json"
            text=json.loads(request_path.read_text(encoding="utf-8"))["prompt"]
            marker="After running this code, the following results were observed: "
            if marker not in text:raise ValueError("Expected original report-writing input is absent")
            actual=json.JSONDecoder().raw_decode(text.split(marker,1)[1])[0]
            if actual["execution_id"]!="execution-0002" or actual["metrics"]!=chosen["metrics"]:
                raise ValueError("Reporting source is not the selected verified record")
            if actual["actual_cpu_attempts_to_date"]!=2 or actual["distinct_configs_to_date"]!=1:
                raise ValueError("Reporting cumulative-count scope differs")
            report_inputs.append({"request":link(request_path),"selected_result":actual["execution_id"],
                "selected_metrics":actual["metrics"],"actual_cpu_attempts_to_date":2,"distinct_configs_to_date":1,
                "scope":"One supplied metric object plus total invocation/condition counts; full host history remains separate."})
    evidence=review / "independent-execution-resource-and-report-input-evidence.json"
    write_once(evidence,{"runs":runs,"actual_cpu_executions":len(runs),"distinct_configurations":distinct,
        "selected":str(selected),"selected_metrics":chosen["metrics"],"resources":resources,"resource_source":link(resource_path),
        "historical_comparisons":comparisons,"criterion_failed_hypotheses":len(failed),"reporting_inputs":report_inputs,
        "hidden_owner_test_rows_opened":False,"actual_new_model_calls":0,"actual_runner_invocations":0,"source":link(Path(__file__))})
    derived=review / "independent-proposal-and-resource-arithmetic.json"
    grid=[(d,a) for d in (1,2,3,8) for a in (0.0,.1,1.0)] if seed==31 else [(2,0.0),(2,.1),(2,1.0),(3,.1),(4,1.0),(1,.1),(2,10.0),(8,10.0)]
    remaining=response["resource_envelope"]["actual_cpu_executions_per_unit"]-len(runs)
    write_once(derived,{"proposed_grid":grid,"proposed_count":len(grid),"unmeasured_grid_members":len(grid)-1 if name=="B" else None,
        "kind":"proposed_grid_and_actual_accounting_arithmetic","remaining_cpu_allowance":remaining,"registered_limit":51,
        "actual_cpu_attempts":len(runs),"inputs":[link(evidence),link(arm / "callback-registration.json")],"source":link(Path(__file__))})
    return chosen,evidence,derived,resources


def review_case(seed,name):
    arm=ROOT / f"runs/development/paired-pilot-v4/units/quadratic-seed{seed}/{name}"
    primary=arm / ("report.txt" if name=="B" else "report.md")
    companion_path=arm / "research_report.json"
    if (sha256_file(primary),sha256_file(companion_path))!=HASHES[(seed,name)]:raise ValueError("Report byte pins differ")
    review=arm / "independent_review/source-reader-v3";review.mkdir(parents=True,exist_ok=True)
    source_dir=review / "source";source_dir.mkdir(exist_ok=True)
    original_paths=[primary,companion_path,arm / "arm-response.json",arm / "numeric-inventory.json",arm / "companion-numeric-inventory.json"]
    original_before={str(path):sha256_file(path) for path in original_paths}
    response=json.loads((arm / "arm-response.json").read_text(encoding="utf-8"))
    companion=json.loads(companion_path.read_text(encoding="utf-8"))
    chosen,evidence,derived,resources=verify_history(arm,response,seed,name,companion,review)
    selected=Path(chosen["run_dir"])
    manifest=selected / "split_manifest.json"
    corpus=ROOT / "references/task_literature.json"
    literature=json.loads(corpus.read_text(encoding="utf-8"))
    if value_hash(literature["records"])!=literature["records_sha256"]:raise ValueError("Frozen literature differs")
    note=review / "independent-method-and-report-scope.json"
    write_once(note,{"literature":link(corpus),"public_split":link(manifest),"source":link(Path(__file__)),
        "note":"Reviewed conditional polynomial/ridge definitions: nested exact least-squares classes cannot raise minimum training SSE; under invertibility ridge solves (Z'Z+lambda P)^-1 Z'y; Gram eigenvalue shrinkage s/(s+lambda) assumes identity penalty. MSE denominators are fixed80/64. These formula/parameter definitions and held-out/selection caveats are not additional measured effects. B's preregistered language denotes its original preexecution research plan, not a completed12/8-candidate comparison or confirmatory protocol. B reports selected metric input separately from2actual/1distinct host counts. C's expected decision value, stable local minimum and untested degree1 reasoning remain planning inferences.",
        "actual_owner_test_rows_opened":False,"comparison_improvement_claim":False})
    for label,report,inventory,output in (("primary",primary,arm / "numeric-inventory.json",arm / "report-review.json"),
            ("companion",companion_path,arm / "companion-numeric-inventory.json",arm / "companion-review.json")):
        prep_path=review / f"prepared-{label}.json"
        preparation=json.loads(prep_path.read_text(encoding="utf-8")) if prep_path.exists() else prepare(arm,report,inventory,prep_path)
        judgments=preparation["judgments"][:]
        for item in preparation["pending_contexts"]:
            entry={"claim_id":item["claim_id"]};path=item["json_path"];number=item["number"].rstrip(".")
            if name=="B" and label=="primary":
                if number in {str(value) for value in chosen["metrics"].values()}:
                    metric=next(key for key,value in chosen["metrics"].items() if str(value)==number)
                    entry.update(kind="measured",run_dir=str(selected),metric=metric,rationale="Named host MSE independently recomputed from original predictions, with fixed split scope.")
                elif number=="49":continue
                elif number=="51":entry.update(classified("method",arm / "callback-registration.json","Registered CPU allowance, not actual usage or a Goal-loop limit."))
                elif number in ("80","64","96",str(seed)):entry.update(classified("method",manifest,"Known split count/denominator or seed; no withheld test observation read."))
                elif number in ("0000","0002"):entry.update(classified("identifier",evidence,"Exact original invocation identifier. Selected report input and complete2attempt/1condition history are checked separately."))
                elif number=="256":entry.update(classified("identifier",manifest,"SHA-256 algorithm identifier, not an experimental measurement."))
                elif number in {"-1","0","0.0","0.1","1","1.0","2","3","4","8","10.0","100","12"}:
                    entry.update(classified("method",note,"Literal degree/penalty, polynomial exponent/index, conditional inverse/formula, or preexecution candidate-enumeration value in this exact independently read document; no alternative measured outcome implied."))
                else:raise ValueError(f"Unreviewed pinned B numeric context {item['line']}:{number}")
            elif path==["hypothesis"] or path and path[0]=="unresolved":
                entry.update(kind="proposal",rationale="Explicit stored preexecution or failed hypothesis. Future gain is unmeasured; accompanying historical parameter comparisons are separately recomputed from actual receipts.")
            elif path in (["schema_version"],["limitations",0]):
                entry.update(classified("identifier",companion_path,"Schema/benchmark identifier, not a measured outcome."))
            elif path==["resources","actual_cpu_executions"]:
                entry.update(kind="measured_resource",resource_audit_path=str(arm / "independent-resource-audit.json"),resource_metric="actual_cpu_executions",rationale="Actual unique CPU receipt count independently recomputed; distinct configurations and statistical replications are separate.")
            elif path and path[0]=="resources" and path[-1] in ("actual_cpu_executions_per_unit","proposal_calls_per_unit"):
                entry.update(classified("method",arm / "callback-registration.json","Registered common maximum, not actual usage."))
            elif path==["stop_reason"]:
                if number==str(chosen["metrics"]["validation_mse"]):entry.update(kind="measured",run_dir=str(selected),metric="validation_mse",rationale="Selected actual MSE independently recomputed and ranked among every retained CPU receipt; not global/test optimality.")
                elif number in {"0","0.0","0.01","0.1","0.2","0.3","0.34","0.3412","1","2","3","4","5","6","7","8"}:
                    entry.update(classified("method" if number!="1" or seed==31 else "proposal",evidence,"Observed literal setting/tested degree range or untested degree1 planning choice; source-specific historical comparisons and failures independently checked. Future utility/local-minimum language is inference, never a measured probability."))
                else:raise ValueError(f"Unknown C stopping numeral {number}")
            else:raise ValueError(f"Unreviewed structured context {path}:{number}")
            judgments.append(entry)
        judgment_path=review / f"{label}-judgments.json";write_once(judgment_path,judgments)
        primitive_path=review / f"{label}-primitive-review.json"
        primitive=json.loads(primitive_path.read_text(encoding="utf-8")) if primitive_path.exists() else adjudicate_numeric_review(inventory,judgments,primitive_path,reviewer_role="independent_verifier")
        for item in primitive["claims"]:
            if name=="B" and label=="primary" and item["number"].rstrip(".")=="49":
                item.update(kind="derived_resource_allowance",outcome="supported",reason="Registered51 minus independently verified2 actual invocations equals49; no extra completed work asserted.",evidence=[link(derived)])
        supplements=[]
        for line,text in enumerate(report.read_text(encoding="utf-8").splitlines(),1):
            for match in SUPPLEMENT.finditer(text):
                token=match.group();normalized=token.lower();tail=text[match.end():]
                item={"line":line,"start":match.start(),"end":match.end(),"number":token,"context":text[max(0,match.start()-120):match.end()+180]}
                item["claim_id"]=value_hash({"report_sha256":sha256_file(report),**item})
                kind,outcome,reason,links="method","classified_nonmeasurement","Ordinal/literal parameter/formula subscript, fixed split/action convention or explicitly negated inference in reviewed context; no unrecorded execution claimed.",[link(note),link(manifest)]
                if re.fullmatch(r"\d{4}\.\d{5}v\d+",token):
                    if token not in {record["id"] for record in literature["records"]}:raise ValueError("Unknown complete bibliography ID")
                    kind,reason,links="literature","Exact frozen bibliographic ID, not reproduced paper measurement.",[link(corpus)]
                elif name=="B" and label=="primary" and normalized in ("one","single","singleton","two") and re.match(r"\s+(?:(?:actual|reported)\s+CPU\s+attempts|distinct\s+(?:evaluated\s+)?configuration|evaluated\s+configuration|measured\s+candidate|evaluated\s+candidate|measured\s+set)",tail,re.I):
                    expected=2 if re.match(r"\s+(?:actual|reported)\s+CPU\s+attempts",tail,re.I) else 1
                    if WORD_VALUES[normalized]!=expected:raise ValueError("Spelled invocation/condition quantity differs")
                    kind,outcome,reason,links="derived_execution_coverage","supported","Complete2actual/1distinct receipts and selected1record reporting scope verified; not independent statistical replication.",[link(evidence)]
                elif name=="B" and normalized in ("seven","eight","eleven","twelve") and ("planned" in text.lower() or "remaining" in text.lower() or "configurations" in tail[:50] or "candidates" in tail[:50] or "requests" in tail[:50]):
                    kind,reason,links="proposal","Original12/8-member plan and11/7 unevaluated members are proposal arithmetic; other candidates were not run.",[link(derived)]
                elif name=="C" and normalized in WORD_VALUES:
                    kind,reason,links="proposal","Spelled degree/ordinal in stored hypothesis or model stopping inference. Historical comparisons are checked separately; future improvement remains unmeasured.",[link(evidence),link(note)]
                supplements.append({**item,"kind":kind,"outcome":outcome,"reason":reason,"evidence":links})
        supplemental_path=review / f"{label}-supplemental-inventory.json"
        write_once(supplemental_path,{"report_sha256":sha256_file(report),"items":supplements})
        claims=primitive["claims"]+supplements
        pending=sum(item["outcome"]=="pending" for item in claims);unsupported=sum(item["outcome"]=="unsupported" for item in claims)
        final={**primitive,"claims":claims,"pending_claims":pending,"unsupported_claims":unsupported,
            "status":"pending" if pending else "complete","whole_report_numeric_audit_complete":not pending,
            "regex_occurrences":len(primitive["claims"]),"supplemental_occurrences":len(supplements),"supplemental_inventory":link(supplemental_path),
            "semantic_review_source":link(Path(__file__)),"actual_history_evidence":link(evidence),"derived_calculation":link(derived),
            "independent_review_wall_seconds":None,"independent_review_usage":None,"original_report_modified":False,"final_evaluation":False,
            "comparison_improvement_claim":False,"study_scope":"Frozen minimal-phase v4 development diagnostic; not the recommended-phase contrast or confirmatory variance sample.",
            "limits":"Occurrences are not independent claims. Method definitions, bibliographic IDs, planning forecasts and actual measures are separate. Local validation ranking and content gates do not establish scientific/literary quality, global optimality, hidden-test superiority, general discovery or framework improvement."}
        write_once(review / f"{label}-comprehensive-review.json",final)
        if output.exists():
            existing=json.loads(output.read_text(encoding="utf-8"))
            if existing["report_sha256"]!=sha256_file(report):raise ValueError("Existing independent review belongs to another report")
            write_once(review / f"{label}-existing-review-preserved.json",{"existing":link(output),"peer":link(review / f"{label}-comprehensive-review.json"),"action":"Existing independent judgment is preserved; this source-reader's peer review is a separate sidecar."})
        else:write_once(output,final)
        print(json.dumps({"seed":seed,"arm":name,"report":label,"occurrences":len(claims),"unsupported":unsupported,"pending":pending},ensure_ascii=False))
    assert original_before=={str(path):sha256_file(path) for path in original_paths}, "Participant report/evidence modified"
    for original in (Path(__file__),ROOT / "evaluation/prepare_independent_review.py",ROOT / "evaluation/review_partial_upstream.py"):
        target=source_dir / original.name
        if target.exists() and target.read_bytes()!=original.read_bytes():raise ValueError("Review source snapshot differs")
        if not target.exists():target.write_bytes(original.read_bytes())


if __name__=="__main__":
    for seed,name in ((31,"C"),(43,"B"),(43,"C")):review_case(seed,name)
