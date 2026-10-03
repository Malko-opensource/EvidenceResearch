"""Author engineering checks on explicit synthetic receipts and tiny public rows.

These fixtures do not execute a provider, sample owner data or run a research
study. Their positive component predicates never qualify an actual report.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from evidence_research.context_boundary import ContextBoundaryRecorder
from evidence_research.model import CodexProvider
from evidence_research.report_semantics import (evaluate_predicate, evaluate_fixture_predicate,
    evaluate_fixture_nonresult_context, semantic_units, semantic_claim, run_reference,
    _review_claim, _strict_proposal_object)
from evidence_research.tasks import TASK_VERSION, make_spec, run_task, sha256_file, value_hash, write_json
from evidence_research.verifier import verify


def link(path): return {"path":str(path.resolve()), "sha256":sha256_file(path)}


class EvidenceFixture:
    """Source-bound synthetic transport; all rows and flags are constructed here."""
    def __init__(self, root, arm="C"):
        self.root=Path(root).resolve(); self.root.mkdir(parents=True); self.arm=arm
        self.envelope={"reasoning_effort":"medium", "proposal_calls_per_unit":20,"actual_cpu_executions_per_unit":20}
        # These are explicit public engineering rows; no private generator exists.
        train=[{"id":f"train-{i}","x":x,"y":1+x*x} for i,x in enumerate((-1.,-.6,-.2,.2,.6,1.))]
        validation=[{"id":f"validation-{i}","x":x,"y":1+x*x} for i,x in enumerate((-.8,0.,.8))]
        splits={key:{"count":len(rows),"sha256":value_hash(rows),"ids_sha256":value_hash([r["id"] for r in rows])} for key,rows in (("train",train),("validation",validation))}
        bundle={"train":train,"validation":validation,"split_manifest":{"task_id":"public-engineering","task_version":TASK_VERSION,"seed":7,"generation":"explicit tiny public arrays, fixture only","splits":splits}}
        self.public={"task_id":"public-engineering","seed":7,"task_bundle":bundle}
        sources=Path(__file__).resolve().parents[1]/"evidence_research"
        self.registration=self.root/"callback-registration.json"
        write_json(self.registration,{"public_task":self.public,"model_id":"synthetic-model","resource_envelope":self.envelope,
            "implementation_sha256":sha256_file(sources/("arms.py" if arm=="B" else "comparison_arms.py")),"fixture_only":True})
        self.recorder=ContextBoundaryRecorder(self.root,arm=arm,registration=self.registration,model_id="synthetic-model",
            resource_envelope=self.envelope,public_task=self.public,fixture_only=True)
        self.provider=SimpleNamespace(model="synthetic-model",reasoning_effort="medium",guard=CodexProvider.guard,evidence_dir=self.root/"model")
        self.transport=self.root/"model-transport.jsonl"; self.count=0; self.cpu_count=0

    def model(self, response=None, *, failed=False, usage=None, phase=None, role=None):
        call=f"{'improved' if self.arm=='C' else 'upstream'}-{self.count:04d}"; self.count+=1
        role=role or ({"module":"evidence_research.comparison_arms","qualname":"ImprovedArm.__call__","actor_class":"ImprovedArm","reviewer_type":None} if self.arm=="C" else {"module":"agents","qualname":"BaseAgent.inference","actor_class":"PostdocAgent","reviewer_type":None})
        logical={"ordinal":self.count-1,"host_ordinal":len([r for r in self.recorder.rows if r["event"] in ("provider_terminal","host_return")]),
            "phase":phase or ("PROPOSE" if self.arm=="C" else "plan formulation"),"role":role}
        prompt=json.dumps({"goal":"We propose an unexecuted tiny public fixture."},ensure_ascii=False,sort_keys=True)
        full=CodexProvider.guard+prompt
        boundary=self.recorder.capture(call_id=call,prompt=prompt,full_prompt=full,logical_context=logical,transport_path=self.transport,provider=self.provider)
        transport={"call_id":call,"status":"requested","context_boundary":boundary,"logical_request":logical}
        with self.transport.open("a",encoding="utf-8") as stream: stream.write(json.dumps(transport)+"\n")
        folder=self.provider.evidence_dir/call; folder.mkdir(parents=True)
        request={"model":"synthetic-model","reasoning_effort":"medium","prompt":prompt,"full_prompt":full,
            "execution_kind":"simulation_fixture","fixture_only":True,"provider_source_sha256":self.recorder.binding["sources"]["model.py"]}
        identity={k:request[k] for k in ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")}
        request["fingerprint"]=value_hash(identity)
        request["command"]=["codex","exec","--ignore-user-config","--ephemeral","--skip-git-repo-check","--sandbox","read-only","--model","synthetic-model","--cd",str(self.root/"public_model_cwd"),"--json","-c",'approval_policy="never"',"--output-last-message",str(folder/"response.txt"),"-c",'model_reasoning_effort="medium"',"-"]
        write_json(folder/"request.json",request)
        raw={"type":"turn.failed" if failed else "turn.completed"}
        if not failed: raw["usage"]=usage or {"input_tokens":10,"output_tokens":3,"cached_input_tokens":0}
        elif usage is not None: raw["usage"]=usage
        (folder/"events.jsonl").write_text(json.dumps(raw)+"\n",encoding="utf-8")
        body=response if isinstance(response,str) else json.dumps(response or {"candidates":[{"hypothesis":"We propose a future comparison."}]},ensure_ascii=False)
        (folder/"response.txt").write_text(body,encoding="utf-8"); (folder/"stderr.log").write_bytes(b"")
        result={"status":"failed" if failed else "completed","model":"synthetic-model","fingerprint":request["fingerprint"],
            "execution_kind":"simulation_fixture","fixture_only":True,"tool_calls":[],"usage":raw.get("usage"),"wall_seconds":1.25,"returncode":1 if failed else 0,
            "files":{name:sha256_file(folder/name) for name in ("request.json","events.jsonl","response.txt","stderr.log")}}
        write_json(folder/"result.json",result)
        self.recorder.record_model(folder=folder,logical_context=logical,boundary=boundary)
        with self.transport.open("a",encoding="utf-8") as stream: stream.write(json.dumps({**transport,"status":result["status"],"evidence_dir":str(folder)})+"\n")
        return boundary,folder,logical

    def cpu(self, config=None, *, criterion=None, baseline=None, boundary=None, invalid=False):
        folder=self.root/f"research/runs/cpu-{self.cpu_count:04d}"; self.cpu_count+=1; folder.mkdir(parents=True)
        spec=make_spec(self.public["task_id"],7,config or {"degree":2,"alpha":0.},model="synthetic-model",
            criterion=criterion,resource_envelope=self.envelope,task_bundle=self.public["task_bundle"])
        spec["fixture_only"]=True
        if invalid: spec["config"]={"degree":99,"alpha":0.}
        if baseline is not None: spec["baseline"]={"run_id":baseline.name}
        if boundary is not None:
            from evidence_research.context_boundary import audit_context_boundary
            facts=audit_context_boundary(boundary,self.root)
            spec["model_evidence"]={"call_id":facts["call_id"],"fingerprint":facts["request_fingerprint"]}
        write_json(folder/"registered_spec.json",spec); result=run_task(spec,folder); checked=verify(spec,result,folder)
        if checked["valid"] is not True: raise AssertionError(checked)
        returned=json.dumps({"execution_kind":"actual_cpu_execution","execution_id":folder.name,"metrics":checked["metrics"]},sort_keys=True)
        self.recorder.record_cpu_return(logical_context={"ordinal":self.cpu_count-1,"host_ordinal":len(self.recorder.rows),"phase":"EXECUTE","role":"explicit_public_fixture"},returned_text=returned,records=[{"run_dir":str(folder)}])
        return folder,checked

    def audit(self):
        completed=[]; failed=[]; totals={"input_tokens":0,"output_tokens":0}; completed_totals=dict(totals); known=True; elapsed=0.
        for p in sorted((self.root/"model").glob("*/result.json")):
            r=json.loads(p.read_text(encoding="utf-8")); (completed if r["status"]=="completed" else failed).append(str(p.parent))
            elapsed+=r["wall_seconds"]; u=r.get("usage")
            if not isinstance(u,dict): known=False
            else:
                for k in totals:
                    totals[k]+=u[k]
                    if r["status"]=="completed":completed_totals[k]+=u[k]
        measures={"provider_calls":len(completed),"provider_attempts":len(completed)+len(failed),"failed_model_attempts":len(failed),"model_seconds":elapsed}
        for k in totals:measures[k]=totals[k] if known else None; measures["completed_"+k]=completed_totals[k]
        path=self.root/"independent-resource-audit.json"
        write_json(path,{"schema_version":"independent-resource-audit-1","arm_output":str(self.root),"model_id":"synthetic-model","resource_envelope":self.envelope,
            "completed_model_evidence_dirs":completed,"failed_model_attempt_dirs":failed,"host_action_receipts":{},"continuation_lineage_path":None,"measures":measures})
        return path


def knowledge(audit,known=True,field="tokens_known",text=None):
    return {"kind":"execution_provenance","predicate_id":"resource_knowledge","text":text or ("Token usage is known for all actual provider attempts." if known else "Token usage is not known for all actual provider attempts."),
        "arguments":{"resource_audit":link(audit),"field":field,"value":known if field=="tokens_known" else None}}


def incumbent(run,baseline,boundary,success=False):
    return {"kind":"execution_provenance","predicate_id":"registered_incumbent_criterion",
        "text":"Execution succeeded and the registered incumbent criterion was met." if success else "Execution succeeded and the registered incumbent criterion was not met.",
        "arguments":{"run":run_reference(run),"baseline":run_reference(baseline),"boundary":boundary,"success":success}}


def planning(f,boundary,folder,text,pointer="/candidates/0/hypothesis",priors=None):
    unit=next(u for u in semantic_units(json.dumps({"hypothesis":text}),"a"*64) if u["unit_kind"]=="json_string")
    claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Exact original response authorship, not factual truth.",
        nonresult_context={"kind":"original_proposal_output","boundary":boundary,"response":link(folder/"response.txt"),"field_pointer":pointer,"prior_runs":priors or []})
    return claim,unit


class C9SemanticEvidenceTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(prefix="c9-semantic-public-"); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_whole_token_knowledge_both_arms_component_only(self):
        values=[]
        for arm in ("B","C"):
            f=EvidenceFixture(self.root/arm,arm); f.model(); f.model(); claim=knowledge(f.audit())
            proof=evaluate_fixture_predicate(claim,f.root); values.append(proof["facts"]["value"])
            self.assertEqual(proof["facts"]["evidence_class"],"synthetic_fixture"); self.assertFalse(proof["facts"]["adoption_eligible"])
            with self.assertRaises(ValueError): evaluate_predicate(claim,f.root)
        self.assertEqual(values,[True,True])

    def test_unknown_failed_usage_not_zero_or_known(self):
        f=EvidenceFixture(self.root/"unknown"); f.model(); f.model(failed=True); path=f.audit()
        self.assertFalse(evaluate_fixture_predicate(knowledge(path,False),f.root)["facts"]["value"])
        with self.assertRaises(ValueError):evaluate_fixture_predicate(knowledge(path,True),f.root)
        claim=knowledge(path,False); claim["arguments"]["value"]=None
        with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)

    def test_attested_failed_usage_known_and_null_billing(self):
        f=EvidenceFixture(self.root/"known");f.model();f.model(failed=True,usage={"input_tokens":2,"output_tokens":0});path=f.audit()
        self.assertTrue(evaluate_fixture_predicate(knowledge(path),f.root)["facts"]["value"])
        claim=knowledge(path,field="provider_billed_cost",text="Provider billed cost is unavailable.")
        self.assertIsNone(evaluate_fixture_predicate(claim,f.root)["facts"]["value"])
        claim["arguments"]["value"]=0
        with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)

    def test_knowledge_omitted_and_duplicate_request_rejected_after_rehash(self):
        f=EvidenceFixture(self.root/"inventory");f.model();f.model();path=f.audit(); original=json.loads(path.read_text())
        for dirs in (original["completed_model_evidence_dirs"][:1],original["completed_model_evidence_dirs"]*2):
            changed=deepcopy(original);changed["completed_model_evidence_dirs"]=dirs;write_json(path,changed)
            with self.assertRaises(ValueError):evaluate_fixture_predicate(knowledge(path),f.root)

    def test_knowledge_false_same_scalar_cannot_replace_raw_inventory(self):
        f=EvidenceFixture(self.root/"scalar");f.model();path=f.audit();record=json.loads(path.read_text());record["measures"]["input_tokens"]=99;write_json(path,record)
        with self.assertRaises(ValueError):evaluate_fixture_predicate(knowledge(path),f.root)

    def test_knowledge_scope_and_boolean_types_strict(self):
        f=EvidenceFixture(self.root/"types");f.model();path=f.audit()
        for value in (1,0,"true",None):
            claim=knowledge(path);claim["arguments"]["value"]=value
            with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)
        for raw in ("Token usage is known and research performance improved.","Before this proposal, token usage is known."):
            with self.assertRaises(ValueError):evaluate_fixture_predicate(knowledge(path,text=raw),f.root)

    def test_resource_scalar_pointer_cannot_support_an_arbitrary_field(self):
        f=EvidenceFixture(self.root/"pointer");f.model();path=f.audit()
        for pointer_text in ({"resources":{"tokens_known":True}},{"framework_is_superior":True}):
            text=json.dumps(pointer_text);unit=next(u for u in semantic_units(text,"b"*64) if u["unit_kind"]=="json_scalar")
            claim=semantic_claim(unit,kind="execution_provenance",outcome="supported",rationale="Full resource knowledge Boolean.",predicate_id="resource_knowledge",arguments=knowledge(path)["arguments"])
            # Production rejects synthetic data even at the correct pointer;
            # wrong pointer must fail earlier for its independent scope reason.
            if unit["pointer"]=="/framework_is_superior":
                with self.assertRaisesRegex(ValueError,"structured field"):_review_claim(claim,unit,f.root)
            else:
                with self.assertRaises(ValueError):_review_claim(claim,unit,f.root)

    def test_incumbent_tie_strictly_rejected_and_execution_distinct(self):
        f=EvidenceFixture(self.root/"tie");base,bv=f.cpu();b,_,_=f.model();run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"],"improvement":0.},baseline=base,boundary=b)
        claim=incumbent(run,base,b);proof=evaluate_fixture_predicate(claim,f.root)
        self.assertFalse(proof["facts"]["success"]);self.assertTrue(proof["facts"]["execution_success"])
        self.assertEqual(proof["facts"]["outcome"],"criterion_rejection")
        with self.assertRaises(ValueError):evaluate_fixture_predicate(incumbent(run,base,b,True),f.root)
        with self.assertRaises(ValueError):evaluate_predicate(claim,f.root)

    def test_incumbent_improvement_and_margin_boundary(self):
        for index,margin_kind in enumerate(("zero","equal","larger")):
            f=EvidenceFixture(self.root/f"margin-{index}");base,bv=f.cpu({"degree":1,"alpha":0.});b,_,_=f.model()
            # The true best fit on explicit rows has essentially zero error.
            reference,_=f.cpu();rv=json.loads((reference/"result.json").read_text())["metrics"]["validation_mse"]
            gain=bv["metrics"]["validation_mse"]-rv
            margin=0. if margin_kind=="zero" else gain if margin_kind=="equal" else gain+1.
            run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"],"improvement":margin},baseline=base,boundary=b)
            proof=evaluate_fixture_predicate(incumbent(run,base,b,margin_kind=="zero"),f.root)
            self.assertEqual(proof["facts"]["success"],margin_kind=="zero")

    def test_incumbent_rejects_future_baseline_and_wrong_candidate_call(self):
        f=EvidenceFixture(self.root/"future");b,_,_=f.model();base,bv=f.cpu();run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"]},baseline=base,boundary=b)
        with self.assertRaisesRegex(ValueError,"original prior"):evaluate_fixture_predicate(incumbent(run,base,b),f.root)
        later,_,_=f.model()
        with self.assertRaisesRegex(ValueError,"exact original proposal"):evaluate_fixture_predicate(incumbent(run,base,later),f.root)

    def test_incumbent_wrong_baseline_number_and_scope_rejected(self):
        f=EvidenceFixture(self.root/"wrong-baseline");base,bv=f.cpu();b,_,_=f.model();run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"]+1.},baseline=base,boundary=b)
        with self.assertRaisesRegex(ValueError,"baseline value"):evaluate_fixture_predicate(incumbent(run,base,b),f.root)
        claim=incumbent(run,base,b);claim["text"]="This was the best candidate and improved research performance."
        with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)

    def test_incumbent_max_direction_and_absolute_threshold_both_apply(self):
        for index,threshold in enumerate((0.,100.)):
            f=EvidenceFixture(self.root/f"max-{index}");base,bv=f.cpu();b,_,_=f.model()
            run,_=f.cpu({"degree":1,"alpha":0.},criterion={"direction":"max","baseline_value":bv["metrics"]["validation_mse"],"improvement":0.,"threshold":threshold},baseline=base,boundary=b)
            success=threshold==0.
            self.assertEqual(evaluate_fixture_predicate(incumbent(run,base,b,success),f.root)["facts"]["success"],success)

    def test_incumbent_malformed_success_and_forecast_cannot_be_supported(self):
        f=EvidenceFixture(self.root/"incumbent-types");base,bv=f.cpu();b,_,_=f.model()
        run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"]},baseline=base,boundary=b)
        for value in (0,1,"false",None):
            claim=incumbent(run,base,b);claim["arguments"]["success"]=value
            with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)
        claim=incumbent(run,base,b);claim["text"]+=" The next fit will improve generalization."
        with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)

    def test_incumbent_technical_failure_not_successful_execution(self):
        f=EvidenceFixture(self.root/"technical");base,bv=f.cpu();b,_,_=f.model();run,_=f.cpu(criterion={"direction":"min","baseline_value":bv["metrics"]["validation_mse"]},baseline=base,boundary=b,invalid=True)
        claim=incumbent(run,base,b)
        with self.assertRaisesRegex(ValueError,"conflate execution"):evaluate_fixture_predicate(claim,f.root)
        claim["text"]="Execution failed; the registered incumbent criterion was not met."
        proof=evaluate_fixture_predicate(claim,f.root);self.assertEqual(proof["facts"]["outcome"],"technical_failure");self.assertIsNone(proof["facts"]["value"])

    def test_common_original_proposal_authorship_nonresult_only(self):
        text="We propose a future comparison."
        for arm in ("B","C"):
            f=EvidenceFixture(self.root/arm,arm);b,folder,_=f.model(text if arm=="B" else {"candidates":[{"hypothesis":text}]})
            claim,unit=planning(f,b,folder,text,pointer="" if arm=="B" else "/candidates/0/hypothesis")
            proof=evaluate_fixture_nonresult_context(claim,unit,f.root);self.assertFalse(proof["adoption_eligible"])
            with self.assertRaises(ValueError):_review_claim(claim,unit,f.root)

    def test_original_proposal_cannot_truncate_factual_sentence(self):
        original="We propose a future comparison. Memory caused the improvement."
        f=EvidenceFixture(self.root/"truncate");b,folder,_=f.model({"candidates":[{"hypothesis":original}]})
        claim,unit=planning(f,b,folder,"We propose a future comparison.")
        with self.assertRaisesRegex(ValueError,"shorten"):evaluate_fixture_nonresult_context(claim,unit,f.root)
        claim,unit=planning(f,b,folder,original)
        with self.assertRaises(ValueError):evaluate_fixture_nonresult_context(claim,unit,f.root)

    def test_original_completed_factual_result_does_not_become_planning(self):
        text="We propose next steps. The outcome was independently replicated."
        f=EvidenceFixture(self.root/"fact");b,folder,_=f.model({"stop_reason":text});claim,unit=planning(f,b,folder,text,"/stop_reason")
        with self.assertRaises(ValueError):evaluate_fixture_nonresult_context(claim,unit,f.root)

    def test_original_proposal_phase_role_and_arm_transplants_rejected(self):
        text="We propose a future comparison."
        for index,(arm,phase,role) in enumerate((("B","report writing",None),("C","plan formulation",None),("C","PROPOSE",{"module":"agents","qualname":"BaseAgent.inference","actor_class":"PostdocAgent"}))):
            f=EvidenceFixture(self.root/f"transplant-{index}",arm);b,folder,_=f.model(text if arm=="B" else {"candidates":[{"hypothesis":text}]},phase=phase,role=role)
            claim,unit=planning(f,b,folder,text,"" if arm=="B" else "/candidates/0/hypothesis")
            with self.assertRaisesRegex(ValueError,"non-planning"):evaluate_fixture_nonresult_context(claim,unit,f.root)

    def test_original_proposal_wrong_response_and_duplicate_key_rejected(self):
        f=EvidenceFixture(self.root/"wrong-response");b,folder,_=f.model();_,other,_=f.model()
        claim,unit=planning(f,b,folder,"We propose a future comparison.");claim["nonresult_context"]["response"]=link(other/"response.txt")
        with self.assertRaises(ValueError):evaluate_fixture_nonresult_context(claim,unit,f.root)
        for raw in ('{"candidates":[],"candidates":[]}', 'Before the result {"candidates":[]}','```json\n{}\n```\nExtra assertion.'):
            with self.assertRaises(ValueError):_strict_proposal_object(raw)

    def test_exact_rationale_and_stop_fields_cannot_be_changed_or_supported_as_truth(self):
        text="We propose an unexecuted comparison."
        f=EvidenceFixture(self.root/"rationale");b,folder,_=f.model({"candidates":[{"hypothesis":text,"selection_reason":text,"assessment":{"rationale":text}}],"stop_reason":text})
        for pointer in ("/candidates/0/selection_reason","/candidates/0/assessment/rationale","/stop_reason"):
            claim,unit=planning(f,b,folder,text,pointer)
            self.assertFalse(evaluate_fixture_nonresult_context(claim,unit,f.root)["adoption_eligible"])
            claim["outcome"]="supported";claim["predicate_id"]="original_proposal_output"
            with self.assertRaises(ValueError):_review_claim(claim,unit,f.root)
        claim,unit=planning(f,b,folder,text+" The framework is superior.","/stop_reason")
        with self.assertRaises(ValueError):evaluate_fixture_nonresult_context(claim,unit,f.root)

    def test_planning_actual_prior_descriptor_requires_matching_source_bound_fit(self):
        f=EvidenceFixture(self.root/"actual-prior");base,_=f.cpu({"degree":1,"alpha":0.})
        text="We propose a future comparison with the verified linear model."
        b,folder,_=f.model({"candidates":[{"hypothesis":text}]})
        claim,unit=planning(f,b,folder,text,priors=[run_reference(base)])
        self.assertTrue(evaluate_fixture_nonresult_context(claim,unit,f.root)["prior_adjectives"])
        wrong="We propose a future comparison with the verified quadratic model."
        other,ofolder,_=f.model({"candidates":[{"hypothesis":wrong}]})
        claim,unit=planning(f,other,ofolder,wrong,priors=[run_reference(base)])
        with self.assertRaisesRegex(ValueError,"descriptor"):evaluate_fixture_nonresult_context(claim,unit,f.root)

    def test_all_fixture_aliases_propagate_and_malformed_metadata_rejects(self):
        for index,flag in enumerate(("fixture_only","simulation_only","test_fixture_only")):
            f=EvidenceFixture(self.root/f"flag-{index}");f.model();path=f.audit();raw=json.loads(path.read_text())
            raw[flag]=True;write_json(path,raw)
            self.assertFalse(evaluate_fixture_predicate(knowledge(path),f.root)["facts"]["adoption_eligible"])
            for malformed in (None,1,"false"):
                raw[flag]=malformed;write_json(path,raw)
                with self.assertRaisesRegex(ValueError,"malformed fixture"):evaluate_fixture_predicate(knowledge(path),f.root)

    def test_production_cannot_activate_component_through_arguments_or_keyword(self):
        f=EvidenceFixture(self.root/"no-switch");f.model();path=f.audit();claim=knowledge(path)
        with self.assertRaises(TypeError):evaluate_predicate(claim,f.root,_component_fixture=True)
        claim["arguments"]["component_fixture"]=True
        with self.assertRaises(ValueError):evaluate_fixture_predicate(claim,f.root)

    def test_future_prior_and_missing_field_cannot_enable_planning(self):
        f=EvidenceFixture(self.root/"prior");b,folder,_=f.model();future,_=f.cpu()
        claim,unit=planning(f,b,folder,"We propose a future comparison.",priors=[run_reference(future)])
        with self.assertRaisesRegex(ValueError,"future"):evaluate_fixture_nonresult_context(claim,unit,f.root)
        claim,unit=planning(f,b,folder,"We propose a future comparison.",pointer="/candidates/0/selection_reason")
        with self.assertRaisesRegex(ValueError,"missing"):evaluate_fixture_nonresult_context(claim,unit,f.root)


if __name__=="__main__": unittest.main()
