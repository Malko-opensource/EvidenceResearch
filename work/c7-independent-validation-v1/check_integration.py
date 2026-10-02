"""Independent metadata/source-closure checks; fictitious values are not scores.

No registration, private suite, model or task runner is invoked. An explicit
empty engineering marker substitutes for a sealed-file hash contract only.
"""
from copy import deepcopy
from pathlib import Path
import ast,json,math,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];CANDIDATE=ROOT/"work/c7"
sys.path.insert(0,str(CANDIDATE))
from transport_fixture import sha,write
from evidence_research.report_semantics import frozen_semantic_reference_hashes
from evidence_research.evaluation import (_semantic_score_ready,analyze_pairs,frozen_sources,
    _assert_frozen,PROTOCOL_VERSION,EFFICIENCY_PROTOCOL_VERSION)
from evidence_research.study import _report_scores_complete

def main():
    number=len(list(HERE.glob("integration-attempt-*.json")))+1
    start=time.perf_counter();sources=list((CANDIDATE/"evidence_research").glob("*.py"))
    before={str(p.relative_to(CANDIDATE)):sha(p) for p in sources}
    good={"semantic_report_audit_complete":True,"unsupported_semantic_result_claims":0,"semantic_evidence_qualification":"actual"}
    attacks=[{"fixture_only":True},{"component_only":True},{"evidence_class":"synthetic_fixture"},
        {"evaluation_scope":"synthetic_engineering_fixture"},{"semantic_evidence_qualification":"component_fixture"},
        {"semantic_evidence_qualification":"engineering_legacy"},{"semantic_evidence_qualification":"unqualified"},
        {"evaluation_scope":["actual"]},{"semantic_evidence_qualification":{}},{"fixture_only":"false"},{"evaluation_scope":"unknown_scope"},
        {"simulation_only":True},{"test_fixture_only":True},{"simulation_only":"false"},{"test_fixture_only":None},
        {"fixture_only":None},{"component_only":None},{"simulation_only":None},{"evidence_class":None},
        {"evaluation_scope":None},{"semantic_evidence_qualification":None}]
    metadata=[];errors=[]
    for change in attacks:
        outputs={str(required):_semantic_score_ready({**good,**change},required=required) for required in (True,False)}
        metadata.append({"fields":change,"gate_boolean":outputs,"expected":False})
        if any(outputs.values()):errors.append({"gate":"semantic_score_ready","fields":change})
    false_count=_semantic_score_ready({**good,"unsupported_semantic_result_claims":False},required=True)
    if false_count:errors.append({"gate":"semantic_boolean_unsupported_count"})
    refs=frozen_semantic_reference_hashes();frozen=frozen_sources([Path(p) for p in refs])
    expected={"context_boundary.py","report_semantics.py","source_facts_c7.json","task_literature_v2.json"}
    missing=expected-{Path(p).name for p in frozen}
    if missing:errors.append({"gate":"frozen_source_closure","missing":sorted(missing)})
    if any(frozen.get(p)!=v for p,v in refs.items()):errors.append({"gate":"frozen_source_reference_pin"})
    marker=HERE/f"empty-engineering-marker-{number:04d}.json";write(marker,{"fixture_only":True,"scope":"Empty marker for file integrity only; no owner/task data"})
    protocol={"status":"preregistered","version":EFFICIENCY_PROTOCOL_VERSION,"frozen_sources":frozen,
        "suite":{"private_file":str(marker),"private_sha256":sha(marker)}}
    # This calls no registration or owner metric; all opened paths are listed static sources or own marker.
    _assert_frozen(protocol);source_attacks=[]
    for path in refs:
        altered=deepcopy(protocol);altered["frozen_sources"][path]="0"*64
        try:_assert_frozen(altered);rejected=False
        except ValueError:rejected=True
        source_attacks.append({"path":path,"wrong_external_pin_rejected":rejected})
        if not rejected:errors.append({"gate":"wrong_reference_source_pin","path":path})
    # Pure shape/statistical control. Every number here is invented fixture data;
    # analyze_pairs does not replace the actual owner-score artifact validator.
    fields={"status":"verified","test_mse":1.0,"validation_mse":1.0,"execution_seconds":1.0,"arm_wall_seconds":1.0,
        "provider_calls":1,"duplicate_executions":0,"recovered_errors":0,"unsupported_claims":0,"verified_memory_hits":0,
        "task_success":True,"provider_billed_cost":None,"whole_report_numeric_audit_complete":True,"common_report_sufficiency":True,
        "unsupported_numeric_claims":0,**good}
    pairs=[{"unit_id":f"synthetic-{i}","relative_gain":0.5,"B":deepcopy(fields),"C":{**deepcopy(fields),"test_mse":0.5}} for i in range(3)]
    p={"version":PROTOCOL_VERSION,"primary_metric":"test_mse","suite":{"task_ids":[r["unit_id"] for r in pairs]},
        "adoption":{"minimum_mean_relative_gain":0.1},"baseline_provenance":{"kind":"structural_baseline"},"model_effect_A":{"estimated":False}}
    shape_control=analyze_pairs(p,pairs)["adopted"]
    if not shape_control:errors.append({"gate":"shape_control_did_not_reach_statistical_branch"})
    shape_attacks=[]
    for change in attacks:
        mutant=deepcopy(pairs);mutant[0]["C"].update(change)
        adopted=analyze_pairs(p,mutant)["adopted"]
        shape_attacks.append({"fields":change,"synthetic_statistical_adopted_boolean":adopted,"expected":False})
        if adopted:errors.append({"gate":"analyze_pairs_nonactual_metadata","fields":change})
    study_tree=ast.parse((CANDIDATE/"evidence_research/study.py").read_text(encoding="utf-8"))
    bindings={}
    for name in ("register_pilot","check_pilot"):
        function=next(n for n in study_tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
        names={n.id for n in ast.walk(function) if isinstance(n,ast.Name)}
        bindings[name]={"frozen_semantic_reference_hashes_called":"frozen_semantic_reference_hashes" in names,
            "frozen_upstream_sources_called":"frozen_upstream_sources" in names}
        if not all(bindings[name].values()):errors.append({"gate":"study_reference_closure","function":name})
    after={str(p.relative_to(CANDIDATE)):sha(p) for p in sources}
    frozen_guard=json.loads((HERE/"frozen-source-before.json").read_text(encoding="utf-8"))
    changed=[r["path"] for r in frozen_guard["files"] if sha(ROOT/r["path"])!=r["sha256"]]
    out={"schema_version":"independent-c7-integration-shape-source-closure-1","status":"provisional_pass" if not errors and before==after and not changed else "provisional_failed",
        "errors":errors,"metadata_attacks":metadata,"boolean_unsupported_count_accepted":false_count,"source_reference_inventory":refs,"source_pin_attacks":source_attacks,
        "required_modules_and_external_json_present":not missing,"study_ast_bindings":bindings,
        "analyze_pairs_shape_control_boolean":shape_control,"analyze_pairs_metadata_attacks":shape_attacks,
        "shape_control_is_real_adoption_proof":False,"source_before":before,"source_after":after,"candidate_stable":before==after,
        "frozen_changed":changed,"actual_provider_calls":0,"cpu_fit_executions":0,"actual_research_trials":0,"owner_test_private_generation_reads":False,
        "monetary_cost":None,"helper_seconds":time.perf_counter()-start,"fixture_only":True,"source_freeze":False,
        "scope":"Synthetic Boolean control and explicit listed source/hash closure only; no final protocol registration or actual score qualification."}
    path=HERE/f"integration-attempt-{number:04d}.json";write(path,out)
    print(json.dumps({"status":out["status"],"errors":errors,"candidate_stable":before==after,"frozen_changed":changed},ensure_ascii=True))
    if out["status"]!="provisional_pass":raise SystemExit(1)

if __name__=="__main__":main()
