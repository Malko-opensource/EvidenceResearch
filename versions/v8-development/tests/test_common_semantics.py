"""Prospective c7 engineering fixtures; no actual provider or research study.

Synthetic transport is always ineligible for adoption. Small trusted CPU fits
exercise arithmetic/source contracts only; no hidden original owner data exists
in these fixtures, and no observed study/report is revised by this module.
"""
import ast
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from evidence_research.context_boundary import ContextBoundaryRecorder
from evidence_research.model import CodexProvider
from evidence_research.report_semantics import (FACT_CORPUS_SHA256, FACT_REGISTRY_SHA256,
    _check_nonresult_scope, _review_claim, evaluate_predicate, evaluate_fixture_predicate,
    evaluate_fixture_nonresult_context, frozen_semantic_reference_hashes,
    parse_temporal_resource_list, prepare_semantic_review, semantic_claim, semantic_units,
    run_reference, adjudicate_semantic_review)
from evidence_research.tasks import (make_spec, run_task, sha256_file, split_manifest,
    task_data, write_json)
from evidence_research.verifier import verify
from tests.test_context_boundaries import TapeFixture


def link(path):
    return {"path":str(path.resolve()),"sha256":sha256_file(path)}


class TrustedCPUFixture(TapeFixture):
    """Explicit synthetic provider tape plus independently verified CPU contracts."""
    def __init__(self,root,arm="C"):
        self.root=Path(root); self.root.mkdir(parents=True); self.arm=arm
        self.envelope={"reasoning_effort":"medium","proposal_calls_per_unit":20,"actual_cpu_executions_per_unit":20}
        data=task_data("dev-quadratic",457)
        bundle={"train":data["train"],"validation":data["validation"],"split_manifest":split_manifest("dev-quadratic",457)}
        self.public={"task_id":"dev-quadratic","seed":457,"task_bundle":bundle}
        sources=Path(__file__).resolve().parents[1]/"evidence_research"
        self.registration=self.root/"callback-registration.json"
        write_json(self.registration,{"public_task":self.public,"model_id":"synthetic-model","resource_envelope":self.envelope,
            "implementation_sha256":sha256_file(sources/("arms.py" if arm=="B" else "comparison_arms.py")),"fixture_only":True})
        self.recorder=ContextBoundaryRecorder(self.root,arm=arm,registration=self.registration,
            model_id="synthetic-model",resource_envelope=self.envelope,public_task=self.public,fixture_only=True)
        self.provider=SimpleNamespace(model="synthetic-model",reasoning_effort="medium",guard=CodexProvider.guard,evidence_dir=self.root/"model")
        self.transport=self.root/"model-transport.jsonl"; self.index=0; self.cpu_index=0

    def cpu(self,*,config=None,output_includes_metrics=True,hypothesis=None,baseline=None,model_evidence=None,fixture_only=False,provenance=None):
        folder=self.root/f"research/runs/component-{self.cpu_index:04d}"; self.cpu_index+=1
        folder.mkdir(parents=True)
        spec=make_spec(self.public["task_id"],self.public["seed"],config or {"degree":2,"alpha":0.0},
            model="synthetic-model",resource_envelope=self.envelope,task_bundle=self.public["task_bundle"])
        if hypothesis is not None: spec["hypothesis"]=hypothesis
        if baseline is not None: spec["baseline"]={"run_id":baseline.name}
        if model_evidence is not None: spec["model_evidence"]=model_evidence
        if fixture_only is not False: spec["fixture_only"]=fixture_only
        if provenance is not None: spec.update(provenance)
        write_json(folder/"registered_spec.json",spec)
        result=run_task(spec,folder); checked=verify(spec,result,folder)
        if checked["valid"] is not True: raise AssertionError(checked)
        metrics=checked["metrics"]
        block=json.dumps({"execution_kind":"actual_cpu_execution","execution_id":folder.name,
            **({"metrics":metrics} if output_includes_metrics else {"result_path":str(folder/"result.json")})},sort_keys=True)
        self.recorder.record_cpu_return(logical_context={"ordinal":self.cpu_index-1,"host_ordinal":len(self.recorder.rows),"phase":"EXECUTE","role":"component_fixture"},
            returned_text=block,records=[{"run_dir":str(folder)}])
        return folder,metrics,block


