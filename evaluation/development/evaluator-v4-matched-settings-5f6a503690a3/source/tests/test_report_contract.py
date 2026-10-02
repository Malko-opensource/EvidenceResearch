from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from evidence_research.report_contract import REPORT_SCHEMA_VERSION, verify_report_contract
from evidence_research.tasks import make_spec, run_task, sha256_file, write_json
from evidence_research.verifier import verify
from evidence_research.evaluation import (EFFICIENCY_PROTOCOL_VERSION, analyze_pairs, paired_uncertainty,
    _audit_telemetry, prepare_numeric_review, adjudicate_numeric_review)


class ReportContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.run=self.root / "actual-cpu"
        self.spec=make_spec("dev-quadratic",71,{"degree":2,"alpha":0.1})
        run_task(self.spec,self.run)
        self.verification=verify(self.spec,json.loads((self.run / "result.json").read_text()),self.run)
        self.report={"schema_version":REPORT_SCHEMA_VERSION,"goal":"Study validation prediction.",
            "hypothesis":self.spec["hypothesis"],"selected_config":self.spec["config"],
            "provenance":{k:self.spec[k] for k in ("task_id","task_version","seed","split_manifest_sha256","implementation_sha256","evaluator_sha256")},
            "execution":{"kind":self.spec["execution_entrypoint"]["kind"],"entrypoint":self.spec["command"],"reproduction_command":self.spec["reproduction_command"]},
            "evidence":[{"path":str(self.run / "result.json"),"sha256":sha256_file(self.run / "result.json")}],
            "measured_metrics":[{"metric":"validation_mse","value":self.verification["metrics"]["validation_mse"],"kind":"measured","evidence_path":str(self.run / "result.json"),"evidence_sha256":sha256_file(self.run / "result.json")}],
            "selection_reason":"Registered configuration independently verified.","unresolved":[],
            "limitations":["Only a development split is measured."],"next_questions":["Does the candidate generalize?"],
            "references":[{"kind":"literature","url":"https://arxiv.org/abs/2501.04227","claim":"Literature describes the original workflow."}],
            "resources":{"tokens_known":False,"token_usage":None,"seconds":None,"scope":"No model call in this unit test; CPU evidence only."}}
    def audit(self,report):
        path=self.root / "report.json"; write_json(path,report)
        return verify_report_contract(path,arm_output=self.root,spec=self.spec,verification=self.verification,selected_run_dir=self.run)
    def test_common_sufficient_content_with_actual_cpu_evidence(self):
        self.assertTrue(self.audit(self.report)["valid"])
    def test_fabricated_metrics_are_rejected(self):
        r=deepcopy(self.report);r["measured_metrics"][0]["value"]=0
        self.assertFalse(self.audit(r)["valid"])
    def test_missing_research_content_is_rejected(self):
        for field in ("hypothesis","limitations","references","next_questions","execution"):
            with self.subTest(field=field):
                r=deepcopy(self.report);r.pop(field)
                self.assertFalse(self.audit(r)["valid"])
    def test_wrong_seed_or_changed_evidence_is_rejected(self):
        r=deepcopy(self.report);r["provenance"]["seed"]+=1
        self.assertFalse(self.audit(r)["valid"])
        (self.run / "result.json").write_text("{}")
        self.assertFalse(self.audit(self.report)["valid"])

    def test_primary_and_companion_have_separate_independent_reviews(self):
        links=[];sources=[]
        for name in ("primary","companion"):
            path=self.root / f"{name}.txt";path.write_text("No measured numerical claim in this fixture.")
            inventory=self.root / f"{name}-inventory.json";prepare_numeric_review(path,inventory)
            review=self.root / f"{name}-review.json";adjudicate_numeric_review(inventory,[],review,reviewer_role="independent_verifier")
            links.append({"path":str(review),"sha256":sha256_file(review)})
            sources.append({"path":str(path),"sha256":sha256_file(path)})
        telemetry={"provenance":"trusted_host_audit","duplicate_executions":0,"recovered_errors":0,
                   "unsupported_claims":0,"verified_memory_hits":0,"sources":sources,
                   "report_review_paths":links,"claim_audit_scope":"whole_report_and_companion_numeric_inventories"}
        telemetry_path=self.root / "telemetry.json";write_json(telemetry_path,telemetry)
        counters,evidence=_audit_telemetry({"telemetry_evidence_path":str(telemetry_path)},self.root)
        self.assertTrue(counters["whole_report_numeric_audit_complete"])
        self.assertEqual(len(evidence["report_claim_review"]),2)
        telemetry["unsupported_claims"]=1;write_json(telemetry_path,telemetry)
        with self.assertRaisesRegex(ValueError,"aggregate unsupported"):
            _audit_telemetry({"telemetry_evidence_path":str(telemetry_path)},self.root)


