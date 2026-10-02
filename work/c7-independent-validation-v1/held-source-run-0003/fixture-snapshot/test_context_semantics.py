"""Independent registered original-input/prefix attacks, engineering only.

All model-shaped receipts are visibly synthetic. Actual tiny CPU fits only
exercise artifact contracts over explicit public arrays, never private data.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import hashlib
import unittest

from transport_fixture import BoundaryFixture, compact, digest, link, sha, write
from evidence_research.context_boundary import audit_context_boundary
from evidence_research.report_semantics import (evaluate_predicate,evaluate_fixture_predicate,
    evaluate_fixture_nonresult_context,parse_temporal_resource_list,_check_nonresult_scope,
    semantic_claim,prepare_semantic_review,adjudicate_semantic_review,run_reference)
import evidence_research.report_semantics as semantics

SCRATCH=None


class ContextSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SCRATCH is None: raise RuntimeError("use independent driver")
        cls.root=Path(SCRATCH);cls.root.mkdir(parents=True)
        cls.index=0;cls.observations=[]
        cls.good={arm:BoundaryFixture(cls.root/arm,arm,include_all_returns=True,
            selected_plan="We will test a change to the verified regularized quadratic fit.") for arm in ("B","C")}

    def fresh(self,**kwargs):
        type(self).index+=1
        return BoundaryFixture(self.root/f"mutant-{self.index:03d}","C",with_cpu=False,**kwargs)

    def claim(self,f=None,text="Before this proposal, measured input usage was 30 tokens.",measure="input_tokens",value=30):
        f=f or self.good["C"]
        return {"kind":"execution_provenance","predicate_id":"historical_context_resources","text":text,
            "arguments":{"boundary":f.target(),"scope":"historical_pre_request","measure":measure,"value":value}}

    def positive(self,f=None):
        f=f or self.good["C"]
        proof=evaluate_fixture_predicate(self.claim(f),f.root)
        self.assertEqual(proof["facts"]["value"],30)
        self.assertFalse(proof["facts"]["adoption_eligible"])
        self.assertEqual(proof["facts"]["evidence_class"],"synthetic_fixture")
        return proof

    @contextmanager
    def changed(self,path,value):
        path=Path(path);before=path.read_bytes();old_sha=sha(path)
        if isinstance(value,bytes): path.write_bytes(value)
        else: write(path,value)
        type(self).observations.append({"path":str(path),"before_sha256":old_sha,"mutant_sha256":sha(path),"restored_after_case":True})
        try: yield
        finally: path.write_bytes(before)

    def test_prefix_valid_both(self):
        proofs=[]
        for arm,f in self.good.items():
            proof=self.positive(f);proofs.append(proof["facts"])
            audit=audit_context_boundary(f.target(),f.root)
            self.assertEqual(audit["measures"]["completed_provider_calls"],2)
            self.assertEqual(audit["measures"]["actual_cpu_executions"],2)
            self.assertEqual(audit["measures"]["input_tokens"],30)
            self.assertEqual(audit["request_fingerprint"],json.loads((f.folders[2]/"request.json").read_text())["fingerprint"])
            with self.assertRaises(ValueError): evaluate_predicate(self.claim(f),f.root)
        self.assertEqual(proofs[0],proofs[1])

    def test_prefix_final_relabel(self):
        self.positive()
        for text in ("The final whole-unit provider input usage was 30 tokens.",
            "Before this proposal, measured input usage was 60 tokens.",
            "Before this proposal, final input usage was 30 tokens."):
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text=text),self.good["C"].root)

    def test_prefix_arbitrary_subset(self):
        f=self.fresh();self.positive(f)
        tape=f.recorder.path;rows=[json.loads(x) for x in tape.read_text().splitlines()]
        omitted=next(row for row in rows if row["event"]=="provider_terminal")
        raw=b"".join(compact(row)+b"\n" for row in rows if row is not omitted)
        with self.changed(tape,raw):
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f,value=20,text="Before this proposal, measured input usage was 20 tokens."),f.root)

    def test_prefix_order(self):
        f=self.fresh();self.positive(f)
        rows=deepcopy(f.transport)
        # The physical target is retained but its logical ordinal/phase/role changes.
        for key,value in (("ordinal",0),("host_ordinal",0),("phase","earlier phase"),("role",{"kind":"different-role"})):
            mutated=deepcopy(rows);mutated[-2]["logical_request"][key]=value
            with self.changed(f.transport_path,b"".join(compact(row)+b"\n" for row in mutated)):
                with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f),f.root)

    def test_prefix_replay_doublecount(self):
        f=self.fresh(replay_prefix=True);self.positive(f)
        audit=audit_context_boundary(f.target(),f.root)
        self.assertEqual(audit["measures"]["input_tokens"],30)
        self.assertEqual(audit["measures"]["completed_provider_calls"],2)
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f,text="Before this proposal, measured input usage was 40 tokens.",value=40),f.root)
        with self.assertRaises(ValueError): f.recorder.record_model(folder=f.folders[0],logical_context={"ordinal":9},boundary=f.boundaries[0])

    def test_prefix_unknown_failure(self):
        f=self.fresh(failed_second=True)
        audit=audit_context_boundary(f.target(),f.root)
        self.assertIsNone(audit["measures"]["input_tokens"])
        self.assertEqual(audit["completed_token_usage_lower_bound"],{"input_tokens":10,"output_tokens":2})
        self.assertEqual(audit["measures"]["wall_seconds"],2.5)
        for v in (0,10,30):
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f,text=f"Before this proposal, measured input usage was {v} tokens.",value=v),f.root)
        proof=evaluate_fixture_predicate(self.claim(f,text="Before this request, measured resources were 2.50 provider wall seconds.",measure="wall_seconds",value=2.5),f.root)
        self.assertEqual(proof["facts"]["value"],2.5)

    def test_prefix_source_tamper(self):
        f=self.fresh();self.positive(f)
        request=f.folders[0]/"request.json";original=json.loads(request.read_text())
        for key,value in (("model","wrong-model"),("reasoning_effort","high"),("provider_source_sha256","0"*64),("full_prompt","missing guard"),("fingerprint","0"*64),("command",["codex","exec","--sandbox","danger-full-access"])):
            mutant={**original,key:value}
            with self.changed(request,mutant):
                with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f),f.root)
        target=Path(f.target()["path"]);original=json.loads(target.read_text())
        for name in ("tasks.py","model.py","arms.py"):
            mutant=deepcopy(original);mutant["binding"]["sources"][name]="0"*64
            with self.changed(target,mutant):
                with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f),f.root)
        with self.assertRaises(ValueError): audit_context_boundary(f.target(),self.good["B"].root)

    def test_prefix_missing_logical_tail(self):
        f=self.fresh();self.positive(f)
        orphan=f.root/"model/improved-9999";orphan.mkdir();write(orphan/"request.json",{"fixture_only":True})
        audit=audit_context_boundary(f.target(),f.root)
        self.assertIn("raw_terminal_receipt_has_missing_original_host_mapping",audit["pending_reasons"])
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f),f.root)

    def test_history_unqualified(self):
        self.positive()
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text="Provider input usage was 30 tokens."),self.good["C"].root)

    def test_history_list_valid(self):
        facts=[]
        for arm,f in self.good.items():
            audit=audit_context_boundary(f.target(),f.root)
            text="Before this proposal, measured resources were 2 CPU executions, 30 input tokens and 6 output tokens."
            proof=evaluate_fixture_predicate(self.claim(f,text=text),f.root);facts.append(proof["facts"])
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(f,text=text.replace("6 output","99 output")),f.root)
            self.assertEqual(audit["measures"]["actual_cpu_executions"],2)
        self.assertEqual(facts[0],facts[1])

    def test_history_appendix(self):
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text="This document has a historical appendix. Provider input usage was 30 tokens."),self.good["C"].root)

    def test_history_unrelated_design(self):
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text="Historically, we tested feature design, provider input usage was 30 tokens."),self.good["C"].root)

    def test_history_negated_intro(self):
        for raw in ("Not before this proposal, provider input usage was 30 tokens.","Before this proposal was not the scope; provider input usage was 30 tokens."):
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text=raw),self.good["C"].root)

    def test_history_mixed_final(self):
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text="Before this proposal, measured input usage was 30 tokens; final total usage was 30 tokens."),self.good["C"].root)

    def test_history_mixed_forecast(self):
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text="Before this proposal, measured input usage was 30 tokens, and the next experiment will improve error by 10 percent."),self.good["C"].root)

    def test_history_monetary_unknown(self):
        first="Before this proposal, measured input usage was 30 tokens."
        self.positive();_check_nonresult_scope("Monetary cost is unknown.","limitation")
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.claim(text=first+" Monetary cost is unknown."),self.good["C"].root)
        self.assertIsNotNone(parse_temporal_resource_list(first))

    def available(self,f,count):
        return {"kind":"execution_provenance","predicate_id":"report_input_availability",
            "text":f"The named original reporting input contains validation MSE values for {count} verified runs.",
            "arguments":{"boundary":f.target(),"scope":"named_original_input","metric":"validation_mse","count":count,"count_kind":"runs"}}

    def test_availability_context_not_history(self):
        values=[]
        for f in self.good.values():
            proof=evaluate_fixture_predicate(self.available(f,2),f.root);values.append(proof["facts"])
            self.assertIn("not whole agent history",proof["facts"]["scope"])
            claim=self.available(f,2);claim["text"]="The agent had only two scores in its entire history."
            with self.assertRaises(ValueError): evaluate_fixture_predicate(claim,f.root)
        self.assertEqual(values[0],values[1])
        one=BoundaryFixture(self.root/"one-score","B")
        self.assertEqual(evaluate_fixture_predicate(self.available(one,1),one.root)["facts"]["count"],1)
        self.assertEqual(audit_context_boundary(one.target(),one.root)["measures"]["actual_cpu_executions"],2)

    def test_availability_path_not_value(self):
        f=BoundaryFixture(self.root/"paths-only","C",paths_only=True)
        audit=audit_context_boundary(f.target(),f.root)
        self.assertEqual(audit["available_metrics"],[])
        self.assertEqual(evaluate_fixture_predicate(self.available(f,0),f.root)["facts"]["count"],0)
        with self.assertRaises(ValueError): evaluate_fixture_predicate(self.available(f,2),f.root)

    def test_availability_other_phase(self):
        f=self.good["C"];self.assertEqual(evaluate_fixture_predicate(self.available(f,2),f.root)["facts"]["count"],2)
        claim=self.available(f,2);claim["arguments"]["boundary"]=deepcopy(f.boundaries[1]);claim["text"]="The agent had only one score in all phases.";claim["arguments"]["count"]=1
        with self.assertRaises(ValueError): evaluate_fixture_predicate(claim,f.root)

    def test_availability_posthoc_context(self):
        f=self.fresh();self.positive(f)
        request=f.folders[2]/"request.json";original=json.loads(request.read_text())
        mutant={**original,"prompt":"Owner-generated summary constructed after the model response."}
        with self.changed(request,mutant):
            with self.assertRaises(ValueError): evaluate_fixture_predicate(self.available(f,0),f.root)
        claim=self.available(f,0);claim["arguments"]["boundary"]={"path":str(f.root/"invented-context.json"),"sha256":"0"*64}
        with self.assertRaises((ValueError,FileNotFoundError)): evaluate_fixture_predicate(claim,f.root)

    def test_availability_reading_upgrade(self):
        for f in self.good.values():
            evaluate_fixture_predicate(self.available(f,2),f.root)
            claim=self.available(f,2);claim["text"]="The agent read and understood all five papers."
            with self.assertRaises(ValueError): evaluate_fixture_predicate(claim,f.root)

    def test_planning_question_both(self):
        import ast
        for module in ("arms.py","comparison_arms.py"):
            path=Path(semantics.__file__).with_name(module);questions=[]
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node,ast.Dict):
                    for k,v in zip(node.keys,node.values):
                        if isinstance(k,ast.Constant) and k.value=="next_questions" and isinstance(v,ast.List):
                            questions += [q.value for q in v.elts if isinstance(q,ast.Constant) and isinstance(q.value,str)]
            self.assertTrue(questions)
            q=questions[0];unit={"unit_kind":"json_string","pointer":"/next_questions/0","decoded_text":q}
            claim={"kind":"proposal","outcome":"classified_nonresult","text":q,"nonresult_context":{"kind":"fixed_next_question","source":link(path)}}
            proof=evaluate_fixture_nonresult_context(claim,unit,self.good["C"].root)
            self.assertTrue(proof["fixed_question"]);self.assertFalse(proof["adoption_eligible"])
            claim["text"]="We achieved the best result?";unit["decoded_text"]=claim["text"]
            with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(claim,unit,self.good["C"].root)

    def test_planning_prior_adjective(self):
        from evidence_research.tasks import make_spec,run_task
        for f in self.good.values():
            raw="We will test a change to the verified regularized quadratic fit."
            unit={"unit_kind":"paragraph","decoded_text":raw}
            context={"kind":"context_boundary","boundary":f.target(),"field":"selected_native_plan","prior_runs":[run_reference(f.runs[1]["folder"])]}
            claim={"kind":"proposal","outcome":"classified_nonresult","text":raw,"nonresult_context":context}
            proof=evaluate_fixture_nonresult_context(claim,unit,f.root);self.assertTrue(proof["prior_adjectives"])
            # A genuine matching CPU artifact exists later than the target input;
            # availability is a temporal assertion, not just task/config equality.
            future=f.root/"research/runs/future-prior"
            spec=make_spec(f.public["task_id"],f.public["seed"],{"degree":2,"alpha":0.1},model=f.model,
                task_bundle=f.bundle,resource_envelope=f.envelope);spec["fixture_only"]=True
            result=run_task(spec,future);self.assertEqual(result["status"],"success")
            f.recorder.record_cpu_return(logical_context={"ordinal":3,"host_ordinal":6,"phase":"future component only","role":{"kind":"fixture-cpu"}},
                returned_text=json.dumps({"metrics":result["metrics"]},sort_keys=True),records=[{"run_dir":str(future)}])
            audit=audit_context_boundary(f.target(),f.root);self.assertEqual(audit["measures"]["actual_cpu_executions"],2)
            self.assertNotIn(str(future),{p["run_dir"] for p in audit["prior_runs"]})
            for priors in ([],[run_reference(f.runs[0]["folder"])],[run_reference(self.good["B" if f.arm=="C" else "C"].runs[1]["folder"])],[run_reference(future)]):
                mutant=deepcopy(claim);mutant["nonresult_context"]["prior_runs"]=priors
                with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(mutant,unit,f.root)
            # Task-condition substitution remains invalid after refreshing the
            # direct receipt and append-only tail hashes. The original prefix,
            # callback registration, data and actual model artifact stay fixed.
            spec_path=future/"registered_spec.json";original_spec=spec_path.read_bytes();original_tape=f.recorder.path.read_bytes()
            changed_spec=json.loads(original_spec);changed_spec["seed"]+=1;write(spec_path,changed_spec)
            rows=[json.loads(line) for line in original_tape.decode().splitlines()];old_id=None;new_receipt=None
            for row in rows:
                if row.get("event")=="cpu_terminal" and row["sources"]["registered_spec.json"]["path"]==str(spec_path):
                    old_id=row["receipt_identity"];row["sources"]["registered_spec.json"]=link(spec_path)
                    row["receipt_identity"]=digest(row["sources"]);new_receipt={"receipt_identity":row["receipt_identity"],"sources":row["sources"]}
                if row.get("event") in {"host_return","host_return_replay"} and old_id:
                    row["cpu_receipts"]=[new_receipt if item["receipt_identity"]==old_id else item for item in row["cpu_receipts"]]
            output=[]
            for row in rows:
                body={key:value for key,value in row.items() if key not in {"event_sha256","previous_sha256"}}
                body["previous_sha256"]=output[-1]["event_sha256"] if output else None
                output.append({**body,"event_sha256":digest(body)})
            f.recorder.path.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for row in output),encoding="utf-8")
            try:
                with self.assertRaisesRegex(ValueError,"CPU task/model/settings differ"):
                    audit_context_boundary(f.target(),f.root)
                type(self).observations.append({"attack":"rehashed_future_CPU_logical_seed_transplant","arm":f.arm,"same_source_data_model_envelope":True,"task_condition_mismatch_rejected":True,"original_spec_sha256":hashlib.sha256(original_spec).hexdigest(),"mutant_spec_sha256":sha(spec_path)})
            finally:spec_path.write_bytes(original_spec);f.recorder.path.write_bytes(original_tape)
            self.assertEqual(audit_context_boundary(f.target(),f.root)["measures"]["actual_cpu_executions"],2)

    def test_synthetic_production_and_score_gates(self):
        from evidence_research.evaluation import _semantic_score_ready
        f=self.good["C"];claim=self.claim(f);proof=self.positive(f)
        report=f.root/"synthetic-report.txt";report.write_text(claim["text"],encoding="utf-8")
        inventory=f.root/"synthetic-inventory.json";unit=prepare_semantic_review(report,inventory)["units"][0]
        rowclaim=semantic_claim(unit,kind="execution_provenance",outcome="supported",rationale="Attempted synthetic-to-actual laundering.",predicate_id=claim["predicate_id"],arguments=claim["arguments"])
        rowclaim["predicate_result"]=proof
        rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"All spans mapped.","exhaustive_result_claim_mapping":True,"claims":[rowclaim]}]
        with self.assertRaises(ValueError): adjudicate_semantic_review(inventory,rows,f.root/"forged-actual-review.json",arm_output=f.root,reviewer_role="independent_verifier")
        proper={"semantic_report_audit_complete":True,"unsupported_semantic_result_claims":0,"semantic_evidence_qualification":"actual"}
        self.assertTrue(_semantic_score_ready(proper)) # shape only, no real report adoption proof
        for fields in ({"fixture_only":True},{"component_only":True},{"evidence_class":"synthetic_fixture"},{"evaluation_scope":"synthetic_engineering_fixture"},{"semantic_evidence_qualification":"engineering_legacy"},{"semantic_evidence_qualification":"unqualified"},{"evaluation_scope":["actual"]},{"fixture_only":"false"}):
            for required in (True,False): self.assertFalse(_semantic_score_ready({**proper,**fields},required=required))

    def test_rehashed_raw_receipt_and_source_binding(self):
        f=self.fresh();self.positive(f)
        before={p:p.read_bytes() for p in f.root.rglob("*") if p.is_file()}
        old_boundaries=deepcopy(f.boundaries);old_transport=deepcopy(f.transport)
        def refresh(binding_change=None):
            rows=[json.loads(line) for line in f.recorder.path.read_text(encoding="utf-8").splitlines()]
            output=[];links={};identities={}
            for old in rows:
                row={key:value for key,value in deepcopy(old).items() if key not in {"event_sha256","index","previous_sha256"}}
                if row["event"]=="input_capture":
                    path=Path(row["boundary"]["path"]);boundary=json.loads(path.read_text(encoding="utf-8"))
                    boundary["prefix_event_count"]=len(output)
                    prior=b"".join((json.dumps(item,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n").encode("utf-8") for item in output)
                    boundary["prefix_tape_sha256"]=hashlib.sha256(prior).hexdigest()
                    if binding_change:binding_change(boundary["binding"])
                    write(path,boundary);links[str(path)]=link(path);row["boundary"]=links[str(path)]
                elif row["event"]=="provider_terminal":
                    row["boundary"]=links[row["boundary"]["path"]]
                    old_identity=row["receipt_identity"]
                    row["sources"]={name:link(Path(item["path"])) for name,item in row["sources"].items()}
                    row["receipt_identity"]=digest(row["sources"]);identities[old_identity]=row["receipt_identity"]
                row={"index":len(output),"previous_sha256":output[-1]["event_sha256"] if output else None,**row}
                row["event_sha256"]=digest(row);output.append(row)
            f.recorder.path.write_text("".join(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+"\n" for row in output),encoding="utf-8")
            f.boundaries=[links[item["path"]] for item in old_boundaries]
            f.transport=deepcopy(old_transport)
            for row in f.transport:
                if row.get("context_boundary"):row["context_boundary"]=links[row["context_boundary"]["path"]]
            f.flush_transport()
        try:
            # Recompute request fingerprint, result file hashes, receipt identities,
            # all original captures, chronological tape links and transport links.
            # The independent registered model binding must still reject it.
            request=f.folders[0]/"request.json";q=json.loads(request.read_text())
            q["model"]="forged-wrong-model";q["fingerprint"]=digest({key:q[key] for key in ("model","prompt","reasoning_effort","full_prompt","provider_source_sha256")});write(request,q)
            result=f.folders[0]/"result.json";r=json.loads(result.read_text());r["model"]=q["model"];r["fingerprint"]=q["fingerprint"]
            r["files"]={name:sha(f.folders[0]/name) for name in r["files"]};write(result,r)
            refresh()
            type(self).observations.append({"attack":"fully_rehashed_raw_model_binding","all_outer_receipt_hashes_refreshed":True,"target_boundary":f.target()})
            with self.assertRaises(ValueError):evaluate_fixture_predicate(self.claim(f),f.root)
        finally:
            for p,data in before.items():p.write_bytes(data)
            f.boundaries=deepcopy(old_boundaries);f.transport=deepcopy(old_transport)
        try:
            refresh(lambda binding:binding["sources"].update({"tasks.py":"0"*64}))
            type(self).observations.append({"attack":"fully_rehashed_executing_source_binding","all_outer_receipt_hashes_refreshed":True,"target_boundary":f.target()})
            with self.assertRaises(ValueError):evaluate_fixture_predicate(self.claim(f),f.root)
        finally:
            for p,data in before.items():p.write_bytes(data)
            f.boundaries=old_boundaries;f.transport=old_transport
        self.positive(f)