def resource_claim(boundary,*,text="Before this proposal, measured resources were 10 input tokens and 3 output tokens.",measure="input_tokens",value=10):
    return {"kind":"measured_result","predicate_id":"historical_context_resources","text":text,
        "arguments":{"boundary":boundary,"scope":"historical_pre_request","measure":measure,"value":value}}


class CommonResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="c7-common-resource-"); self.root=Path(self.temp.name).resolve()
    def tearDown(self): self.temp.cleanup()

    def test_equivalent_b_c_fixture_proofs_are_explicitly_not_actual_support(self):
        values=[]
        for arm in ("B","C"):
            f=TapeFixture(self.root/arm,arm); f.model(); b,_,_=f.model()
            claim=resource_claim(b); proof=evaluate_fixture_predicate(claim,f.root)
            self.assertFalse(proof["facts"]["adoption_eligible"])
            self.assertEqual(proof["facts"]["evidence_class"],"synthetic_fixture")
            self.assertEqual(proof["facts"]["evaluation_scope"],"synthetic_engineering_fixture")
            values.append(proof["facts"])
            with self.assertRaises(ValueError): evaluate_predicate(claim,f.root)
            claim["arguments"]["component_fixture"]=True
            with self.assertRaises(ValueError): evaluate_predicate(claim,f.root)
            with self.assertRaises(TypeError): evaluate_predicate(claim,f.root,_component_fixture=True)
        self.assertEqual(values[0],values[1])

    def test_every_quantity_is_checked_not_only_selected_scalar(self):
        f=TapeFixture(self.root/"C"); f.model(); b,_,_=f.model()
        with self.assertRaises(ValueError): evaluate_fixture_predicate(resource_claim(b,text="Before this proposal, measured resources were 10 input tokens and 99 output tokens."),f.root)

    def test_unknown_failed_usage_never_zero_but_time_can_be_audited(self):
        f=TapeFixture(self.root/"C"); f.model(); f.model(failed=True); b,_,_=f.model()
        with self.assertRaises(ValueError): evaluate_fixture_predicate(resource_claim(b,value=0,text="Before this proposal, measured input usage was 0 tokens."),f.root)
        proof=evaluate_fixture_predicate(resource_claim(b,measure="wall_seconds",value=2.5,text="Before this request, measured resources were 2.50 provider wall seconds."),f.root)
        self.assertEqual(proof["facts"]["value"],2.5)

    def test_missing_logical_or_host_receipt_is_not_a_fixture_positive(self):
        f=TapeFixture(self.root/"C"); f.model(); b,_,_=f.model(logical=False)
        with self.assertRaises(ValueError): evaluate_fixture_predicate(resource_claim(b),f.root)
        f=TapeFixture(self.root/"orphan"); f.model(); b,_,_=f.model()
        orphan=f.root/"model/improved-9999"; orphan.mkdir(); (orphan/"request.json").write_text("{}",encoding="utf-8")
        with self.assertRaises(ValueError): evaluate_fixture_predicate(resource_claim(b),f.root)

    def test_production_review_rejects_fixture_proof_even_when_numeric_values_match(self):
        f=TapeFixture(self.root/"C"); f.model(); b,_,_=f.model()
        report=f.root/"report.txt"; text="Before this proposal, measured input usage was 10 tokens."; report.write_text(text,encoding="utf-8")
        inventory=f.root/"semantic-inventory.json"; unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="measured_result",outcome="supported",rationale="Attempted fixture transfer to actual report.",
            predicate_id="historical_context_resources",arguments=resource_claim(b)["arguments"])
        claim["predicate_result"]=evaluate_fixture_predicate(claim,f.root)
        rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Complete exact span.","exhaustive_result_claim_mapping":True,"claims":[claim]}]
        with self.assertRaises(ValueError): adjudicate_semantic_review(inventory,rows,f.root/"review.json",arm_output=f.root,reviewer_role="independent_verifier")

    def test_all_nonresult_report_preserves_explicit_original_arm_fixture_scope(self):
        f=TapeFixture(self.root/"C"); f.model(); f.cpu()
        text="We propose a future comparison."; report=f.root/"nonresult.txt"; report.write_text(text,encoding="utf-8")
        inventory=f.root/"nonresult-inventory.json"; unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Future proposal with no supported metric predicate.")
        rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Complete proposal unit.","exhaustive_result_claim_mapping":True,"claims":[claim]}]
        output=f.root/"nonresult-review.json"
        record=adjudicate_semantic_review(inventory,rows,output,arm_output=f.root,reviewer_role="independent_verifier")
        self.assertEqual(record["semantic_evidence_qualification"],"component_fixture")
        self.assertTrue(record["nonactual_original_provenance"])
        from evidence_research.report_semantics import validate_semantic_review
        self.assertFalse(validate_semantic_review(output,arm_output=f.root,require_complete=False)["semantic_report_audit_complete"])
        with self.assertRaises(ValueError): validate_semantic_review(output,arm_output=f.root)

    def test_nonresult_only_alternate_arm_markers_and_malformed_metadata(self):
        from evidence_research.report_semantics import validate_semantic_review
        for key in ("fixture_only","simulation_only","test_fixture_only"):
            for index,value in enumerate((True,None,"true",1,0)):
                with self.subTest(key=key,value=value):
                    root=self.root/f"{key}-{index}"; root.mkdir()
                    write_json(root/"callback-registration.json",{key:value,"scope":"Synthetic metadata component fixture; no actual provider is asserted."})
                    report=root/"nonresult.txt"; report.write_text("We propose a future comparison.",encoding="utf-8")
                    inventory=root/"inventory.json"; unit=prepare_semantic_review(report,inventory)["units"][0]
                    claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Pure future proposal.")
                    rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Full original unit.","exhaustive_result_claim_mapping":True,"claims":[claim]}]
                    if value is True:
                        record=adjudicate_semantic_review(inventory,rows,root/"review.json",arm_output=root,reviewer_role="independent_verifier")
                        self.assertEqual(record["semantic_evidence_qualification"],"component_fixture")
                        self.assertFalse(validate_semantic_review(root/"review.json",arm_output=root,require_complete=False)["semantic_report_audit_complete"])
                    else:
                        with self.assertRaisesRegex(ValueError,"malformed fixture"): adjudicate_semantic_review(inventory,rows,root/"review.json",arm_output=root,reviewer_role="independent_verifier")