class ConservativeEfficiencyTests(unittest.TestCase):
    def fixture(self):
        names=[f"fixture{i}" for i in range(9)]
        protocol={"version":EFFICIENCY_PROTOCOL_VERSION,"suite":{"task_ids":names},"model_effect_A":{"status":"unavailable"},
                  "adoption":{"token_gain_ci95_lower_greater_than":.2,"quality_log_ratio_ci95_upper_less_than":.0953101798043249},
                  "baseline_provenance":{"kind":"upstream_adaptation"},"primary_metric":"token_efficiency_with_noninferior_quality"}
        rows=[]
        for name in names:
            arms={}
            for arm,total in (("B",1000),("C",100)):
                arms[arm]={"status":"verified","task_success":True,"test_mse":.1,"validation_mse":.1,
                     "execution_seconds":.01,"arm_wall_seconds":1,"provider_calls":1,"provider_attempts":1,
                     "duplicate_executions":0,"recovered_errors":0,"unsupported_claims":0,"verified_memory_hits":0,
                     "provider_billed_cost":None,"whole_report_numeric_audit_complete":True,"common_report_sufficiency":True,
                     "provider_token_usage":{"input_tokens":total-1,"output_tokens":1},
                     "total_provider_token_usage":{"input_tokens":total-1,"output_tokens":1},"unknown_token_usage":False}
            rows.append({"unit_id":name,"relative_gain":0,**arms})
        return protocol,rows
    def test_known_usage_efficiency_and_quality_gates_both_pass(self):
        protocol,rows=self.fixture();report=analyze_pairs(protocol,rows)
        self.assertTrue(report["adopted"])
    def test_unknown_B_is_null_and_only_conservative_bound(self):
        protocol,rows=self.fixture()
        for row in rows:
            row["B"]["unknown_token_usage"]=True;row["B"]["total_provider_token_usage"]=None;row["B"]["provider_attempts"]=2
        report=analyze_pairs(protocol,rows)
        self.assertTrue(report["adopted"])
        self.assertEqual(report["efficiency_effect_B_vs_C"]["token_reduction_scope"],"conservative lower bounds")
        self.assertIsNone(rows[0]["B"]["total_provider_token_usage"])
    def test_unknown_C_blocks_adoption_even_with_large_known_gain(self):
        protocol,rows=self.fixture();rows[0]["C"]["unknown_token_usage"]=True;rows[0]["C"]["total_provider_token_usage"]=None
        self.assertEqual(analyze_pairs(protocol,rows)["status"],"inconclusive")
    def test_inadequate_report_or_inferior_quality_blocks_efficiency(self):
        protocol,rows=self.fixture();rows[0]["C"]["common_report_sufficiency"]=False
        self.assertFalse(analyze_pairs(protocol,rows)["adopted"])
        protocol,rows=self.fixture()
        for row in rows:row["C"]["test_mse"]=.2
        self.assertFalse(analyze_pairs(protocol,rows)["adopted"])
    def test_componentwise_bounds_have_monotone_bootstrap_endpoints(self):
        bound=[.1+.05*i for i in range(9)];actual=[v+.1 for v in bound]
        b=paired_uncertainty(bound);a=paired_uncertainty(actual)
        self.assertLessEqual(b["mean"],a["mean"])
        self.assertLessEqual(b["ci95"][0],a["ci95"][0])

if __name__=="__main__":unittest.main()