class CommonGrammarTests(unittest.TestCase):
    def test_narrow_temporal_list_and_compound_parse(self):
        cases=("Before this proposal, measured resources were 20 CPU executions, 30 input tokens and 10 output tokens.",
            "Before this request, measured provider input usage was 30 tokens.",
            "Before this proposal, 2 distinct configurations required 4 CPU executions totaling 0.125 seconds, alongside 3 completed provider calls totaling 6.50 seconds and 30 input plus 10 output tokens.")
        for text in cases:
            with self.subTest(text=text): self.assertIsNotNone(parse_temporal_resource_list(text))

    def test_unqualified_negated_unrelated_mixed_final_forecast_and_unknown_reject(self):
        cases=("Provider input usage was 30 tokens.","This document has a historical appendix. Provider input usage was 30 tokens.",
            "Historically, we tested feature design, provider input usage was 30 tokens.","Not before this proposal, provider input usage was 30 tokens.",
            "Before this proposal, measured input usage was 30 tokens; final total usage was 30 tokens.",
            "Before this proposal, measured input usage was 30 tokens, and the next experiment will improve error by 10 percent.",
            "Before this proposal, measured input usage was 30 tokens; monetary cost is unknown.",
            "Before this proposal, measured resources were 30 input tokens and 30 input tokens.",
            "Before this proposal, measured resources were 0.5 CPU executions.",
            "Before this proposal, measured resources were 0e999 provider wall seconds.")
        for text in cases:
            with self.subTest(text=text): self.assertIsNone(parse_temporal_resource_list(text))
        self.assertIsNotNone(parse_temporal_resource_list("Before this proposal, measured input usage was 30 tokens;"))
        _check_nonresult_scope("Monetary cost is unknown.","limitation")

    def test_normative_minimum_is_not_an_achieved_result(self):
        _check_nonresult_scope("The procedure should choose the observed minimum.","method")
        for text in ("The procedure achieved the minimum.","The procedure should choose the observed minimum. We achieved the best result."):
            with self.assertRaises(ValueError): _check_nonresult_scope(text,"method")

    def test_english_korean_denials_do_not_hide_other_positive_clause(self):
        for text in ("Framework improvement is not established.","프레임워크 설계 개선과 모델 교체 효과는 이 보고서에서 주장하지 않는다."):
            _check_nonresult_scope(text,"limitation")
        for text in ("Framework improvement is not established, but our framework improved research performance.",
            "프레임워크 개선은 입증하지 않는다. 그러나 우리 프레임워크는 연구 성능을 개선했다.",
            "우리 프레임워크는 연구 성능을 개선했다. 프레임워크 개선을 이 보고서에서 주장하지 않는다."):
            with self.assertRaises(ValueError): _check_nonresult_scope(text,"limitation")


class CommonSourceAndArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="c7-common-facts-"); self.root=Path(self.temp.name).resolve()
    def tearDown(self): self.temp.cleanup()

    def test_finite_fact_forms_are_only_source_attribution_in_both_languages(self):
        closure=frozen_semantic_reference_hashes()
        registry=next(Path(path) for path,digest in closure.items() if digest==FACT_REGISTRY_SHA256)
        corpus=next(Path(path) for path,digest in closure.items() if digest==FACT_CORPUS_SHA256)
        facts=json.loads(registry.read_text(encoding="utf-8"))["facts"]
        self.assertEqual(len(facts),6)
        for fact in facts:
            for form in fact["allowed_forms"]:
                claim={"text":form["text"],"kind":"literature","predicate_id":"source_fact_attribution","arguments":{
                    "source":link(corpus),"registry_sha256":FACT_REGISTRY_SHA256,"fact_id":fact["fact_id"],"form_id":form["form_id"],"url":fact["url"]}}
                proof=evaluate_predicate(claim,self.root)
                self.assertIn("synopsis attribution",proof["facts"]["scope"])
                for changed in (form["text"]+" Therefore our model is optimal.",form["text"]+" We read and understood every full paper."):
                    attack=deepcopy(claim); attack["text"]=changed
                    with self.assertRaises(ValueError): evaluate_predicate(attack,self.root)
                attack=deepcopy(claim); attack["kind"]="measured_result"
                with self.assertRaises(ValueError): evaluate_predicate(attack,self.root)
                attack=deepcopy(claim); attack["arguments"]["registry_sha256"]="0"*64
                with self.assertRaises(ValueError): evaluate_predicate(attack,self.root)
                copied=self.root/"copied-corpus.json"; copied.write_bytes(corpus.read_bytes())
                attack=deepcopy(claim); attack["arguments"]["source"]=link(copied)
                with self.assertRaises(ValueError): evaluate_predicate(attack,self.root)

    def test_exact_common_synopsis_quote_keeps_source_id_and_url_binding(self):
        sources=frozen_semantic_reference_hashes(); corpus=next(Path(path) for path,digest in sources.items() if digest==FACT_CORPUS_SHA256)
        row=json.loads(corpus.read_text(encoding="utf-8"))["records"][0]
        quote="The closed-form ridge solution depends on the feature covariance and regularization strength."
        claim={"text":quote,"kind":"literature","predicate_id":"attributed_literature","arguments":{"source":link(corpus),"source_id":row["id"],"url":row["url"],"excerpt":quote}}
        self.assertEqual(evaluate_predicate(claim,self.root)["facts"]["evidence_class"],"actual")
        for changes in ({"source_id":"2501.04227v2"},{"url":"https://arxiv.org/abs/2503.18102v1"}):
            attack=deepcopy(claim); attack["arguments"].update(changes)
            with self.assertRaises(ValueError): evaluate_predicate(attack,self.root)
        copied=self.root/"copy.txt"; copied.write_bytes(corpus.read_bytes()); attack=deepcopy(claim); attack["arguments"]["source"]=link(copied)
        self.assertEqual(evaluate_predicate(attack,self.root)["facts"]["evidence_class"],"engineering_legacy")

    def test_same_run_gap_direction_rounding_split_unit_and_ratio(self):
        f=TrustedCPUFixture(self.root/"C"); f.model(); folder,metrics,_=f.cpu()
        gap=metrics["validation_mse"]-metrics["train_mse"]; display=f"{gap:.8f}"
        claim={"text":f"For the named verified run, validation MSE minus training MSE is {display} MSE.","kind":"measured_result","predicate_id":"derived_metric_arithmetic",
            "arguments":{"run":run_reference(folder),"operation":"validation_minus_training","left_metric":"validation_mse","right_metric":"train_mse","unit":"mse","decimal_places":8,"value":float(display)}}
        proof=evaluate_predicate(claim,f.root); self.assertEqual(proof["facts"]["derived_value"],gap)
        for changes in ({"left_metric":"train_mse"},{"operation":"ratio"},{"unit":"percent"},{"decimal_places":7},{"value":-float(display)}):
            attack=deepcopy(claim); attack["arguments"].update(changes)
            with self.assertRaises(ValueError): evaluate_predicate(attack,f.root)
        attack=deepcopy(claim); attack["text"]+=" This proves superior generalization."
        with self.assertRaises(ValueError): evaluate_predicate(attack,f.root)
        attack=deepcopy(claim); attack["arguments"]["run"]["sources"][0]["sha256"]="0"*64
        with self.assertRaises(ValueError): evaluate_predicate(attack,f.root)

    def test_explicit_fixture_cpu_arithmetic_never_completes_actual_report(self):
        f=TrustedCPUFixture(self.root/"C"); f.model(); folder,metrics,_=f.cpu(fixture_only=True)
        displayed=f"{metrics['validation_mse']-metrics['train_mse']:.8f}"
        text=f"For the named verified run, validation MSE minus training MSE is {displayed} MSE."
        report=f.root/"fixture-gap.txt"; report.write_text(text,encoding="utf-8"); inventory=f.root/"fixture-gap-inventory.json"
        unit=prepare_semantic_review(report,inventory)["units"][0]
        claim=semantic_claim(unit,kind="measured_result",outcome="supported",rationale="Component arithmetic whose original CPU spec explicitly declares fixture scope.",predicate_id="derived_metric_arithmetic",
            arguments={"run":run_reference(folder),"operation":"validation_minus_training","left_metric":"validation_mse","right_metric":"train_mse","unit":"mse","decimal_places":8,"value":float(displayed)})
        self.assertEqual(evaluate_predicate(claim,f.root)["facts"]["evidence_class"],"synthetic_fixture")
        rows=[{"unit_id":unit["unit_id"],"outcome":"reviewed","rationale":"Complete exact arithmetic span.","exhaustive_result_claim_mapping":True,"claims":[claim]}]
        review=adjudicate_semantic_review(inventory,rows,f.root/"fixture-gap-review.json",arm_output=f.root,reviewer_role="independent_verifier")
        self.assertEqual(review["semantic_evidence_qualification"],"component_fixture")
        from evidence_research.report_semantics import validate_semantic_review
        checked=validate_semantic_review(f.root/"fixture-gap-review.json",arm_output=f.root,require_complete=False)
        self.assertFalse(checked["semantic_report_audit_complete"])
        review["semantic_evidence_qualification"]="actual"; write_json(f.root/"forged-actual-review.json",review)
        with self.assertRaises(ValueError): validate_semantic_review(f.root/"forged-actual-review.json",arm_output=f.root,require_complete=False)

    def test_malformed_original_fixture_marker_does_not_default_to_actual(self):
        f=TrustedCPUFixture(self.root/"C"); f.model(); folder,metrics,_=f.cpu(fixture_only="yes")
        display=f"{metrics['validation_mse']-metrics['train_mse']:.8f}"
        claim={"text":f"For the named verified run, validation MSE minus training MSE is {display} MSE.","kind":"measured_result","predicate_id":"derived_metric_arithmetic",
            "arguments":{"run":run_reference(folder),"operation":"validation_minus_training","left_metric":"validation_mse","right_metric":"train_mse","unit":"mse","decimal_places":8,"value":float(display)}}
        with self.assertRaisesRegex(ValueError,"malformed fixture"): evaluate_predicate(claim,f.root)

    def test_all_declared_nonactual_cpu_markers_and_malformed_types_propagate(self):
        for key in ("fixture_only","simulation_only","test_fixture_only"):
            for index,value in enumerate((True,None,"true",1,0,[],{})):
                with self.subTest(key=key,value=value):
                    f=TrustedCPUFixture(self.root/f"{key}-{index}"); f.model()
                    folder,metrics,_=f.cpu(provenance={key:value})
                    display=f"{metrics['validation_mse']-metrics['train_mse']:.8f}"
                    claim={"text":f"For the named verified run, validation MSE minus training MSE is {display} MSE.","kind":"measured_result","predicate_id":"derived_metric_arithmetic",
                        "arguments":{"run":run_reference(folder),"operation":"validation_minus_training","left_metric":"validation_mse","right_metric":"train_mse","unit":"mse","decimal_places":8,"value":float(display)}}
                    if value is True:
                        proof=evaluate_predicate(claim,f.root)
                        self.assertEqual(proof["facts"]["evidence_class"],"synthetic_fixture")
                        self.assertFalse(proof["facts"]["adoption_eligible"])
                    else:
                        with self.assertRaisesRegex(ValueError,"malformed fixture"): evaluate_predicate(claim,f.root)

    def test_named_metric_input_is_value_bound_not_paths_or_entire_history(self):
        for arm in ("B","C"):
            f=TrustedCPUFixture(self.root/arm,arm); f.model(); folder,metrics,block=f.cpu()
            prompt=block if arm=="B" else json.dumps({"verified_memory":[{"run_id":folder.name,"metrics":metrics}]},sort_keys=True)
            b,_,_=f.model(prompt)
            claim={"kind":"execution_provenance","text":"The named original reporting input contains validation MSE values for 1 verified run.","predicate_id":"report_input_availability",
                "arguments":{"boundary":b,"scope":"named_original_input","metric":"validation_mse","count":1,"count_kind":"runs"}}
            self.assertEqual(evaluate_fixture_predicate(claim,f.root)["facts"]["count"],1)
            with self.assertRaises(ValueError): evaluate_predicate(claim,f.root)
            later,_,_=f.model(str(folder/"result.json")); attack=deepcopy(claim); attack["arguments"]["boundary"]=later
            with self.assertRaises(ValueError): evaluate_fixture_predicate(attack,f.root)
            attack=deepcopy(claim); attack["text"]="The agent had only one score."
            with self.assertRaises(ValueError): evaluate_fixture_predicate(attack,f.root)


class CommonPlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="c7-common-planning-"); self.root=Path(self.temp.name).resolve()
    def tearDown(self): self.temp.cleanup()

    def unit(self,text,field="goal"):
        return next(row for row in semantic_units(json.dumps({field:text}),"f"*64) if row["unit_kind"]=="json_string")

    def test_host_fixed_questions_common_b_c_and_past_result_attack(self):
        source_root=Path(__file__).resolve().parents[1]/"evidence_research"
        for name in ("arms.py","comparison_arms.py"):
            path=source_root/name; tree=ast.parse(path.read_text(encoding="utf-8")); questions=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Dict):
                    for key,value in zip(node.keys,node.values):
                        if isinstance(key,ast.Constant) and key.value=="next_questions" and isinstance(value,ast.List):
                            questions.extend(item.value for item in value.elts if isinstance(item,ast.Constant) and isinstance(item.value,str))
            self.assertTrue(questions)
            for text in questions:
                unit=next(row for row in semantic_units(json.dumps({"next_questions":[text]}),"f"*64) if row["unit_kind"]=="json_string")
                claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Bound host future question.",nonresult_context={"kind":"fixed_next_question","source":link(path)})
                _review_claim(claim,unit,self.root)
        _check_nonresult_scope("Does removing memory change decisions?","proposal",fixed_question=True)
        for text in ("Did we achieve the best result?","We achieved the best result. Will we test again?"):
            with self.assertRaises(ValueError): _check_nonresult_scope(text,"proposal",fixed_question=True)

    def test_original_planning_prior_and_future_or_wrong_descriptor_reject(self):
        f=TrustedCPUFixture(self.root/"C"); f.model(); prior,_,_=f.cpu(config={"degree":6,"alpha":0.0})
        text="We propose to test regularization against the measured unregularized degree-6 model."
        b,_,_=f.model(json.dumps({"goal":text},sort_keys=True)); unit=self.unit(text)
        context={"kind":"context_boundary","boundary":b,"field":"goal","prior_runs":[run_reference(prior)]}
        claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Prospective exact original field with prior proof.",nonresult_context=context)
        proof=evaluate_fixture_nonresult_context(claim,unit,f.root); self.assertFalse(proof["adoption_eligible"])
        with self.assertRaises(ValueError): _review_claim(claim,unit,f.root)
        no_prior=deepcopy(claim); no_prior["nonresult_context"]["prior_runs"]=[]
        with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(no_prior,unit,f.root)
        future,_,_=f.cpu(config={"degree":6,"alpha":1.0}); attack=deepcopy(claim); attack["nonresult_context"]["prior_runs"]=[run_reference(future)]
        with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(attack,unit,f.root)
        changed="We propose to test a change to the measured unregularized quintic model."
        new,_,_=f.model(json.dumps({"goal":changed},sort_keys=True)); new_unit=self.unit(changed)
        attack=semantic_claim(new_unit,kind="proposal",outcome="classified_nonresult",rationale="Degree swap attack.",nonresult_context={**context,"boundary":new})
        with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(attack,new_unit,f.root)

    def test_original_b_visible_plan_is_not_reconstructed_from_final_fields(self):
        f=TapeFixture(self.root/"B","B"); f.model()
        text="We propose to test a future comparison under matched conditions."
        f.recorder.capture_report_era(logical_context={"host_ordinal":1},selected_output="Original selected result.",
            selected_code="CONFIG = {}",selected_plan=text,phase="report writing")
        b,_,_=f.model(text); unit=self.unit(text,"selected_native_plan")
        claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Original report-era plan appears in this exact input.",
            nonresult_context={"kind":"context_boundary","boundary":b,"field":"selected_native_plan","prior_runs":[]})
        self.assertFalse(evaluate_fixture_nonresult_context(claim,unit,f.root)["adoption_eligible"])
        later,_,_=f.model("A different reporting input."); attack=deepcopy(claim); attack["nonresult_context"]["boundary"]=later
        with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(attack,unit,f.root)

    def test_executed_hypothesis_requires_the_exact_origin_request_not_other_boundary(self):
        f=TrustedCPUFixture(self.root/"C"); f.model(); prior,_,_=f.cpu(config={"degree":6,"alpha":0.0})
        text="We propose to test regularization against the measured unregularized degree-6 model."
        boundary,provider,_=f.model(json.dumps({"goal":text},sort_keys=True)); request=json.loads((provider/"request.json").read_text(encoding="utf-8"))
        candidate,_,_=f.cpu(config={"degree":6,"alpha":0.1},hypothesis=text,baseline=prior,
            model_evidence={"call_id":provider.name,"fingerprint":request["fingerprint"]})
        unit=self.unit(text); context={"kind":"registered_hypothesis","boundary":boundary,"run":run_reference(candidate),"prior_runs":[run_reference(prior)]}
        claim=semantic_claim(unit,kind="proposal",outcome="classified_nonresult",rationale="Same-source actual hypothesis with pre-request prior.",nonresult_context=context)
        self.assertFalse(evaluate_fixture_nonresult_context(claim,unit,f.root)["adoption_eligible"])
        other,_,_=f.model(json.dumps({"goal":text,"instructions":"Different request with the same words."},sort_keys=True))
        attack=deepcopy(claim); attack["nonresult_context"]["boundary"]=other
        with self.assertRaises(ValueError): evaluate_fixture_nonresult_context(attack,unit,f.root)


if __name__=="__main__": unittest.main()
